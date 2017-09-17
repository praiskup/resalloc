# Resalloc server API.
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

import time
from resalloc.server import db, models
from resalloc.helpers import TState
import threading

class Ticket(object):
    id = None
    resource = None


class ServerAPI(object):
    def __init__(self, sync):
        self.sync = sync

    def my_id(self):
        return str(threading.current_thread())

    def takeTicket(self, tags=None, signal=False):
        session = db.Session()
        ticket = models.Ticket()
        if signal:
            ticket.tid = self.my_id()

        tag_objects = []
        for tag in (tags or []):
            to = models.TicketTag()
            to.ticket = ticket
            to.id = tag
            tag_objects.append(to)

        session.add_all([ticket] + tag_objects)
        session.commit()
        ticket_id = ticket.id
        db.Session.remove()
        self.sync.ticket.set()
        return ticket_id


    def checkTicket(self, ticket_id):
        session = db.Session()
        ticket = session.query(models.Ticket).get(ticket_id)
        data = None
        if ticket.resource:
            data = ticket.resource.data
        db.Session.remove()
        return data


    def takeResource(self, tags=None):
        """ ... blocking! ... """
        ticket_id = self.takeTicket(tags, True)
        output = ""
        while True:
            with self.sync.resource_ready:
                while self.sync.resource_ready.wait(timeout=10):
                    if self.sync.tid==self.my_id():
                        break

                output = self.checkTicket(ticket_id)
                if output:
                    break

        t = Ticket()
        t.id = ticket_id
        return t


    def closeTicket(self, ticket_id):
        session = db.Session()
        ticket = session.query(models.Ticket).get(ticket_id)
        ticket.state = TState.CLOSED
        session.add(ticket)
        session.commit()
        db.Session.remove()
