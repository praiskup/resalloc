"""
Tests for resallocserver/manager.py
"""

from resallocserver.manager import Manager
from resallocserver.main import Synchronizer

from tests import ResallocTestCase


class TestManager(ResallocTestCase):
    def test_something(self):
        sync = Synchronizer()
        #Manager(sync).run()
