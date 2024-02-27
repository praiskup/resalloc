"""
Handle certain tasks by a background daemon process.
"""

import base64

from copr_common.background_worker import BackgroundWorker

from resalloc_agent_spawner.helpers import (
    get_config,
    CmdCallerMixin,
    tid_to_rk,
)

class AgentHandler(BackgroundWorker, CmdCallerMixin):
    """ Start daemon process per given task from AgentWorkerManager """

    def __init__(self):
        super().__init__()
        self.opts = get_config()

    @classmethod
    def adjust_arg_parser(cls, parser):
        parser.add_argument(
            "--ticket-id",
            type=int,
            required=True,
            help="ticket ID to handle",
        )

    def handle_ticket(self, ticket_id):
        """
        Import a single task
        """
        redis_key = tid_to_rk(ticket_id)

        # We know there's self._redis initialized by parent class so we don't
        # create yet another connection.
        redis_dict = self._redis.hgetall(redis_key)
        ticket_data = base64.b64encode(redis_dict["data"])

        if redis_dict["state"] == "PREPARING":
            if self.cmd_take(redis_dict["group_id"], ticket_data):
                self._redis.hset(redis_key, "state", "WORKING")
            else:
                # failed preparation -> prepare removal
                self._redis.hset(redis_key, "state", "ENDED")
            return

        if redis_dict["state"] == "TERMINATING":
            self.cmd_terminate(redis_dict["group_id"], ticket_data)
            self._redis.hset(redis_key, "state", "ENDED")

    def handle_task(self):
        try:
            self.handle_ticket(self.args.ticket_id)
        finally:
            self.redis_set_worker_flag("status", "done")


def main():
    """ realloc-agent-worker entrypoint """
    worker = AgentHandler()
    worker.process()


if __name__ == "__main__":
    main()
