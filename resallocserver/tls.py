"""
TLS configuration of the resalloc xmlrpc server.
"""

import ssl
from pathlib import Path

from resallocserver.app import app


class ServerTLS:
    """
    The TLS configuration of the xmlrpc server
    """

    def __init__(self, config):
        self.certfile = config.get("ssl_certfile")
        self.keyfile = config.get("ssl_keyfile")
        clients_dir = config.get("ssl_clients")
        self.clients = (
            self._read_client_certs(Path(clients_dir)) if clients_dir else None
        )
        if clients_dir and not self.certfile:
            raise ValueError(
                "ssl_clients is set but ssl_certfile is not, SSL/TLS is disabled"
            )

        # build the TLS context here itself, any misconfiguration
        # would kill the entire process, not just the xmlrpc server
        self.context = self._build_tls_context() if self.enabled else None

    def _read_client_certs(self, clients_dir: Path):
        """Concatenate clients pem files"""
        certificates = [
            path.read_text(encoding="ascii")
            for path in sorted(clients_dir.glob("*.pem"))
            if path.is_file()
        ]
        if not certificates:
            raise ValueError("No client certificates found")
        return "\n".join(certificates)

    def _build_tls_context(self):
        """Build the TLS context from the configured certificates"""
        context = ssl.create_default_context(
            ssl.Purpose.CLIENT_AUTH, cadata=self.clients
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
            app.log.warning("SSL/TLS is not configured on the server")
            # returns plain socket, HTTP only
            return sock

        if not self.clients:
            app.log.warning("No SSL/TLS clients are configured")

        return self.context.wrap_socket(sock, server_side=True,
                                        do_handshake_on_connect=False)
