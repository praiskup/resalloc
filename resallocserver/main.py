# Resalloc server main() method (and friends).
# Copyright (C) 2017-2021 Red Hat, Inc.
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

from __future__ import absolute_import

import os
import time
import threading

from resalloc import helpers
from resallocserver import models, api
from resallocserver.app import app, session_scope
from resallocserver.manager import Manager
from resallocserver.logic import QResources
import alembic.config

PORT = 8000
CLSXMLRPC = None

try:
    import SimpleXMLRPCServer
    import SocketServer
    class wrap(SocketServer.ThreadingMixIn, SimpleXMLRPCServer.SimpleXMLRPCServer):
        pass
    CLSXMLRPC = wrap
except:
    import xmlrpc.server
    import socketserver
    class wrap(socketserver.ThreadingMixIn, xmlrpc.server.SimpleXMLRPCServer):
        pass
    CLSXMLRPC = wrap


class AtomicEvent(object):
    """
    Similar to threading.Event(), though there's no need to clear() the event
    explicitly.  The clear() method is "called" automatically and atomically, in
    pretty short critical section when no other thread can set() the event.
    This way, it is guaranteed that no set() call will be missed by manager
    between explicit wait() and clear().

    We could actually use plain threading.Condition instead, but to not loose
    any of the notify() actions, the whole time-period of manager's loop would
    have to be in critical section (too long).
    """
    event = threading.Event()
    cond = threading.Condition()

    def set(self):
        with self.cond:
            self.event.set()
            self.cond.notify()

    def wait(self, timeout=None):
        with self.cond:
            if not self.event.is_set():
                # Unlock && wait.
                self.cond.wait(timeout=timeout)
                # Locked again, so unlock and continue ...

            # even if we are woken up by other thread's set(), clear the event
            # since it was set too by that set() method (to avoid additional
            # spin).
            self.event.clear()


class Synchronizer(object):
    ticket = AtomicEvent()
    resource_ready = threading.Condition()
    resource_tid = None


class Server(threading.Thread):
    server = None

    def run(self):
        config = app.config
        # prefer "hostname" over "host", and fallback to "localhost"
        hostname = config.get("hostname") or config.get("host") or "localhost"
        self.server = CLSXMLRPC((hostname, config['port']))
        self.server.allow_none = True
        self.server.daemon_threads = True
        self.server.register_introspection_functions()
        self.server.register_instance(api.ServerAPI(self.sync))
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def init_by_alembic():
    app.log.info("Initializing database")
    alembic_dir = os.path.dirname(__file__)
    with helpers.pushd(alembic_dir):
        alembicArgs = [
        '--raiseerr',
        'upgrade', 'head',
        ]
        alembic.config.main(argv=alembicArgs)


def init_by_models():
    with session_scope() as session:
        models.Base.metadata.create_all(session.get_bind())


def main():
    """ module entrypoint """
    # Create the database, if not exist yet.
    init_by_alembic()

    # Synchronization tool.
    sync = Synchronizer()

    # Delete leftovers from previous session, we need to run everything
    # asynchronously, see https://github.com/praiskup/resalloc/issues/41
    with session_scope() as session:
        QResources(session=session).fix_broken_after_restart(app.log)

    # Start server on background.
    server = Server()
    server.sync = sync
    server.start()

    try:
        Manager(sync).run()
    except KeyboardInterrupt:
        app.log.info("Stopping upon a KeyboardInterrupt")
    except:
        app.log.exception("Exception raised in Manager().run()")
        raise
    finally:
        server.shutdown()
