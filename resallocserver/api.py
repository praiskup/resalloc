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

import sys
import time
from resallocserver import models
from resallocserver.app import session_scope
from resalloc.helpers import TState
import threading

threadLocal = threading.local()

class ServerAPIException(Exception):
    pass

class Ticket(object):
    id = None
    resource = None


class ServerAPI(object):
    def __init__(self, sync):
        self.sync = sync

    def my_id(self):
        return str(threading.current_thread())

    def takeTicket(self, tags=None, sandbox=None):
        with session_scope() as session:
            ticket = models.Ticket()
            ticket.sandbox = sandbox
            tag_objects = []
            for tag in (tags or []):
                to = models.TicketTag()
                to.ticket = ticket
                to.id = tag
                tag_objects.append(to)

            session.add_all([ticket] + tag_objects)
            session.flush()
            ticket_id = ticket.id

        self.sync.ticket.set()
        return ticket_id


    def collectTicket(self, ticket_id):
        output = {
            'ready': False,
            'output': None,
            'closed': None
        }
        with session_scope() as session:
            ticket = session.query(models.Ticket).get(ticket_id)
            if not ticket:
                output["ready"] = None
                return output

            if ticket.resource:
                output['output'] = ticket.resource.data
                output['ready'] = True
            output['closed'] = ticket.state == TState.CLOSED
        return output


    def waitTicket(self, ticket_id):
        """ ... blocking! ... """
        output = ""

        with session_scope() as session:
            ticket = session.query(models.Ticket).get(ticket_id)
            ticket.tid = self.my_id()
            session.add(ticket)

        while True:
            with session_scope() as session:
                ticket = session.query(models.Ticket).get(ticket_id)
                if ticket.resource:
                    return ticket.resource.data

            with self.sync.resource_ready:
                while self.sync.resource_ready.wait(timeout=10):
                    if self.sync.tid==self.my_id():
                        break


    def closeTicket(self, ticket_id):
        with session_scope() as session:
            ticket = session.query(models.Ticket).get(ticket_id)
            if not ticket:
                raise ServerAPIException("no such ticket {0}".format(ticket_id))
            ticket.state = TState.CLOSED
        self.sync.ticket.set()
