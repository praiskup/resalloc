"""
Tests for yield_lines_from_fds()
"""

import os
import subprocess
import time

import pytest

from resallocserver.helpers import yield_lines_from_fds, LineBufferOverflow


def _pipe_with_data(data):
    """Create a pipe, write data to it, close the write end, return read fd."""
    r, w = os.pipe()
    os.write(w, data)
    os.close(w)
    return r


class TestYieldLinesFromFds:

    def test_single_line(self):
        fd = _pipe_with_data(b"hello\n")
        result = list(yield_lines_from_fds([fd]))
        assert result == [(fd, b"hello\n")]

    def test_multiple_lines(self):
        fd = _pipe_with_data(b"one\ntwo\nthree\n")
        result = list(yield_lines_from_fds([fd]))
        assert result == [
            (fd, b"one\n"),
            (fd, b"two\n"),
            (fd, b"three\n"),
        ]

    def test_partial_line_at_eof(self):
        fd = _pipe_with_data(b"no newline")
        result = list(yield_lines_from_fds([fd]))
        assert result == [(fd, b"no newline")]

    def test_partial_line_after_complete_lines(self):
        fd = _pipe_with_data(b"first\nsecond")
        result = list(yield_lines_from_fds([fd]))
        assert result == [
            (fd, b"first\n"),
            (fd, b"second"),
        ]

    def test_empty_input(self):
        fd = _pipe_with_data(b"")
        result = list(yield_lines_from_fds([fd]))
        assert not result

    def test_empty_lines(self):
        fd = _pipe_with_data(b"\n\n\n")
        result = list(yield_lines_from_fds([fd]))
        assert result == [
            (fd, b"\n"),
            (fd, b"\n"),
            (fd, b"\n"),
        ]

    def test_multiple_fds(self):
        fd1 = _pipe_with_data(b"from-fd1\n")
        fd2 = _pipe_with_data(b"from-fd2\n")
        result = list(yield_lines_from_fds([fd1, fd2]))
        assert set(result) == {
            (fd1, b"from-fd1\n"),
            (fd2, b"from-fd2\n"),
        }

    def test_timeout_on_read(self):
        r, w = os.pipe()
        try:
            with pytest.raises(TimeoutError, match="on read"):
                list(yield_lines_from_fds([r], timeout=0.1))
        finally:
            os.close(r)
            os.close(w)

    def test_timeout_deadline_expired(self):
        r, w = os.pipe()
        os.write(w, b"line\n")
        try:
            with pytest.raises(TimeoutError, match="timeouted after"):
                for _ in yield_lines_from_fds([r], timeout=0.01):
                    time.sleep(0.05)
        finally:
            os.close(r)
            os.close(w)

    def test_max_line_length_ok(self):
        fd = _pipe_with_data(b"short\n")
        result = list(yield_lines_from_fds([fd], max_line_length=1000))
        assert result == [(fd, b"short\n")]

    def test_max_line_length_exceeded(self):
        fd = _pipe_with_data(b"a" * 300 + b"\n")
        with pytest.raises(LineBufferOverflow, match="exceeded 200 bytes"):
            list(yield_lines_from_fds([fd], max_line_length=200))

    def test_max_line_length_exact_boundary(self):
        fd = _pipe_with_data(b"a" * 199 + b"\n")
        result = list(yield_lines_from_fds([fd], max_line_length=200))
        assert len(result) == 1

    def test_max_line_length_no_newline(self):
        fd = _pipe_with_data(b"a" * 300)
        with pytest.raises(LineBufferOverflow, match="exceeded 200 bytes"):
            list(yield_lines_from_fds([fd], max_line_length=200))

    def test_max_line_length_short_lines_pass(self):
        fd = _pipe_with_data(b"ok\n" * 100)
        result = list(yield_lines_from_fds([fd], max_line_length=10))
        assert len(result) == 100

    def test_large_line_across_chunks(self):
        """Line larger than 4096 read buffer works when no limit set."""
        fd = _pipe_with_data(b"x" * 10000 + b"\n")
        result = list(yield_lines_from_fds([fd]))
        assert result == [(fd, b"x" * 10000 + b"\n")]

    def test_binary_data(self):
        data = bytes(range(256)).replace(b"\n", b"\x00") + b"\n"
        fd = _pipe_with_data(data)
        result = list(yield_lines_from_fds([fd]))
        assert len(result) == 1
        assert result[0][1] == data

    def test_two_fds_lines_not_mixed(self):
        """Lines from two fds are attributed correctly, not interleaved."""
        fd1 = _pipe_with_data(b"aaa\nbbb\nccc\n")
        fd2 = _pipe_with_data(b"111\n222\n333\n")
        result = list(yield_lines_from_fds([fd1, fd2]))
        fd1_lines = [line for fd, line in result if fd == fd1]
        fd2_lines = [line for fd, line in result if fd == fd2]
        assert fd1_lines == [b"aaa\n", b"bbb\n", b"ccc\n"]
        assert fd2_lines == [b"111\n", b"222\n", b"333\n"]

    def test_interleaved_stdout_stderr(self):
        """Subprocess alternates stdout/stderr writes; lines stay attributed."""
        script = (
            "import sys\n"
            "for i in range(5):\n"
            "    out = sys.stdout if i % 2 == 0 else sys.stderr\n"
            "    out.write(f'{out.name}:{i}\\n')\n"
            "    out.flush()\n"
        )
        with subprocess.Popen(
            ["python3", "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as sp:
            stdout_fd = sp.stdout.fileno()
            stderr_fd = sp.stderr.fileno()
            result = list(yield_lines_from_fds([stdout_fd, stderr_fd]))

        stdout_lines = [line for fd, line in result if fd == stdout_fd]
        stderr_lines = [line for fd, line in result if fd == stderr_fd]
        assert stdout_lines == [b"<stdout>:0\n", b"<stdout>:2\n", b"<stdout>:4\n"]
        assert stderr_lines == [b"<stderr>:1\n", b"<stderr>:3\n"]
