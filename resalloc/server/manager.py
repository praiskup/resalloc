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
from resalloc.server import db, models
from resalloc import helpers
from resalloc.server.config import CONFIG_DIR
from sqlalchemy import or_


class RState(helpers.StateSet):
    values = [
        'STARTING',
        'READY',
        # This should be properly stopped instance, without any leftover
        # allocated resources.  The database entries may be garbage collected.
        'ENDED',
    ]


class AllocWorker(threading.Thread):
    def __init__(self, event, pool, res_id):
        self.resource_id = res_id
        self.pool = pool
        self.event = event
        threading.Thread.__init__(self)

    def run(self):
        # Run the allocation script.

        print("running spinup command: {0}".format(self.pool.cmd_new))
        retval = subprocess.call(self.pool.cmd_new, shell=True)

        session = db.SessionFactory()
        resource = session.query(models.Resource).get(self.resource_id)
        resource.state = RState.ENDED if retval else RState.READY
        print("the state == " + resource.state)
        session.add(resource)
        session.commit()
        session.close()

        # Notify manager that it is worth doing re-spin.
        self.event.set()


class Pool(object):
    max = 4
    max_starting = 1
    max_prealloc = 2

    cmd_new = None
    cmd_delete = None
    cmd_livecheck = None

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
            all_query = (session.query(models.Resource)
                                .filter_by(pool=self.name)
                                .filter(models.Resource.state.isnot(RState.ENDED)))
            all_up = all_query.count()
            ready = all_query.filter(models.Resource.state.in_([RState.READY, RState.STARTING])).count()
            starting = all_query.filter(models.Resource.state.in_([RState.STARTING])).count()

            print("pool {0}, ready {1}, starting {2}".format(self.name, ready, starting))
            if all_up >= self.max \
                   or ready >= self.max_prealloc \
                   or starting >= self.max_starting:
                # Quota reached, don't allocate more.
                break

            self.allocate(session)


class Manager(object):
    def __init__(self, event):
        self.event = event

    def _assign_tickets(self):
        # # Assign tickets with resources.
        # tickets = select_in_new_state.order_by id
        # for ticket in tickets:
        #     if not exists_resource:
        #         continue

        #     resource.state = taken
        #     ticket.state = assigned
        #     ticket.resource = resource
        pass


    def _reload_config(self):
        config_file = os.path.join(CONFIG_DIR, "pools.yaml")
        config = helpers.load_config_file(config_file)

        pools = []
        for pool_id in config:
            pool = Pool(pool_id, self.event)
            pool.from_dict(config[pool_id])
            pool.validate()
            pools.append(pool)

        return pools


    def _loop(self):
        session = db.SessionFactory()
        self._assign_tickets()
        pools = self._reload_config()
        for pool in pools:
            pool._allocate_more_resources(session)
        session.close()
        print("loop done...")


    def run(self):
        self._loop()
        while True:
            # Wait for the request to set the event (or timeout).
            self.event.wait(timeout=20)
            self.event.clear()
            # Until the wait() is called again, any additional event.set() call
            # means another round (even though it might do nothing).
            self._loop()
