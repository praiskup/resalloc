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

def cached_session(function):
    def wrap(self, *args, **kwargs):
        ret = None
        if self.session:
            ret = function(self, *args, **kwargs)
        else:
            self.session = db.Session()
            ret = function(self, *args, **kwargs)
            db.Session.remove()
            self.session = None
        return ret
    return wrap


class ServerAPI(object):
    session = None

    def __init__(self, sync):
        self.sync = sync

    def my_id(self):
        return str(threading.current_thread())

    @cached_session
    def takeTicket(self, tags=None, session=None):
        ticket = models.Ticket()
        tag_objects = []
        for tag in (tags or []):
            to = models.TicketTag()
            to.ticket = ticket
            to.id = tag
            tag_objects.append(to)

        self.session.add_all([ticket] + tag_objects)
        self.session.commit()
        ticket_id = ticket.id
        self.sync.ticket.set()
        return ticket_id


    @cached_session
    def _checkTicket(self, ticket_id):
        ticket = self.session.query(models.Ticket).get(ticket_id)
        return ticket.resource

    @cached_session
    def collectTicket(self, ticket_id, session=None):
        output = {
            'ready': False,
            'output': None,
        }
        resource = self._checkTicket(ticket_id)
        if resource:
            output['output'] = resource.data
            output['ready'] = True

        return output

    @cached_session
    def waitTicket(self, ticket_id):
        """ ... blocking! ... """
        output = ""
        while True:
            ticket = self.session.query(models.Ticket).get(ticket_id)
            if not ticket.tid:
                ticket.tid = self.my_id()
                self.session.add(ticket)
                self.session.commit()
                continue

            if ticket.resource:
                return ticket.resource.output

            with self.sync.resource_ready:
                while self.sync.resource_ready.wait(timeout=10):
                    if self.sync.tid==self.my_id():
                        break

    @cached_session
    def closeTicket(self, ticket_id):
        ticket = self.session.query(models.Ticket).get(ticket_id)
        ticket.state = TState.CLOSED
        self.session.add(ticket)
        self.session.commit()
