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

from resalloc.helpers import RState, TState
from resallocserver import models
from sqlalchemy.orm import Query
from sqlalchemy import or_


class QObject(object):
    def __init__(self, session=None, pool=None):
        if session:
            self.query = self.query.with_session(session)
        if pool:
            self.query = self.query.filter_by(pool=pool)

class QResources(QObject):
    query = Query(models.Resource)

    def up(self):
        return self.query.filter_by(state=RState.UP)

    def on(self):
        return self.query.filter(models.Resource.state != RState.ENDED)

    def ready(self):
        return (self.up()
                    .outerjoin(models.Ticket)
                    .filter(models.Ticket.id == None))

    def taken(self):
        return (self.up()
                    .outerjoin(models.Ticket)
                    .filter(models.Ticket.id != None))

    def starting(self):
        return self.query.filter_by(state=RState.STARTING)

    def stats(self):
        items = {}
        items['on']     = self.on().outerjoin(models.Ticket).all()
        items['up']     = [x for x in items['on'] if x.state  == RState.UP]
        items['ready']  = [x for x in items['up'] if x.ticket == None]
        items['taken']  = [x for x in items['up'] if x.ticket != None]
        items['start']  = [x for x in items['on'] if x.state  == RState.STARTING]
        items['term']   = [x for x in items['on'] if x.state  == RState.DELETING]
        return {key: len(value) for (key, value) in items.items()}

    def clean_candidates(self):
        return self.on().filter(models.Resource.state != RState.DELETING)\
                        .outerjoin(models.Ticket)\
                        .filter(or_(
                            models.Ticket.state == TState.CLOSED,
                        ))

    def clean(self):
        return self.on().filter_by(state=RState.DELETE_REQUEST)


class QTickets(QObject):
    query = Query(models.Ticket)

    def new(self):
        return self.query.filter_by(resource_id=None)
