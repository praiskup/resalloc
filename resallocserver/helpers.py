"""
Helper utilities for the resalloc server.
"""

import os
import select
import time


class LineBufferOverflow(Exception):
    """Raised when a line exceeds the maximum allowed length."""


def yield_lines_from_fds(fds, timeout=None, max_line_length=None):
    """
    Generator that reads lines from file descriptors, yielding (fd, line) pairs.
    Raises TimeoutError when the deadline is exceeded.
    Raises LineBufferOverflow when a line exceeds max_line_length.
    """
    timeout = timeout or 60 * 60 * 24
    deadline = time.monotonic() + timeout
    buffers = {fd: b"" for fd in fds}
    active_fds = set(fds)

    while active_fds:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"timeouted after {timeout}s")

        ready, _, _ = select.select(list(active_fds), [], [], remaining)
        if not ready:
            raise TimeoutError(f"timeouted after {timeout}s (on read)")

        for fd in ready:
            if max_line_length:
                capacity = max_line_length - len(buffers[fd])
                if capacity <= 0:
                    raise LineBufferOverflow(
                        f"line on fd {fd} exceeded {max_line_length} bytes")
                chunk = os.read(fd, min(4096, capacity))
            else:
                chunk = os.read(fd, 4096)

            if chunk:
                buffers[fd] += chunk
                while b'\n' in buffers[fd]:
                    line, buffers[fd] = buffers[fd].split(b'\n', 1)
                    yield (fd, line + b'\n')
                continue

            # EOF
            if buffers[fd]:
                yield (fd, buffers[fd])
            active_fds.discard(fd)
