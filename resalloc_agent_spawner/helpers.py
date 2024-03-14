"""
resalloc agent spawner helpers
"""

import os
import subprocess

from resalloc.helpers import load_config_file


def rk_to_tid(key):
    """ Redis agent key to Resalloc Ticket ID """
    return int(key.split(":")[1])


def tid_to_rk(ticket):
    """ Resalloc Ticket ID to Redis Agent key """
    return f"agent:{ticket}"


def get_config():
    """
    Load the agent-spawner YAML configuration
    """
    conf_dir = os.environ.get("CONFIG_DIR", "/etc/resalloc-agent-spawner")
    config_file = os.path.join(conf_dir, "config.yaml")
    config = load_config_file(config_file)
    config.setdefault("agent_groups", {})
    config.setdefault("resalloc_server", "http://localhost:49100")
    config.setdefault("logfile", "/tmp/agent-spawner.log")
    config.setdefault("redis_db", "")
    config.setdefault("redis_host", "127.0.0.1")
    config.setdefault("redis_port", "6379")
    config.setdefault("redis_password", "")
    groups = config["agent_groups"]
    for group_id in groups.keys():
        group = groups[group_id]
        group.setdefault("cmd_converge_to", "/usr/bin/echo 1")
        group.setdefault("cmd_check_finished", "/bin/false")
        group.setdefault("cmd_prepare", "/bin/true")
        group.setdefault("cmd_terminate", "/bin/true")
        group.setdefault("cmd_try_release", "/bin/false")
        group.setdefault("tags", ["please-specify-some-tags"])
    return config


class CmdCallerMixin:
    """
    Wrapper around calling command hooks.
    """

    def _cmd(self, group_id, cmd_id):
        return self.opts["agent_groups"][group_id][cmd_id]

    def cmd_converge_to(self, group_id):
        """
        Query the outside world for the ideal number of agents in given group.
        """
        result = subprocess.run(
            self._cmd(group_id, "cmd_converge_to"),
            stdout=subprocess.PIPE, check=False, shell=True)
        if result.returncode == 0:
            try:
                return int(result.stdout.decode("utf-8").strip())
            except ValueError:
                self.log.error("Converge-to hook failure, expected int, "
                               "got: %s", result.stdout)
                return None

        self.log.debug("Failing to run converge-to hook")
        return None

    def cmd_try_release(self, group_id, data):
        """
        Call hook that releases the resource
        """
        cmd = self._cmd(group_id, "cmd_try_release")
        result = subprocess.run(cmd, check=False, **self.subproces_kwargs(data))
        return not result.returncode

    def cmd_is_finished(self, group_id, data):
        """
        Call hook that releases the resource
        """
        result = subprocess.run(
            self._cmd(group_id, "cmd_check_finished"),
            check=False, **self.subproces_kwargs(data))
        return not result.returncode

    def cmd_take(self, group_id, data):
        """
        Initialize the agent
        """
        return not subprocess.run(
            self._cmd(group_id, "cmd_prepare"), check=False,
            **self.subproces_kwargs(data),
        ).returncode

    def cmd_terminate(self, group_id, data):
        """
        Prepare the agent for removal.
        """
        subprocess.run(
            self._cmd(group_id, "cmd_terminate"),
            check=False,
            **self.subproces_kwargs(data),
        )

    def subproces_kwargs(self, data):
        """
        generate "generic" subprocess.Popen kwargs
        """
        return {
            "env": {
                "AGENT_SPAWNER_RESOURCE_DATA": str(data),
            },
            "shell": True,
        }
