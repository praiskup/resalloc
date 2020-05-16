"""
Client resalloc Python API.
"""

import errno
import socket
import time

try:
    import xmlrpclib
    C_XMLRPC = xmlrpclib.ServerProxy
except ImportError:
    # pylint: disable=invalid-name
    import xmlrpc.client
    C_XMLRPC = xmlrpc.client.ServerProxy


class _WrappedXMLRPCClient(object):
    def __init__(self, connection_string, survive_server_restart):
        self._conn = C_XMLRPC(connection_string)
        self.survive_server_restart = survive_server_restart
        self._retry_errors = [
            errno.ECONNREFUSED,
            errno.ECONNABORTED,
            errno.ECONNRESET,
            errno.ENETUNREACH,
            errno.ENETRESET,
            errno.ENETDOWN,
        ]

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
            except socket.error as os_e:
                if not self.survive_server_restart:
                    raise
                if os_e.errno not in self._retry_errors:
                    raise
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
