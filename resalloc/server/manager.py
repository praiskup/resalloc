# Central brain of the resalloc server.
# Copyright (C) 2017 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os
import threading
import subprocess
import warnings
from resalloc.server import db, models
from resalloc.server.db import session_scope
from resalloc import helpers
from resalloc.helpers import RState
from resalloc.server.log import get_logger
from resalloc.server.logic import QResources, QTickets
from resalloc.server.config import CONFIG_DIR
from sqlalchemy import or_

log = get_logger(__name__)

class Worker(threading.Thread):
    def __init__(self, event, pool, res_id):
        self.resource_id = res_id
        self.pool = pool
        self.event = event
        threading.Thread.__init__(self)

    def run(self):
        self.log = log.getChild("worker")
        self.job()


class TerminateWorker(Worker):
    def close(self):
        with session_scope() as session:
            resource = session.query(models.Resource).get(self.resource_id)
            resource.state = RState.ENDED
            session.add(resource)
            self.event.set()

    def job(self):
        with session_scope() as session:
            resource = session.query(models.Resource).get(self.resource_id)
            resource.state = RState.DELETING
            session.add(resource)

        self.log.debug("TerminateWorker(pool={0}): \"{1}\""\
                .format(self.pool.name, self.pool.cmd_delete))
        if not self.pool.cmd_delete:
            self.close()
            return

        try:
            subprocess.check_output(self.pool.cmd_delete, shell=True)
            self.close()
        except subprocess.CalledProcessError as e:
            return


class AllocWorker(Worker):

    def job(self):
        self.log.debug(
            "Allocating new resource id={id} in pool '{pool}' by {cmd}"\
                .format(
                    id=self.resource_id,
                    pool=self.pool.name,
                    cmd=self.pool.cmd_new
                )
        )

        # Run the allocation script.
        retval = 0
        output = ''
        try:
            output = subprocess.check_output(self.pool.cmd_new, shell=True)
        except subprocess.CalledProcessError as e:
            output = e.output
            retval = e.returncode

        with session_scope() as session:
            resource = session.query(models.Resource).get(self.resource_id)
            resource.state = RState.ENDED if retval else RState.UP
            # TODO: limit for output size?
            resource.data = output
            tags = []
            if type(self.pool.tags) != type([]):
                msg = "Pool {pool} has set 'tags' set, but that's not an array"\
                        .format(pool=self.name)
                warnings.warn(msg)
            else:
                for tag in self.pool.tags:
                    tag_obj = models.ResourceTag()
                    tag_obj.id = tag
                    tag_obj.resource_id = resource.id
                    tags.append(tag_obj)

            log.debug("Allocator ends with state={0}".format(resource.state))
            session.add_all(tags + [resource])

        # Notify manager that it is worth doing re-spin.
        self.event.set()


class Pool(object):
    max = 4
    max_starting = 1
    max_prealloc = 2

    cmd_new = None
    cmd_delete = None
    cmd_livecheck = None
    tags = None

    def __init__(self, name, event):
        self.name = name
        self.event = event

    def validate(self):
        assert(self.cmd_new)
        assert(self.cmd_delete)

    def allocate(self):
        resource_id = None
        with session_scope() as session:
            resource = models.Resource()
            resource.pool = self.name
            session.add(resource)
            session.flush()
            resource_id = resource.id

        if resource_id:
            AllocWorker(self.event, self, int(resource_id)).start()

    def from_dict(self, data):
        allowed_types = [int, str, dict, type(None)]

        if type(data) != dict:
            # TODO: warning
            return

        for key in data:
            if not hasattr(self, key):
                warnings.warn("useless config option '{0}'".format(key))
                continue

            local = getattr(self, key)
            conf_type = type(local)
            if not conf_type in allowed_types:
                continue

            if conf_type == dict:
                setattr(self, key, merge_dict(local, data[key]))
            else:
                setattr(self, key, data[key])

    def _allocate_more_resources(self):
        while True:
            with session_scope() as session:
                qres = QResources(session)
                stats = qres.stats()

            msg = "=> POOL('{0}'):".format(self.name)
            for key, val in stats.items():
                msg = msg + ' {0}={1}'.format(key,val)
            log.debug(msg)

            if stats['on'] >= self.max \
                   or stats['ready'] + stats['start'] >= self.max_prealloc \
                   or stats['start'] >= self.max_starting:
                # Quota reached, don't allocate more.
                break

            self.allocate()

    def _garbage_collector(self):
        to_terminate = []
        with session_scope() as session:
            qres = QResources(session)
            to_terminate = [x.id for x in qres.clean_candidates().all()]

        for res in to_terminate:
            TerminateWorker(self.event, self, int(res)).start()


class Manager(object):
    def __init__(self, sync):
        self.sync = sync

    def _notify_waiting(self, thread_id):
        self.sync.tid = thread_id
        with self.sync.resource_ready:
            self.sync.resource_ready.notify_all()

    def _assign_tickets(self):
        with session_scope() as session:
            qticket = QTickets(session)
            tickets = [x.id for x in qticket.new().order_by(models.Ticket.id).all()]

        for ticket_id in tickets:
            notify_ticket = False
            with session_scope() as session:
                ticket = session.query(models.Ticket).get(ticket_id)
                qres = QResources(session)
                resources = qres.ready().all()
                ticket_tags = ticket.tag_set
                for resource in resources:
                    res_tags = resource.tag_set
                    if ticket_tags.issubset(res_tags):
                        # We have found appropriate resource!
                        ticket.resource = resource
                        if ticket.tid:
                            notify_ticket = ticket.tid
                        session.add_all([resource, ticket])
                        session.flush()
                        break
            if notify_ticket:
                self._notify_waiting(notify_ticket)


    def _reload_config(self):
        config_file = os.path.join(CONFIG_DIR, "pools.yaml")
        config = helpers.load_config_file(config_file)

        pools = []
        for pool_id in config:
            pool = Pool(pool_id, self.sync.ticket)
            pool.from_dict(config[pool_id])
            pool.validate()
            pools.append(pool)

        return pools


    def _loop(self):
        self._assign_tickets()
        pools = self._reload_config()
        for pool in pools:
            pool._allocate_more_resources()
            pool._garbage_collector()
        log.debug("loop done...")


    def run(self):
        self._loop()
        while True:
            # Wait for the request to set the event (or timeout).
            self.sync.ticket.wait(timeout=20)
            self.sync.ticket.clear()
            # Until the wait() is called again, any additional event.set() call
            # means another round (even though it might do nothing).
            self._loop()
