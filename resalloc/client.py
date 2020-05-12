"""
Client resalloc Python API.
"""

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

    def call(self, name, *args):
        """
        Call the ``name`` xmlrpc method with ``*args``, and retry automatically
        if the ``survive_server_restart`` attribute is True.
        """
        fcall = getattr(self._conn, name)
        # we can not pass kwargs here, xmlrpc doesn't seem to support that
        if not self.survive_server_restart:
            return fcall(*args)
        while True:
            try:
                return fcall(*args)
            except OSError as os_e:
                if os_e.errno != 101:
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

    def __init__(self, ticket_id, connection=None):
        # pylint: disable=invalid-name
        self.id = ticket_id
        self._connection = connection._connection

    def collect(self):
        """
        Return True if the ticket has already assigned resource, and store the
        output to ``output`` attribute.
        """
        output = self._connection.call("collectTicket", self.id)
        ready = output['ready']
        if ready:
            self.output = output['output']
        return ready

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
