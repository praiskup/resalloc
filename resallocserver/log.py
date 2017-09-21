# Resalloc server's logging configuration.
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


import logging
from resallocserver.config import CONFIG

def get_logger(loggername):
    log = logging.getLogger(loggername)
    loglevel = logging.getLevelName(CONFIG['loglevel'].upper())
    logfile = CONFIG['main_logfile']
    log.setLevel(loglevel)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main_file = logging.FileHandler(logfile)
    main_file.setLevel(loglevel)
    main_file.setFormatter(file_formatter)
    log.addHandler(main_file)
    stderr = logging.StreamHandler()
    log.addHandler(stderr)
    return log
