"""
Agent spawner daemon.  Part of the resalloc project.
"""

import base64
import sys
import logging
from copr_common.dispatcher import Dispatcher
from copr_common.worker_manager import WorkerManager, QueueTask
from copr_common.log import setup_script_logger
from copr_common.redis_helpers import get_redis_connection

from resalloc.client import (
    Connection as ResallocConnection,
)

from resalloc_agent_spawner.helpers import (
    get_config,
    CmdCallerMixin,
    rk_to_tid,
    tid_to_rk,
)

class Task(QueueTask):
    """ priority queue task handed ower to AgentWorkerManager """
    def __init__(self, task_id):
        self.task_id = task_id
    @property
    def id(self):
        return "agent_ticket_" + str(self.task_id)

class AgentWorkerManager(WorkerManager):
    """
    Start async worker in the background
    """

    worker_prefix = 'agent_backround_handler'

    def start_task(self, worker_id, task):
        self.start_daemon_on_background([
            "resalloc-agent-worker",
            '--daemon',
            '--ticket-id', str(task.task_id),
            '--worker-id', worker_id,
        ])

    def finish_task(self, worker_id, task_info):
        return True


class AgentSpawnerDispatcher(Dispatcher, CmdCallerMixin):
    """
    Track list of opened tickets from Resalloc (representing Agent-like
    resources).  Each Agent is in the following states:

    1. NEW -> ticket is taken, it is being allocated in the background
    2. PREPARING -> script is being run in the background to prepare the agent.
    3. WORKING -> up and running agent
    4. TERMINATING -> script is being run in the background to cleanup after the
       agent.
    5. ENDED -> ready for ticket close

    PREPARING and TERMINATING states are never changed by Dispatcher, but by
    BackgroundWorker.  If one background worker fails to switch the state, new
    one is started instead of it.
    """

    task_type = 'agent-manager'
    worker_manager_class = AgentWorkerManager

    def __init__(self, opts):
        super().__init__(opts)
        self.sleeptime = 10
        self.log = logging.getLogger()
        setup_script_logger(self.log, self.opts["logfile"])
        self.redis = get_redis_connection(opts)
        self.resalloc = ResallocConnection(
            opts["resalloc_server"],
           request_survives_server_restart=True,
        )

    def get_ticket_data(self, ticket_id):
        """ load resalloc ticket ID data """
        ticket = self.resalloc.getTicket(ticket_id)
        if not ticket.collect():
            # not yet resolved or failed
            return None

        # The ticket.output is bytes(), and we don't plan to touch the data at
        # all, we are just going to "forward" the data base64 encoded to our
        # hook scripts.  Encode it now, and never change again.
        return base64.b64encode(ticket.output.data).decode("ascii")

    def try_to_stop(self, group_id, to_stop):
        """
        Attempt to stop TO_STOP resources by closing Resalloc tickets.  Not all
        the resources may be closed at this time.
        """
        stopped = 0
        for ticket_id in self.get_tickets("WORKING"):
            if stopped >= to_stop:
                break

            data = self.get_ticket_data(ticket_id)
            if not data:
                continue  # failed resource, recovers in detect_failed_tickets()
            if not self.cmd_try_release(group_id, data):
                self.log.debug("Can't release %s", ticket_id)
                continue
            self.log.info("agent %s switches to TERMINATING (early)", ticket_id)
            self.set_ticket_attribute(ticket_id, "state", "TERMINATING")
            stopped += 1

    def get_tickets(self, states=None):
        """
        Get the list of ticket IDs currently stored in redis,
        optionally filtered by list of states.
        """
        keys = self.redis.keys(tid_to_rk("*"))
        output = []
        for key in keys:
            if states and self.redis.hget(key, 'state') not in states:
                continue
            output += [rk_to_tid(key)]
        return output

    def set_ticket_attribute(self, ticket_id, key, value):
        """
        For the ticket_id set redis hash key to value.
        """
        hash_id = tid_to_rk(ticket_id)
        self.redis.hset(hash_id, str(key), str(value))

    def get_ticket_attributes(self, ticket_id, keys):
        """
        Return list of redis hash values for the given ticket_id and
        list of keys.
        """
        hash_id = tid_to_rk(ticket_id)
        keys = [str(s) for s in keys]
        return self.redis.hmget(hash_id, keys)

    def agent_counts(self):
        """
        Get 'group_id → count' mapping
        """
        keys = self.redis.keys(tid_to_rk("*"))
        output = {}
        for key in keys:
            group_id = self.redis.hget(key, "group_id")
            self.log.debug("found worker for %s group id", group_id)
            output.setdefault(group_id, 0)
            output[group_id] += 1
        return output

    def agent_drop(self, ticket_id):
        """ drop agent per ticket id, cleanup everything """
        ticket = self.resalloc.getTicket(ticket_id)
        ticket.close()
        self.redis.delete(tid_to_rk(ticket_id))

    def clean_finished_workers(self):
        """
        WORKING — TERMINATING; Check for finalized agents, plan their cleanup
        """
        for ticket_id in self.get_tickets("WORKING"):
            (group_id,) = self.get_ticket_attributes(ticket_id, ["group_id"])
            data = self.get_ticket_data(ticket_id)
            if data is None:
                continue # failed resource, recovers in detect_failed_tickets()
            if not self.cmd_is_finished(group_id, data):
                continue
            self.log.info("Agent %s finished task, normal TERMINATING", ticket_id)
            self.set_ticket_attribute(ticket_id, "state", "TERMINATING")

    def start_preparing(self):
        """
        When the ticket is resolved in Resalloc, we have a working
        resource that we can prepare (in the background).  Switch the state.
        """
        for ticket_id in self.get_tickets("NEW"):
            data = self.get_ticket_data(ticket_id)
            if data is None:
                continue
            self.set_ticket_attribute(ticket_id, "data", data)
            self.set_ticket_attribute(ticket_id, "state", "PREPARING")

    def detect_failed_tickets(self):
        """
        Check for failed tickets, close them.  This rarely happens if everything
        is working smoothly.
        """

        for ticket_id in self.get_tickets():
            ticket = self.resalloc.getTicket(ticket_id)
            ticket.collect()
            if ticket.ready is None:
                # Non-existing ticket.  This really seems like the ticket
                # comes from some testing.
                key = tid_to_rk(ticket_id)
                self.log.fatal("Can't handle redis key %s, remove manually", key)
                sys.exit(1)

            if not ticket.failed:
                continue

            state, = self.get_ticket_attributes(ticket_id, ["state"])
            if state in ["PREPARING", "TERMINATING"]:
                # There's a background worker handling these agents.  We
                # need to let them finish.
                continue

            if state == "WORKING":
                # we still want to run the cmd_terminate hook
                self.set_ticket_attribute(ticket_id, "state", "TERMINATING")
                continue

            if state == "NEW":
                # this has never been prepared, simply close the ticket
                self.set_ticket_attribute(ticket_id, "state", "ENDED")


    def converge(self):
        """
        Go through all agent groups; check the ideal number of memgers and start
        new or try to terminate.
        """
        current_agents = self.agent_counts()
        for group_id, group in self.opts["agent_groups"].items():
            current = current_agents.get(group_id, 0)
            ideal = self.cmd_converge_to(group_id)
            if ideal is None:
                self.log.error("can't call converge to for group %s", group_id)
                continue

            if current < ideal:
                todo = ideal - current
                self.log.info("We want %s but have %s agents, starting %s new",
                              ideal, current, todo)
                for _ in range(todo):
                    # spawn as "NEW"
                    tags = group["tags"]
                    ticket = self.resalloc.newTicket(tags)
                    self.log.debug("Requesting new agent via ticket %s",
                                   ticket.id)
                    self.set_ticket_attribute(ticket.id, "group_id", group_id)
                    self.set_ticket_attribute(ticket.id, "state", "NEW")

            elif current > ideal:
                # WORKING — TERMINATING (even agents that did not start any task)
                self.try_to_stop(group_id, current - ideal)

    def get_frontend_tasks(self):
        """
        NEW → PREPARING → WORKING — TERMINATING — ENDED
        """

        # Cleanup after failed tickets
        self.detect_failed_tickets()

        # Drop successfully terminated agents
        for ticket_id in self.get_tickets("ENDED"):
            self.agent_drop(ticket_id)

        # WORKING — TERMINATING (normal)
        self.clean_finished_workers()

        # NEW → PREPARING
        self.start_preparing()

        # spawn NEW or try to switch WORKING → TERMINATING
        self.converge()

        # Return the priority queue to process by background workers.
        background_tasks = []
        for ticket_id in self.get_tickets(["PREPARING", "TERMINATING"]):
            background_tasks += [Task(ticket_id)]
        return background_tasks


def main():
    """ realloc-agent-spawner entrypoint """
    AgentSpawnerDispatcher(get_config()).run()


if __name__ == "__main__":
    main()
