# Resalloc server configuration management.
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
from resalloc.helpers import merge_dict, load_config_file


def get_config():
    """
    Get the resalloc-server configuration dict
    """

    config_dir = "/etc/resallocserver"
    if 'CONFIG_DIR' in os.environ:
        config_dir = os.environ['CONFIG_DIR']

    # Setup defaults.
    config = {
        'db_url': 'sqlite:////var/lib/resalloc-server/db.sqlite',
        'logdir': '/var/log/resallocserver',
        # Bind the xmlrpc server to this hostname/port.
        'hostname': 'localhost',
        'port': 49100,
        'loglevel': 'info',
        # Maximum number of seconds Manager threads wait in loop.  Used for tests
        # only ATM.  Watcher sleeps sleeptime/2.
        'sleeptime': 20,
    }
    config["config_dir"] = config_dir

    config_file = os.path.join(config_dir, 'server.yaml')
    return merge_dict(config, load_config_file(config_file))
