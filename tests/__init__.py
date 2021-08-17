"""
Resalloc test-suite.
"""

import os
import shutil
import tempfile

import six

from resalloc.helpers import RState
from resallocserver.app import app, session_scope
from resallocserver.main import init_by_alembic
from resallocserver import models

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock


class ResallocTestCase:
    """
    Basic test class.  Prepares the testing environment.
    """

    workdir = None

    def setup_method(self, method):
        """ Executed before each test-case """
        _unused = method
        self.workdir = tempfile.mkdtemp(prefix="/tmp/resalloc-tests-")
        app.reset()

        confdir = os.path.join(self.workdir, "etc")
        os.environ["CONFIG_DIR"] = confdir
        os.makedirs(confdir)
        pools_file = os.path.join(confdir, "pools.yaml")
        server_file = os.path.join(confdir, "server.yaml")

        database_file = os.path.join(self.workdir, "sqlite.db")
        db_url = 'sqlite:///' + database_file
        log_dir = os.path.join(self.workdir, "logs")
        os.makedirs(log_dir)

        with open(server_file, 'w') as sfd:
            sfd.write(os.linesep.join([
                "db_url: {db_url}",
                "loglevel: debug",
                "logdir: {log_dir}",
                "#hostname: localhost",
                "#port: 49100",
            ]).format(
                db_url=db_url,
                log_dir=log_dir,
            ) + os.linesep)

        init_by_alembic()

        for file in [pools_file, server_file]:
            open(file, mode='a'). close()

    def teardown_method(self, method):
        """ Executed after each test-case """
        _unused = method
        shutil.rmtree(self.workdir)
        app.reset()

    @staticmethod
    def _prepare_database(data, session):
        if "pools" in data:
            for pool_name, _ in data["pools"].items():
                pool = models.Pool(
                    name=pool_name,
                )
                session.add(pool)

        if "resources" in data:
            for resource_name, res_data in data["resources"].items():
                res = models.Resource(
                    name=resource_name,
                    data=res_data.get("data", u"unset"),
                    state=res_data.get("state", RState.UP),
                    pool=res_data.get("pool", "orphan"),
                )
                session.add(res)

                for tag_name, tag_data in res_data.get("tags", {}).items():
                    tag = models.ResourceTag(
                        id=tag_name,
                        resource=res,
                    )
                    priority = tag_data.get("priority")
                    if priority is not None:
                        tag.priority = priority
                    session.add(tag)


    def prepare_database(self, data):
        """
        Using the DATA dictionary pre-populate the database.
        """
        with session_scope() as session:
            self._prepare_database(data, session)
