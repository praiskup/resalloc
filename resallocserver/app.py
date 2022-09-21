# Resalloc server application context.
# Copyright (C) 2021 Red Hat, Inc.
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

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from resallocserver.config import get_config
from resallocserver.log import get_logger

class AppContext:
    """
    Provide a singleton-like behavior for object attributes.  One needs to
    define instantiate_* methods.
    """
    def __init__(self):
        self._instantiated = {}

    # pylint: disable=missing-function-docstring
    def __getattr__(self, key):
        if key.startswith("instantiate_"):
            raise KeyError("Please define {} method in AppContext".format(key))
        setattr(self, key, getattr(self, "instantiate_{}".format(key))())
        self._instantiated[key] = True
        return getattr(self, key)

    @staticmethod
    def instantiate_config():
        return get_config()

    @staticmethod
    def instantiate_log():
        return get_logger("resallocserver")

    def instantiate_engine(self):
        return create_engine(self.config['db_url'])

    def instantiate_session(self):
        return scoped_session(sessionmaker(bind=self.engine))

    def reset(self):
        for key in list(self._instantiated.keys()):
            delattr(self, key)
            del self._instantiated[key]

app = AppContext()

@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = app.session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
