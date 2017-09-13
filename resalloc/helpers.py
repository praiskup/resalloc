# Helpers to be used by client/server part of resalloc project.
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

class StateSetException(Exception):
    def __init__(self, message):
        self.message = message

class StateSetMeta(type):
    def __getattr__(self, name):
        if name in self.values:
            return name
        values = ', '.join(map(lambda x: "'" + x + "'", self.values))
        msg = "invalid value '{0}' for StateSet({1})".format(name, values)
        raise StateSetException(msg)

    def __getitem__(self, name):
        return self.__getattr__(name)

StateSet = StateSetMeta(str('StateSet'), (), {
    '__doc__': 'Set of states',
    })
