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

class ServerAPI(object):
    def __init__(self, event):
        self.event = event


    def takeTicket(self, tags=None):
        session = db.Session()
        ticket = models.Ticket()
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
        self.event.set()
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
        ticket_id = self.takeTicket(tags)
        output = ""
        while True:
            output = self.checkTicket(ticket_id)
            if output:
                break
            time.sleep(5)

        return output
