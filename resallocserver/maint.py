# Maintainer actions.
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

import subprocess
import sys

from resalloc.helpers import RState
from resallocserver.logic import QResources, QTickets
from resallocserver.models import Resource
from resallocserver.db import session_scope
from resallocserver.log import get_logger

log = get_logger(__name__)

class Maintainer(object):
    def resource_list(self, up=None):
        with session_scope() as session:
            resources = QResources(session)
            if up:
                resources = resources.up()
            else:
                resources = resources.on()

            for resource in resources.all():
                msg = ("{id} - {name} pool={pool} tags={tags} status={status} "
                       "releases={releases} ticket={ticket}")
                tags = ','.join(list(resource.tag_set))
                print(msg.format(
                    id=resource.id,
                    name=resource.name,
                    pool=resource.pool,
                    tags=tags,
                    status=resource.state,
                    releases=resource.releases_counter,
                    ticket=resource.ticket.id if resource.ticket else 'NULL',
                ))

    def resource_delete(self, resources=None):
        if not resources or type(resources) != list:
            log.error("no resources specified")
            return

        for res_id in resources:
            with session_scope() as session:
                resources = QResources(session=session)
                resources.kill(res_id)

    def ticket_list(self):
        with session_scope() as session:
            tq = QTickets(session)
            for ticket in tq.not_closed().all():
                output = ''
                ticket_line = '{id} - state={state} tags={tags}'
                tags = ','.join(list(ticket.tag_set))
                output = ticket_line.format(
                    id=ticket.id,
                    state=ticket.state,
                    tags=tags,
                )

                if ticket.resource:
                    output += ' resource=' + ticket.resource.name

                print (output)

    def foreach_resource(self, args):
        """ Execute shell command for each resource """
        command = args.command
        with session_scope() as session:
            resources = QResources(session)
            for resource in resources.on().all():
                try:
                    command = args.command.format(
                        name=resource.name,
                        state=resource.state,
                        data_utf8=resource.data.decode("utf8"),
                    )
                except KeyError as err:
                    sys.stderr.write(str(err))

                subprocess.call(command, shell=True)
