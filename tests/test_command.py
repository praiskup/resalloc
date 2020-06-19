""" Tests for run_command() in manager.py """

import os
import subprocess
import tempfile

from tests import mock

# pylint: disable=missing-function-docstring, missing-class-docstring, attribute-defined-outside-init

class TestRunCommand:
    def setup_method(self, method):
        _unused = method
        self.workdir = tempfile.mkdtemp(prefix="resalloc-tests-")
        self.configdir = os.path.join(self.workdir, "config")
        os.mkdir(self.configdir)
        self.logdir = os.path.join(self.workdir, "logs")
        os.mkdir(self.logdir)
        self.server_config_file = os.path.join(self.configdir, "server.yaml")
        with open(self.server_config_file, "w") as filed:
            filed.write("""
logdir: {logdir}
""".format(logdir=self.logdir))

        self.patchers = []

        self.patchers.append(mock.patch.dict(
            os.environ,
            {"CONFIG_DIR": self.configdir},
        ))
        self.patchers[-1].start()

    def teardown_method(self, method):
        _unused = method
        for patcher in self.patchers:
            patcher.stop()

    def test_trim(self):
        """
        Test that we correctly trim the long-running command stdout.
        """
        _unused = self

        # We have ugly side-effects in config file handling.
        # pylint: disable=import-outside-toplevel
        from resallocserver.manager import run_command

        capture_bytes = 100
        command = (
            # print to stdout, and at the end write something to stderr
            "bash -c 'for i in $(seq 100000); do echo stdout; done; "
            "echo stderr >&2'"
        )
        res = run_command("pool_trim", 10, "res_10", 1, command, ltype='alloc',
                          catch_stdout_bytes=capture_bytes)
        assert res["status"] == 0
        assert res["stdout"].endswith(b"<< trimmed >>\n")
        assert res["stdout"].startswith(b"stdout\n")
        assert len(res["stdout"]) >= capture_bytes

        logfile = os.path.join(self.logdir, "hooks", "000010_alloc")
        subprocess.check_call(["grep", "stderr", logfile])
        log_count_cmd = "wc -l < {}".format(logfile)
        assert subprocess.check_output(log_count_cmd, shell=True) == b'100001\n'
