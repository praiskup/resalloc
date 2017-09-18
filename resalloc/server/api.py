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
from resalloc.server import db, models
from resalloc.server.db import session_scope
from resalloc.helpers import TState, dump_trhead_id
import threading

threadLocal = threading.local()

class ServerAPIException(Exception):
    pass

class Ticket(object):
    id = None
    resource = None

def dump_thread_decorator(function):
    def wrap(*args, **kwargs):
        dump_trhead_id()
        sys.stderr.write('{0}\n'.format(function))
        return function(*args, **kwargs)
    return wrap


class ServerAPI(object):
    def __init__(self, sync):
        self.sync = sync

    def my_id(self):
        return str(threading.current_thread())

    @dump_thread_decorator
    def takeTicket(self, tags=None):
        with session_scope() as session:
            ticket = models.Ticket()
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


    def _checkTicket(self, ticket_id, session):
        ticket = session.query(models.Ticket).get(ticket_id)
        if not ticket:
            raise ServerAPIException("no such ticket")
        return ticket.resource

    @dump_thread_decorator
    def collectTicket(self, ticket_id):
        output = {
            'ready': False,
            'output': None,
        }
        with session_scope() as session:
            resource = self._checkTicket(ticket_id, session)
            if resource:
                output['output'] = resource.data
                output['ready'] = True
        return output


    @dump_thread_decorator
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

    @dump_thread_decorator
    def closeTicket(self, ticket_id):
        with session_scope() as session:
            ticket = session.query(models.Ticket).get(ticket_id)
            ticket.state = TState.CLOSED
            self.sync.ticket.set()
