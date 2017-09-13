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
from sqlalchemy import or_

class AllocWorker(threading.Thread):
    def __init__(self, event):
        self.event = event
        threading.Thread.__init__(self)

    def run(self):
        # Run the allocation script.

        import time
        time.sleep(10)
        print("timed out worker\n")
        # Notify manager that it is worth doing re-spin.
        # Set the status to "ready" in db.
        event.set()


class Pool(object):
    max_number = 7
    max_starting = 3
    max_preallocated = 5

    def __init__(self, name):
        self.name = name

    def allocate(self, event):
        pass


    def _allocate_more_resources(self, session, event):
        while True:
            all_query = session.query(models.Resource).filter_by(pool=self.name)
            all_up = all_query.count()
            # STARTING -> READY -> TAKEN
            ready = all_query.filter(models.Resource.state.in_(['READY', 'STARTING'])).count()
            starting = all_query.filter(models.Resource.state.in_(['STARTING'])).count()

            print("ready {0}, starting {1}".format(ready, starting))

            if all_up >= self.max_number or ready >= self.max_preallocated or starting >= self.max_starting:
                break

            # resource = models.Resource()
            # resource.pool = self.name
            # session.add(resource)
            # session.commit()

            # self.allocate(event)

        #     working + ready
        #     on = ... from db ...
        #     ready = ... from db ...
        #     max = ... from config ...
        #     max_preallocate = ...
        #     for _ in range(0, pool.alloc_strategy.alloc_more(... params ...)):
        #         # Create the resource in DB, with all the parameters
        #         ...
        #         # Run the allocator
        #         AllocWorker(self.event)
        pass


class Manager(object):
    def __init__(self, event):
        self.event = event
        threading.Thread.__init__(self)

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


    def _reload_config(self):
        return [Pool('starting')]


    def _loop(self):
        session = db.SessionFactory()
        self._assign_tickets(session)
        pools = self._reload_config()
        for pool in pools:
            pool._allocate_more_resources(session, self.event)
        print("loop done... {0}".format(threading.get_ident()))


    def run(self):
        while True:
            # Wait for the request to set the event (or timeout).
            self.event.wait(timeout=15)
            self.event.clear()
            # Until the wait() is called again, any additional event.set() call
            # means another round (even though it might do nothing).
            self._loop()
