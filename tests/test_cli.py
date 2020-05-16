""" test for resalloc.client """

import pytest

from resalloc.client import Connection
from tests import mock

@mock.patch("resalloc.client.time.sleep")
def test_errno_reconnect(p_sleep):
    """ Test that "request_survives_server_restart" tries to reconnect. """
    conn = Connection(
        "http://localhost:654245",
        request_survives_server_restart=True)

    class _side_effect:
        def __init__(self, conn):
            self.conn = conn
            self.called = 0
        def __call__(self, _sleep_time):
            print("called")
            if self.called > 0:
                conn._connection.survive_server_restart = False
            self.called += 1

    p_sleep.side_effect = _side_effect(conn)
    with pytest.raises(Exception):
        ticket = conn.newTicket(tags=["test"])
    assert p_sleep.call_args_list == [mock.call(3), mock.call(3)]
