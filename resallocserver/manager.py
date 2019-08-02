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
import errno
import time
import threading
import subprocess
import warnings
from resalloc import helpers
from resalloc.helpers import RState
from resallocserver import models
from resallocserver.db import session_scope
from resallocserver.log import get_logger
from resallocserver.logic import QResources, QTickets
from resallocserver.config import CONFIG_DIR, CONFIG

log = get_logger(__name__)

def run_command(pool_id, res_id, res_name, id_in_pool, command, ltype='alloc',
                catch_stdout_bytes=None):
    log.debug("running: " + command)
    pfx = 'RESALLOC_'
    env = os.environ.copy()
    env[pfx + 'ID'] = str(res_id)
    env[pfx + 'NAME'] = str(res_name)
    env[pfx + 'POOL_ID'] = str(pool_id)
    env[pfx + 'ID_IN_POOL'] = str(id_in_pool)

    ldir = os.path.join(CONFIG['logdir'], 'hooks')
    try:
        os.mkdir(ldir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    lfile = os.path.join(ldir, '{0:06d}_{1}'.format(res_id, ltype))
    with open(lfile, 'a+b') as logfile:

        if not catch_stdout_bytes:
            return {'status': subprocess.call(command, env=env, shell=True,
                                              stdout=logfile, stderr=logfile)}

        stdout_written = 0
        stdout_stopped = False

        # Run the sub-command to be captured.
        sp = subprocess.Popen(command, env=env, shell=True,
                              stdout=subprocess.PIPE, stderr=logfile)

        captured_string = b""


        for line in iter(sp.stdout.readline, b''):
            # Write to the log.
            logfile.write(line)
            logfile.flush()

            if stdout_stopped:
                continue

            if stdout_written + len(line) > catch_stdout_bytes:
                if stdout_written == 0:
                    # If nothing was written, write at least part of the stdout
                    line = line[:catch_stdout_bytes]
                    captured_string += line

                stdout_stopped = True
                captured_string += "<< trimmed >>\n"
                continue

            stdout_written += len(line)
            captured_string += line


    return {
        'status': sp.wait(),
        'stdout': captured_string,
    }


def reload_config():
    config_file = os.path.join(CONFIG_DIR, "pools.yaml")
    config = helpers.load_config_file(config_file)

    pools = {}
    for pool_id in config:
        assert not pool_id in pools
        pool = Pool(pool_id)
        pool.from_dict(config[pool_id])
        pool.validate()
        pools[pool_id] = pool

    return pools


class ThreadLocalData(threading.local):
    """
    Object of threading.local is always empty right after t.start() is called.
    But if we define __init__() here, the method is always called appropriately
    for each thread (so we have a convenient way to initialize thread-local
    data).

    This trick is described in/taken from  `_threading_local.py` (cpython).
    """
    def __init__(self, **kw):
        self.__dict__.update(kw)
        super(ThreadLocalData, self).__init__()


class Worker(threading.Thread):
    def __init__(self, event, pool, res_id):
        self.local = ThreadLocalData(
            pool=pool,
            resource_id=res_id,
        )
        self.event = event
        threading.Thread.__init__(self)

    def __getattr__(self, attr):
        return getattr(self.local, attr)

    def run(self):
        self.log = log.getChild("worker")
        self.job()


class TerminateWorker(Worker):
    def close(self):
        with session_scope() as session:
            resource = session.query(models.Resource).get(self.resource_id)
            resource.state = RState.ENDED
            session.add(resource)
            if resource.id_in_pool_object:
                session.delete(resource.id_in_pool_object)
        self.event.set()

    def job(self):
        id_in_pool = None
        with session_scope() as session:
            resource = session.query(models.Resource).get(self.resource_id)
            if resource.ticket:
                if resource.ticket.state == helpers.TState.OPEN:
                    log.warning("can't delete {0}, ticket opened"\
                                .format(resource.name))
                    return
            resource.state = RState.DELETING
            session.add(resource)
            session.flush()
            id_in_pool = resource.id_in_pool
            session.expunge(resource)

        self.log.debug("TerminateWorker(pool={0}): name={1} by: \"{2}\""\
                .format(self.pool.name, resource.name, self.pool.cmd_delete))
        if not self.pool.cmd_delete:
            self.close()
            return

        run_command(
                self.pool.id,
                resource.id,
                resource.name,
                id_in_pool,
                self.pool.cmd_delete,
                'terminate',
        )
        self.close()


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

        id_in_pool = None
        with session_scope() as session:
            resource = session.query(models.Resource).get(self.resource_id)
            id_in_pool = resource.id_in_pool
            session.expunge(resource)

        # Run the allocation script.
        output = run_command(
            self.pool.id,
            resource.id,
            resource.name,
            id_in_pool,
            self.pool.cmd_new,
            catch_stdout_bytes=512,
        )

        with session_scope() as session:
            resource.state = RState.ENDED if output['status'] else RState.UP
            resource.data = output['stdout']
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

            if resource.state == RState.ENDED:
                session.delete(resource.id_in_pool_object)


        # Notify manager that it is worth doing re-spin.
        self.event.set()


class Watcher(threading.Thread):
    def loop(self):
        log.debug("Watcher loop")
        pools = reload_config()
        to_check = {}
        with session_scope() as session:
            up = QResources(session).up().all()
            for item in up:
                if not item.pool in pools:
                    continue
                to_check[item.id] = {
                    'name': item.name,
                    'pool': item.pool,
                    'last': item.check_last_time,
                    'fail': item.check_failed_count,
                    'id_in_pool': item.id_in_pool,
                }

        for res_id, data in to_check.items():
            pool = pools[data['pool']]
            if not pool.cmd_livecheck:
                continue
            if data['last'] + pool.livecheck_period > time.time():
                # Not yet needed check.
                continue

            failed_count = 0
            rc = run_command(
                    pool.id,
                    res_id,
                    data['name'],
                    data['id_in_pool'],
                    pool.cmd_livecheck,
                    'watch')

            with session_scope() as session:
                res = session.query(models.Resource).get(res_id)
                res.check_last_time = time.time()
                if rc['status']:
                    res.check_failed_count = res.check_failed_count + 1
                    log.debug("failed check #{0} for {1}"\
                            .format(res.check_failed_count, res_id))
                else:
                    res.check_failed_count = 0
                session.add(res)
                session.flush()
                failed_count = res.check_failed_count

            if failed_count >= 3:
                log.debug("Watcher plans to kill {0}".format(res_id))
                TerminateWorker(self.event, pool, res_id).start()

    def run(self):
        while True:
            self.loop()
            time.sleep(10)


class Pool(object):
    max = 4
    max_starting = 1
    max_prealloc = 2
    # Minimal time in seconds to wait between subsequent resource starts.
    # If the resource fails to start, the timeout still applies.  Note, however,
    # that there's no event (yet?) to wake-up manager if this timeout lasts.
    start_delay = 0

    cmd_new = None
    cmd_delete = None
    cmd_livecheck = None
    livecheck_period = 600
    tags = None
    name_pattern = "{pool_name}_{id}_{datetime}"

    def __init__(self, id):
        self.id = id
        # TODO: drop this
        self.name = id


    def validate(self):
        assert(self.cmd_new)
        assert(self.cmd_delete)


    def _allocate_pool_id(self, session, resource):
        # allocate the lowest available pool_id
        ids_query = (
                session.query(models.IDWithinPool)
                       .filter_by(pool_name=self.name)
                       .order_by(models.IDWithinPool.id)
        )
        ids = {x.id: True for x in ids_query.all()}

        found_id = None
        try_id = 0
        while True:
            if try_id in ids:
                try_id += 1
                continue

            found_id = models.IDWithinPool()
            found_id.id = try_id
            found_id.pool_name = self.name
            found_id.resource_id = resource.id
            return found_id


    def allocate(self, event):
        resource_id = None
        with session_scope() as session:
            dbinfo = session.query(models.Pool).get(self.name)
            dbinfo.last_start = time.time()
            resource = models.Resource()
            resource.pool = self.name
            session.add_all([resource, dbinfo])
            session.flush()

            pool_id = self._allocate_pool_id(session, resource)
            session.add(pool_id)
            session.flush()
            log.debug("id in pool: {0}".format(pool_id.id))

            resource_id = resource.id
            fill_dict = dict(
                id=str(resource_id).zfill(8),
                pool_name=self.name)
            resource.name = helpers.careful_string_format(
                    self.name_pattern, fill_dict)
            session.add(resource)
        if resource_id:
            self.last_start = time.time()
            AllocWorker(event, self, int(resource_id)).start()

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

    def _too_soon(self):
        last_start = 0.0
        with session_scope() as session:
            dbinfo = session.query(models.Pool).get(self.name)
            if not dbinfo:
                dbinfo = models.Pool()
                dbinfo.name = self.name
                dbinfo.last_start = 0.0
                session.add(dbinfo)
            else:
                last_start = dbinfo.last_start

        is_too_soon = last_start + self.start_delay > time.time()
        if is_too_soon:
            log.debug("too soon for Pool('{0}')".format(self.name))
        return is_too_soon

    def _allocate_more_resources(self, event):
        while True:
            with session_scope() as session:
                qres = QResources(session, pool=self.name)
                stats = qres.stats()

            msg = "=> POOL('{0}'):".format(self.name)
            for key, val in stats.items():
                msg = msg + ' {0}={1}'.format(key,val)
            log.debug(msg)

            if stats['on'] >= self.max \
                   or stats['ready'] + stats['start'] >= self.max_prealloc \
                   or stats['start'] >= self.max_starting \
                   or self._too_soon():
                # Quota reached, don't allocate more.
                break

            self.allocate(event)

    def _detect_closed_tickets(self):
        with session_scope() as session:
            qres = QResources(session, pool=self.name)
            for res in qres.clean_candidates().all():
                res.state = RState.DELETE_REQUEST
                session.add(res)


    def _garbage_collector(self, event):
        to_terminate = []
        with session_scope() as session:
            qres = QResources(session, pool=self.name)
            for res in qres.clean().all():
                TerminateWorker(event, self, int(res.id)).start()


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
            tickets = [x.id for x in qticket.waiting().order_by(models.Ticket.id).all()]

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
                        ticket.resource_id = resource.id
                        if ticket.tid:
                            notify_ticket = ticket.tid
                        session.add_all([ticket])
                        break
            if notify_ticket:
                self._notify_waiting(notify_ticket)


    def _loop(self):
        log.debug("Manager's loop.")
        self._assign_tickets()
        for _, pool in reload_config().items():
            pool._allocate_more_resources(self.sync.ticket)
            pool._detect_closed_tickets()
            pool._garbage_collector(self.sync.ticket)


    def run(self):
        watcher = Watcher()
        watcher.event = self.sync.ticket
        watcher.daemon = True
        watcher.start()

        self._loop()
        while True:
            # Wait for the request to set the event (or timeout).
            self.sync.ticket.wait(timeout=20)
            # Until the wait() is called again, any additional event.set() call
            # means another round (even though it might do nothing).
            self._loop()
