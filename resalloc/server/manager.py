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

import threading
from resalloc.server import db, models
from resalloc import helpers
from sqlalchemy import or_


class RState(helpers.StateSet):
    values = [
        'STARTING',
        'READY',
    ]


class AllocWorker(threading.Thread):
    def __init__(self, event, res_id):
        self.resource_id = res_id
        self.event = event
        threading.Thread.__init__(self)

    def run(self):
        # Run the allocation script.

        import time
        time.sleep(4)
        print("finished worker {0}".format(self.resource_id))

        session = db.SessionFactory()
        resource = session.query(models.Resource).get(self.resource_id)
        resource.state = 'READY'
        session.add(resource)
        session.commit()

        # Notify manager that it is worth doing re-spin.
        self.event.set()


class Pool(object):
    max_number = 7
    max_starting = 3
    max_preallocated = 5

    def __init__(self, name, session, event):
        print("new pool " + name)
        self.name = name
        self.session = session
        self.event = event

    def allocate(self):
        resource = models.Resource()
        resource.pool = self.name
        self.session.add(resource)
        self.session.commit()
        print ("allocating id {0}".format(resource.id))
        AllocWorker(self.event, resource.id).start()

    def _allocate_more_resources(self):
        while True:
            all_query = self.session.query(models.Resource).filter_by(pool=self.name)
            all_up = all_query.count()
            # STARTING -> READY -> TAKEN
            ready = all_query.filter(models.Resource.state.in_([RState.READY, RState.STARTING])).count()
            starting = all_query.filter(models.Resource.state.in_([RState.STARTING])).count()

            print("ready {0}, starting {1}".format(ready, starting))
            if all_up >= self.max_number \
                   or ready >= self.max_preallocated \
                   or starting >= self.max_starting:
                break

            self.allocate()


class Manager(object):
    def __init__(self, event):
        self.event = event

    def _assign_tickets(self, session):
        # # Assign tickets with resources.
        # tickets = select_in_new_state.order_by id
        # for ticket in tickets:
        #     if not exists_resource:
        #         continue

        #     resource.state = taken
        #     ticket.state = assigned
        #     ticket.resource = resource
        pass


    def _reload_config(self, session):
        print("loading config")
        pool = Pool('test_pool', session, self.event)
        return [pool]


    def _loop(self):
        session = db.SessionFactory()
        self._assign_tickets(session)
        pools = self._reload_config(session)
        for pool in pools:
            pool._allocate_more_resources()
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
