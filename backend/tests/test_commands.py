import os
import time

import pytest

from tools import commands
from tools.commands import MAX_LOG_CHARS, run_command

posix_only = pytest.mark.skipif(os.name != "posix", reason="uses sh and process groups")


def script(tmp_path, body: str):
    path = tmp_path / "run.sh"
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return str(path)


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A killed child not yet reaped by init still answers; its state says.
    try:
        with open(f"/proc/{pid}/stat") as stat:
            return stat.read().split()[2] != "Z"
    except FileNotFoundError:
        return False


@posix_only
def test_passing_command_keeps_its_output(tmp_path):
    result = run_command(tmp_path, [script(tmp_path, "echo out\necho err >&2\n")])
    assert result.ok
    assert "out" in result.log and "err" in result.log


@posix_only
def test_failing_command_is_not_ok(tmp_path):
    result = run_command(tmp_path, [script(tmp_path, "echo broke\nexit 3\n")])
    assert not result.ok
    assert "broke" in result.log


@posix_only
def test_timeout_stops_everything_the_command_started(tmp_path):
    # Like yarn starting Playwright: the command starts a child that would
    # outlive it, records the child's pid, then waits.
    pid_file = tmp_path / "child.pid"
    body = f"sleep 60 &\necho $! > {pid_file}\necho started the tests\nwait\n"
    began = time.monotonic()
    result = run_command(tmp_path, [script(tmp_path, body)], timeout=1)
    assert time.monotonic() - began < 10
    assert not result.ok
    child = int(pid_file.read_text())
    deadline = time.monotonic() + 5
    while alive(child) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not alive(child)


@posix_only
def test_timeout_keeps_what_was_printed_and_says_so_last(tmp_path):
    result = run_command(tmp_path, [script(tmp_path, "echo half way\nsleep 60\n")], timeout=1)
    assert "half way" in result.log
    assert result.log.endswith("timed out after 1s")


@posix_only
def test_long_timeout_log_is_trimmed_but_keeps_the_note(tmp_path):
    body = "i=0\nwhile [ $i -lt 2000 ]; do echo line $i; i=$((i+1)); done\nsleep 60\n"
    result = run_command(tmp_path, [script(tmp_path, body)], timeout=2)
    assert len(result.log) <= MAX_LOG_CHARS
    assert result.log.endswith("timed out after 2s")


@posix_only
def test_secrets_are_not_passed_to_the_command(tmp_path, monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "secret-token")
    result = run_command(
        tmp_path, [script(tmp_path, 'echo "token=$VERCEL_TOKEN port=$PORT"\n')], env={"PORT": "5"}
    )
    assert "token= port=5" in result.log


def test_missing_program_is_named(tmp_path):
    with pytest.raises(FileNotFoundError, match="no-such-tool"):
        run_command(tmp_path, ["no-such-tool"])


def test_stop_all_falls_back_when_the_group_is_gone(monkeypatch):
    killed = []

    class Process:
        pid = 123

        def kill(self):
            killed.append(True)

    def gone(pid, sig):
        raise ProcessLookupError

    monkeypatch.setattr(commands.os, "killpg", gone, raising=False)
    commands._stop_all(Process())
    assert killed == [True]
