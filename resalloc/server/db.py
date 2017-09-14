# DB connection abstraction for resalloc server.
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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from resalloc.server.config import CONFIG
import threading

threadLocal = threading.local()

engine = create_engine(CONFIG['db_url'])
def EngineSingleton():
    return engine

session = sessionmaker(bind=EngineSingleton())
Session = scoped_session(session)

def SessionFactory():
    return Session()
