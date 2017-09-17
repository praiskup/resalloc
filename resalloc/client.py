import xmlrpclib

class ResallocClientException(Exception):
    pass

class Ticket(object):
    id = None
    connection = None

    def __init__(self, connection=None):
        self.connection = connection

    def check(self):
        return self.connection.checkTicket(self.id)


class Connection(object):
    connection = None

    def __init__(self, conn):
        self.connection = xmlrpclib.ServerProxy(conn)

    def newTicket(self, tags=None):
        if tags == None:
            raise ResallocClientException("no tags specified")

        t = Ticket(connection=connection)
        t.id = self.connection.takeTicket(tags)
        return t

    def getTicket(self, ticket_id):
        t = Ticket(connection=connection)
        t.id = ticket_id
