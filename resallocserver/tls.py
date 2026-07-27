# TLS configuration of the resalloc xmlrpc server.
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

"""
TLS configuration of the resalloc xmlrpc server.
"""

import ssl

from resallocserver.app import app


class ServerTLS:
    """
    The TLS configuration of the xmlrpc server
    """

    def __init__(self, config):
        self.certfile = config.get("ssl_certfile")
        self.keyfile = config.get("ssl_keyfile")
        self.clients = config.get("ssl_clients")

        # build the TLS context here itself, any misconfiguration
        # would kill the entire process, not just the xmlrpc server
        self.context = self._build_tls_context() if self.enabled else None

    def _build_tls_context(self):
        """Build the TLS context from the configured certificates"""
        context = ssl.create_default_context(
            ssl.Purpose.CLIENT_AUTH, cafile=self.clients
        )
        if self.clients:
            context.verify_mode = ssl.CERT_REQUIRED
        context.load_cert_chain(certfile=self.certfile, keyfile=self.keyfile)
        return context

    @property
    def enabled(self):
        """True if the server is configured to speak TLS"""
        return bool(self.certfile)

    def build_tls_socket(self, sock):
        """
        Build the TLS socket, if TLS is correctly configured
        """
        if not self.enabled:
            if self.clients:
                app.log.warning(
                    "ssl_clients is set but ssl_certfile is not, SSL/TLS is disabled"
                )
            else:
                app.log.warning("SSL/TLS is not configured on the server")
            # returns plain socket, HTTP only
            return sock

        if not self.clients:
            app.log.warning("No SSL/TLS clients are configured")

        return self.context.wrap_socket(sock, server_side=True,
                                        do_handshake_on_connect=False)
