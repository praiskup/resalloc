# Helpers DB logic, built on top of models.
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
import uuid

from resalloc.helpers import RState, TState
from resallocserver import models
from sqlalchemy.orm import Query
from sqlalchemy import or_


def assign_ticket(resource, ticket):
    resource.ticket_id = ticket.id
    ticket.resource_id = resource.id

    if not ticket.sandbox:
        # generate random sandbox
        ticket.sandbox = str(uuid.uuid1())

    if not resource.sandbox:
        resource.sandbox = ticket.sandbox
        resource.sandboxed_since = time.time()

    return resource.sandbox == ticket.sandbox


def release_resource(ticket):
    resource = ticket.resource
    resource.ticket_id = None
    resource.released_at = time.time()
    resource.releases_counter += 1


class QObject(object):
    session = None

    def __init__(self, session=None, pool=None):
        if session:
            self.query = self.query.with_session(session)
            self.session = session
        if pool:
            self.query = self.query.filter_by(pool=pool)

class QResources(QObject):
    query = Query(models.Resource)

    def up(self):
        return self.query.filter_by(state=RState.UP)

    def on(self):
        return self.query.filter(models.Resource.state != RState.ENDED)

    def ready(self):
        """
        Get ready resources, those which were never assigned or are released.
        The sandbox-assigned resources are sorted above others - so they can be
        re-used first.
        """
        return (self.up().filter(models.Resource.ticket_id.is_(None))
                         .filter(models.Resource.check_failed_count==0))

    def taken(self):
        """
        Get the list of all _taken_ resources == those that have OPEN ticket
        assigned.
        """
        return (self.up()
                    .filter(models.Resource.ticket_id.isnot(None)))

    def starting(self):
        return self.query.filter_by(state=RState.STARTING)

    def fix_broken_after_restart(self, log):
        """
        Since we execute everything asynchronous by threads, restart of resalloc
        server leads to killing the async threads.
        """
        query = self.query.filter(models.Resource.state.in_([
            RState.STARTING,
            RState.DELETING,
            RState.RELEASING,
        ]))
        for resource in query:
            log.warning("Resource %s in inconsistent state %s => %s",
                        resource.name, resource.state, RState.DELETE_REQUEST)
            resource.state = RState.DELETE_REQUEST

    def stats(self):
        items = {}
        items['on']     = self.on().all()
        items['up']     = [x for x in items['on'] if x.state  == RState.UP]
        # Resources that can be assigned.
        items['ready']  = [x for x in items['up'] if x.ticket_id is None]
        # Opposite for "ready".
        items['taken']  = [x for x in items['up'] if x.ticket_id is not None]
        items['start']  = [x for x in items['on'] if x.state  == RState.STARTING]
        items['term']   = [x for x in items['on'] if x.state  == RState.DELETING]
        # Ready, but already released resources that we can only assign to
        # a ticket from the same sandbox it was assigned before.
        items['released'] = [x for x in items['ready'] if x.releases_counter > 0]
        # Ready resources that have not been assigned to any ticket/sandbox yet.
        items['free'] = [x for x in items['ready'] if x.releases_counter <= 0]
        items['releasing'] = [x for x in items['on'] if x.state == RState.RELEASING]
        return {key: len(value) for (key, value) in items.items()}

    def clean_candidates(self):
        return (
            self.up()
            # isn't it still used?
            .filter(models.Resource.ticket_id.is_(None))
            # was this actually ever used?
            .filter(models.Resource.released_at.isnot(None))
        )

    def check_failure_candidates(self):
        """
        List of resources that are UP, and have non-zero check_failed_count.
        """
        return (
            self.up()
            # isn't it still used?
            .filter(models.Resource.ticket_id.is_(None))
            .filter(models.Resource.check_failed_count > 0)
        )

    def clean(self):
        return self.on().filter_by(state=RState.DELETE_REQUEST)

    def kill(self, res_id):
        # Only open tickets assigned to by resource, if any.
        ticket_update = self.session.query(models.Ticket)\
                                    .filter_by(resource_id=res_id)\
                                    .filter_by(state=TState.OPEN)\
                                    .update({'state': TState.FAILED})

        # Killing only UP resources, for now.  It might have sense to terminate
        # STARTING, but this is not yet solved.
        self.query.filter_by(id=res_id)\
                  .filter_by(state=RState.UP)\
                  .update({'state': RState.DELETE_REQUEST})


class QTickets(QObject):
    query = Query(models.Ticket)

    def waiting(self):
        return self.query.filter_by(resource_id=None)\
                         .filter_by(state=TState.OPEN)

    def not_closed(self):
        return self.query.filter(models.Ticket.state != TState.CLOSED)
