"""
Python priority queue implementation.
"""

# TODO: rename "Task" to "Item" if we want to make this a library, we can
# place any kind of resource into the Queue (Pools, Tickets, etc.).
# TODO: enforce the PriorityQueueTask use.  Using the default __repr__ for
# generic objects might lead to misbehavior.

import itertools
from heapq import heappop, heappush

class PriorityQueue:
    """
    Priority "task" queue.  Taken from:
    https://docs.python.org/3/library/heapq.html#priority-queue-implementation-notes
    Later modified in Copr project.  The higher the 'priority' number is, the
    later the task is taken.
    """

    def __init__(self, removed='<removed-task>'):
        self.prio_queue = []             # list of entries arranged in a heap
        self.entry_finder = {}           # mapping of tasks to entries
        self.removed = removed           # placeholder for a removed task
        self.counter = itertools.count() # unique sequence count

    def add_task(self, task, priority=0):
        'Add a new task or update the priority of an existing task'
        if repr(task) in self.entry_finder:
            self.remove_task(task)
        count = next(self.counter)
        entry = [-priority, count, task]
        self.entry_finder[repr(task)] = entry
        # This works because heapq logic compares entries against each other,
        # and tuples are compared the "good way" (first item has the highest
        # priority, second lower, etc.).  So (1, 2) is lower than (1, 3) while
        # (3, 1) is higher than (2, 1000).  For this implementation, the higher
        # the given priority is, the sooner the task is taken, and if priority
        # is the same - the counter is always incremented (the later tasks have
        # lower priority).
        heappush(self.prio_queue, entry)

    def remove_task(self, task):
        'Mark an existing task as removed.  Raise KeyError if not found.'
        self.remove_task_by_id(repr(task))

    def remove_task_by_id(self, task_id):
        """
        Using task id, drop the task from queue.  Raise KeyError if not found.
        """
        entry = self.entry_finder.pop(task_id)
        entry[-1] = self.removed

    def pop_task(self):
        'Remove and return the lowest priority task. Raise KeyError if empty.'
        while self.prio_queue:
            _, _, task = heappop(self.prio_queue)
            if task is not self.removed:
                del self.entry_finder[repr(task)]
                return task
        raise KeyError('pop from an empty priority queue')


class PriorityQueueTask:
    """
    Objects of this task should be inserted into PriorityQueue
    """

    def __repr__(self):
        return str(self.object_id)

    @property
    def object_id(self):
        """
        An unique value for each item, needs to be easily converted to str().
        """
        raise NotImplementedError
