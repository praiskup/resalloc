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

from resalloc.helpers import RState
from resallocserver.logic import QResources
from resallocserver.models import Resource
from resallocserver.db import session_scope
from resallocserver.log import get_logger

log = get_logger

class Maintainer(object):
    def resource_list(self):
        with session_scope() as session:
            resources = QResources(session)
            for resource in resources.on().all():
                msg = "{id} - {name} pool={pool} tags={tags}"
                tags = ','.join(list(resource.tag_set))
                print(msg.format(
                    id=resource.id,
                    name=resource.name,
                    pool=resource.pool,
                    tags=tags
                ))

    def resource_delete(self, resources=None):
        if not resources:
            log.error("no resources specified")
            return

        for res_id in resources:
            with session_scope() as session:
                resources = QResources(session=session)
                resources.kill(res_id)
