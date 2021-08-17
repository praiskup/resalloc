"""
Tests for resallocserver/manager.py
"""

# pylint: disable=protected-access

import random

import pytest

from resalloc.helpers import TState
from resallocserver import models
from resallocserver.app import session_scope
from resallocserver.main import Synchronizer
from resallocserver.manager import Manager

from tests import ResallocTestCase


class TestManager(ResallocTestCase):

    @pytest.mark.parametrize(
        "passengers, expected_car", [
        (["mother"], "car3"),
        (["father"], "car2"),
        (["son"], "car1"),
        (["mother", "father"], "car3"),
        (["daughter"], "car2"),
    ])
    def test_resource_tag_priority(self, passengers, expected_car):
        self.prepare_database({
            "resources": {
                "car1": {
                    "data": b"red",
                    "tags": {
                        "mother": {"priority": 1},
                        "father": {"priority": 2},
                        "son": {"priority": 3},
                    },
                },
                "car2": {
                    "data": b"green",
                    "tags": {
                        "mother": {"priority": 1},
                        "father": {"priority": 3},
                        "daughter": {"priority": 2},
                    },
                },
                "car3": {
                    "data": b"blue",
                    "tags": {
                        "mother": {"priority": 3},
                        "father": {"priority": 2},
                        "daughter": {},
                    },
                },
            },
        })

        with session_scope() as session:
            ticket = models.Ticket(
                state=TState.OPEN,
                sandbox=str(random.random()),
            )
            session.add(ticket)
            for tag in passengers:
                print(tag)
                tag = models.TicketTag(
                    ticket=ticket,
                    id=tag,
                )
                session.add(tag)

        sync = Synchronizer()
        manager = Manager(sync)
        manager._assign_tickets()

        with session_scope() as session:
            ticket = session.query(models.Ticket).get(1)
            assert ticket.resource.name == expected_car
