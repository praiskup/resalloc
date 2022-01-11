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

import os
import subprocess
import sys
import json
from sqlalchemy.orm import Query

from resalloc.helpers import RState
from resallocserver.logic import QResources, QTickets
from resallocserver.models import Resource
from resallocserver.app import app, session_scope
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

    def resource_info(self, resource):
        with session_scope() as session:
            query = Query(Resource)
            query = query.with_session(session)
            if resource.isnumeric():
                query = query.filter(Resource.id == resource)
            else:
                query = query.filter(Resource.name == resource)
            resource = query.one()
            print(json.dumps(resource.to_dict(), indent=4))

    def resource_delete(self, resources=None):
        if not resources or type(resources) != list:
            log.error("no resources specified")
            return

        for res_id in resources:
            with session_scope() as session:
                resources = QResources(session=session)
                resources.kill(res_id)

    def resource_logs(self, resources=None):
        hooks_dir = os.path.join(app.config["logdir"], "hooks")
        paths = []
        for resource in resources:
            # If the resource was specified by its name instead of its ID
            if not resource.isnumeric():
                with session_scope() as session:
                    query = Query(Resource)
                    query = query.with_session(session)
                    query = query.filter(Resource.name == resource)
                    resource = query.one().id

            # We can't wildcard everything because then `tail' wouldn't
            # discover newly created log files
            suffixes = ["_alloc", "_watch", "_terminate"]
            path = os.path.join(hooks_dir, str(resource).zfill(6))
            paths.extend([path + suffix for suffix in suffixes])

        cmd = ["tail", "-F", "-n+0"] + paths
        subprocess.call(cmd)

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
                    utf_data = ""
                    if resource.data:
                        utf_data = resource.data.decode("utf8")
                    command = args.command.format(
                        name=resource.name,
                        state=resource.state,
                        data_utf8=utf_data,
                    )
                except KeyError as err:
                    sys.stderr.write(str(err))

                subprocess.call(command, shell=True)
