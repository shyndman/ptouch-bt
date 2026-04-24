import errno
import fcntl
import os
import select
import subprocess
import termios
import time
import tty
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectionConfig:
    address: str = "BC:31:98:A0:59:EE"
    channel: int = 1
    device: str = "/dev/rfcomm0"


def rfcomm_name(device):
    name = os.path.basename(device)
    if not name.startswith("rfcomm"):
        raise ValueError(f"expected an rfcomm device path, got {device}")
    return name


def run_rfcomm(args):
    command = ["rfcomm", *args]
    if os.geteuid() != 0:
        command[:0] = ["sudo", "-n"]
    return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def release_rfcomm(device):
    run_rfcomm(["release", rfcomm_name(device)])


def is_rfcomm_connected(device):
    result = run_rfcomm(["show", rfcomm_name(device)])
    output = f"{result.stdout}\n{result.stderr}".lower()
    return result.returncode == 0 and "connected" in output


def rfcomm_command(args):
    command = ["rfcomm", *args]
    if os.geteuid() != 0:
        command[:0] = ["sudo", "-n"]
    return command


def start_rfcomm(config):
    if is_rfcomm_connected(config.device):
        return None

    release_rfcomm(config.device)

    process = subprocess.Popen(
        rfcomm_command(["connect", rfcomm_name(config.device), config.address, str(config.channel)]),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            message = process.stderr.read().strip()
            if "password is required" in message.lower():
                message = "sudo credential needed; run `sudo -v` and retry"
            raise RuntimeError(f"failed to connect {config.device}: {message}")

        if os.path.exists(config.device) and os.access(config.device, os.R_OK | os.W_OK) and is_rfcomm_connected(config.device):
            return process

        time.sleep(0.1)

    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
    raise RuntimeError(f"timed out connecting {config.device} to {config.address} channel {config.channel}")


def stop_rfcomm(process):
    if process is None or process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()


def open_rfcomm(device):
    deadline = time.monotonic() + 5
    while True:
        try:
            fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)
            return fd
        except OSError as error:
            if error.errno not in {errno.ENODEV, errno.ENXIO, errno.EIO, errno.ENOENT, errno.EACCES}:
                raise
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


def drain(fd):
    while True:
        ready, _, _ = select.select([fd], [], [], 0.05)
        if not ready:
            return
        os.read(fd, 4096)


def read_exact(fd, length, timeout):
    deadline = time.monotonic() + timeout
    chunks = []
    remaining = length

    while remaining > 0:
        wait = deadline - time.monotonic()
        if wait <= 0:
            break

        ready, _, _ = select.select([fd], [], [], wait)
        if not ready:
            break

        chunk = os.read(fd, remaining)
        if not chunk:
            break

        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)


def write_all(fd, data):
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        view = view[written:]


@contextmanager
def ptouch_connection(config):
    connection = start_rfcomm(config)
    fd = None
    old_attrs = None
    try:
        fd = open_rfcomm(config.device)
        old_attrs = termios.tcgetattr(fd)
        tty.setraw(fd)
        yield fd
    finally:
        if fd is not None:
            if old_attrs is not None:
                termios.tcsetattr(fd, termios.TCSANOW, old_attrs)
            os.close(fd)
        stop_rfcomm(connection)
