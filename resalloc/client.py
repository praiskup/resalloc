"""
Client resalloc Python API.
"""
from __future__ import print_function

import socket
import ssl
import time
import sys
import os

try:
    import xmlrpclib
    C_XMLRPC = xmlrpclib.ServerProxy
    RPCEXCEPTION = xmlrpclib.Error
except ImportError:
    # pylint: disable=invalid-name
    import xmlrpc.client
    C_XMLRPC = xmlrpc.client.ServerProxy
    RPCEXCEPTION = xmlrpc.client.Error


# Hardcoded on purpose now, load it from the config
CLIENT_KEY_FILE = '~/.config/resalloc-client-key'
SERVER_CERT_FILE = '~/.config/resalloc-server-cert'


def ssl_context():
    """
    Client SSL Context
    """
    server_cert = os.path.expanduser(SERVER_CERT_FILE)
    client_key = os.path.expanduser(CLIENT_KEY_FILE)

    try:
        tls_context = ssl.create_default_context(
            cafile=server_cert if os.path.exists(server_cert) else None)

        if os.path.exists(client_key):
            tls_context.load_cert_chain(client_key)
    except (ssl.SSLError, OSError) as err:
        # pylint: disable=raise-missing-from
        raise ResallocClientException(
            "Invalid client TLS configuration: {0}".format(err))

    return tls_context


class _WrappedXMLRPCClient(object):
    def __init__(self, connection_string, survive_server_restart):
        self._conn = C_XMLRPC(connection_string, context=ssl_context())
        self.survive_server_restart = survive_server_restart

    def call(self, name, *args):
        """
        Call the ``name`` xmlrpc method with ``*args``, and retry automatically
        if the ``survive_server_restart`` attribute is True.
        """
        fcall = getattr(self._conn, name)
        # we can not pass kwargs here, xmlrpc doesn't seem to support that
        while True:
            try:
                return fcall(*args)
            except ssl.SSLError as ssl_err:
                # pylint: disable=raise-missing-from
                raise ResallocClientException(
                    "TLS error while talking to the server: {0}".format(
                        ssl_err))
            except socket.error as sock_err:
                print(str(sock_err), file=sys.stderr)
                if not self.survive_server_restart:
                    raise
            except RPCEXCEPTION as ex:
                print(str(ex), file=sys.stderr)
            time.sleep(3)


class ResallocClientException(Exception):
    """
    Raised for invalid requests.
    """


class Ticket(object):
    """
    Resalloc Ticket representation.
    """
    id = None
    output = None
    closed = None
    ready = None
    failed = None

    def __init__(self, ticket_id, connection=None):
        # pylint: disable=invalid-name
        self.id = ticket_id
        self._connection = connection._connection

    def collect(self):
        """
        Return True if the ticket was assigned the resource (even though it is
        already closed).  Also put
        (a) the resource text (text given by allocator script) into ``output``
            attribute,
        (b) readiness status into ``ready`` atrribute, and
        (c) closed True if the ticket is already closed.
        """
        output = self._connection.call("collectTicket", self.id)
        self.closed = output['closed']
        self.output = output['output']
        self.ready = output['ready']
        self.failed = output["failed"]
        return bool(self.ready)

    def wait(self):
        """
        Actively wait server-side for the ticket to be resolved.  This returns
        immediately after server assigned the resource to this ticket (server
        process handling the request is woken up).
        """
        return str(self._connection.call("waitTicket", self.id))

    def close(self):
        """ Request the ticket close. """
        self._connection.call("closeTicket", self.id)


class Connection(object):
    """
    Resalloc Connection representation.
    """
    # pylint: disable=invalid-name

    def __init__(self, connection_string,
                 request_survives_server_restart=False):
        self._connection = _WrappedXMLRPCClient(connection_string,
                                                request_survives_server_restart)

    def newTicket(self, tags=None, sandbox=None):
        """ Take a new ticket for allocating specific resource """
        if tags is None:
            raise ResallocClientException("no tags specified")

        args = [tags]
        if sandbox:
            args.append(sandbox)

        ticket_id = self._connection.call("takeTicket", *args)
        return Ticket(connection=self, ticket_id=ticket_id)

    def getTicket(self, ticket_id):
        """ Get Ticket() object instantiated by ticket_id """
        return Ticket(connection=self, ticket_id=ticket_id)
