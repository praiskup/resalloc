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

import os, sys
import threading
import subprocess
from resalloc.server import db, models
from resalloc import helpers
from resalloc.helpers import RState
from resalloc.server.logic import QResources, QTickets
from resalloc.server.config import CONFIG_DIR
from sqlalchemy import or_


class Worker(threading.Thread):
    def __init__(self, event, pool, res_id):
        self.resource_id = res_id
        self.pool = pool
        self.event = event
        threading.Thread.__init__(self)


class TerminateWorker(Worker):
    def close(self):
        session = db.Session()
        resource = session.query(models.Resource).get(self.resource_id)
        resource.state = RState.ENDED
        session.add(resource)
        session.commit()
        db.Session.remove()
        self.event.set()

    def run(self):
        if not self.pool.cmd_delete:
            self.close()
            return

        try:
            subprocess.check_output(self.pool.cmd_delete, shell=True)
            self.close()
        except subprocess.CalledProcessError as e:
            return


class AllocWorker(Worker):

    def run(self):
        # Run the allocation script.

        print("running spinup command: {0}".format(self.pool.cmd_new))
        retval = 0
        output = ''
        try:
            output = subprocess.check_output(self.pool.cmd_new, shell=True)
        except subprocess.CalledProcessError as e:
            output = e.output
            retval = e.returncode

        session = db.Session()
        resource = session.query(models.Resource).get(self.resource_id)
        resource.state = RState.ENDED if retval else RState.UP
        # TODO: limit for output size?
        resource.data = output
        tags = []
        if type(self.pool.tags) != type([]):
            print("'tags' is not array")
        else:
            for tag in self.pool.tags:
                tag_obj = models.ResourceTag()
                tag_obj.id = tag
                tag_obj.resource_id = resource.id
                tags.append(tag_obj)

        print("the state == " + resource.state)
        session.add_all(tags + [resource])
        session.commit()
        db.Session.remove()

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
        print("new pool " + name)
        self.name = name
        self.event = event

    def validate(self):
        assert(self.cmd_new)
        assert(self.cmd_delete)

    def allocate(self, session):
        resource = models.Resource()
        resource.pool = self.name
        session.add(resource)
        session.commit()
        print ("allocating id {0}".format(resource.id))
        AllocWorker(self.event, self, int(resource.id)).start()

    def from_dict(self, data):
        allowed_types = [int, str, dict, type(None)]

        if type(data) != dict:
            # TODO: warning
            return

        for key in data:
            if not hasattr(self, key):
                print("useless config " + key)
                continue

            local = getattr(self, key)
            conf_type = type(local)
            if not conf_type in allowed_types:
                continue

            if conf_type == dict:
                setattr(self, key, merge_dict(local, data[key]))
            else:
                setattr(self, key, data[key])

    def _allocate_more_resources(self, session):
        while True:
            qres = QResources(session)
            up, ready, starting, taken = qres.stats()
            print("pool {0}, ready {1}, starting {2}, taken {3}, up {4}"\
                    .format(self.name, ready, starting, taken, up))
            if up >= self.max \
                   or ready + starting >= self.max_prealloc \
                   or starting >= self.max_starting:
                # Quota reached, don't allocate more.
                break

            self.allocate(session)

    def _garbage_collector(self, session):
        qres = QResources(session)
        for resource in qres.clean_candidates().all():
            TerminateWorker(self.event, self, int(resource.id)).start()


class Manager(object):
    def __init__(self, sync):
        self.sync = sync

    def _notify_waiting(self, thread_id):
        self.sync.tid = thread_id
        with self.sync.resource_ready:
            self.sync.resource_ready.notify_all()

    def _assign_tickets(self, session):
        qticket = QTickets(session)
        tickets = qticket.new().order_by(models.Ticket.id).all()

        for ticket in tickets:
            qres = QResources(session)
            resources = qres.ready().all()
            ticket_tags = ticket.tag_set
            for resource in resources:
                res_tags = resource.tag_set
                if ticket_tags.issubset(res_tags):
                    ticket.resource = resource
                    session.add_all([resource, ticket])
                    session.commit()
                    if ticket.tid:
                        self._notify_waiting(ticket.tid)
                    break


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
        session = db.Session()
        self._assign_tickets(session)
        pools = self._reload_config()
        for pool in pools:
            pool._allocate_more_resources(session)
            pool._garbage_collector(session)
        session.commit()
        print("loop done...")


    def run(self):
        self._loop()
        while True:
            # Wait for the request to set the event (or timeout).
            self.sync.ticket.wait(timeout=20)
            self.sync.ticket.clear()
            # Until the wait() is called again, any additional event.set() call
            # means another round (even though it might do nothing).
            self._loop()
