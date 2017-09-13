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
from sqlalchemy.orm import sessionmaker
from resalloc.server.config import CONFIG
import threading

threadLocal = threading.local()

engine = create_engine(CONFIG['db_url'])
def EngineSingleton():
    return engine

# def EngineSingleton():
#     engine = getattr(threadLocal, 'engine', None)
#     if engine is None:
#         print("== Allocating engine ==")
#         threadLocal.engine = create_engine(CONFIG['db_url'])
#     return threadLocal.engine

def SessionFactory():
    session = sessionmaker()
    session.configure(bind=EngineSingleton())
    return session()
