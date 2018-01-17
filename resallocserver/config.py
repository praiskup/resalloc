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
import yaml
from resalloc.helpers import merge_dict, load_config_file

config_dir = "/etc/resallocserver"
if 'CONFIG_DIR' in os.environ:
    config_dir = os.environ['CONFIG_DIR']

# Setup defaults.
CONFIG = {
    'db_url': 'sqlite:////var/lib/resalloc-server/db.sqlite',
    'logdir': '/var/log/resallocserver',
    # Bind the xmlrpc server to this hostname/port.
    'host': 'localhost',
    'port': 49100,
    'loglevel': 'info',
}

CONFIG_DIR = config_dir

config_file = os.path.join(config_dir, 'server.yaml')
CONFIG = merge_dict(CONFIG, load_config_file(config_file))
