#
# Copyright 2023 BredOS
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import atexit
import random
import string
import secrets
import tempfile
import subprocess
from pathlib import Path
from threading import Lock
from functools import wraps
from time import monotonic


def debounce(wait):
    """
    Decorator that will postpone a function's
    execution until after wait seconds
    have elapsed since the last time it was invoked.
    """

    def decorator(func):
        last_time_called = 0
        lock = Lock()

        @wraps(func)
        def debounced(*args, **kwargs):
            nonlocal last_time_called
            with lock:
                elapsed = monotonic() - last_time_called
                remaining = wait - elapsed
                if remaining <= 0:
                    last_time_called = monotonic()
                    return func(*args, **kwargs)
                else:
                    return None

        return debounced

    return decorator


def detect_device() -> str:
    """
    Detect the device model

    Parameters:
    - None

    Returns:
    - str: The device model
    """
    try:
        with open("/sys/firmware/devicetree/base/model", "r") as model_file:
            return model_file.read().rstrip("\n").rstrip("\x00")
    except FileNotFoundError:
        try:
            with open("/sys/class/dmi/id/product_name", "r") as product_name_file:
                return product_name_file.read().rstrip("\n")
        except FileNotFoundError:
            return "unknown"


def get_ram_size(unit: str = "KB") -> int:
    """
    Get the total RAM size in the system

    Parameters:
    - unit: The unit to return the RAM size in. Default is KB

    Returns:
    - int: The total RAM size in the system
    """
    try:
        with open("/proc/meminfo", "r") as meminfo:
            for line in meminfo:
                if line.startswith("MemTotal:"):
                    if unit == "KB":
                        return int(line.split()[1])
                    elif unit == "MB":
                        return int(line.split()[1]) / 1024
                    elif unit == "GB":
                        return int(line.split()[1]) / 1024 / 1024
                    elif unit == "bytes":
                        return int(line.split()[1]) * 1024
    except FileNotFoundError:
        return 0
    return 0


def elevated_file_write(filepath: str, content: str):
    proc = subprocess.run(
        ["pkexec", "tee", filepath], input=content.encode(), check=True
    )


def wrap_lines(lines: list, width: int) -> list:
    return [wrapped for line in lines for wrapped in textwrap.wrap(line, width)]


def match_filename(cut_filename: str, full_filenames: list) -> str | None:
    cut_lower = cut_filename.lower()
    matches = [
        path
        for path in full_filenames
        if os.path.basename(path).lower().startswith(cut_lower)
    ]
    return matches[0] if len(matches) == 1 else None


class Elevator:
    def __init__(self):
        self.proc = None
        self.secret = secrets.token_hex(32)
        self.script_path = None

    @property
    def spawned(self) -> bool:
        return self.proc != None

    def _make_server_script(self):
        rand = "".join(random.choices(string.ascii_letters + string.digits, k=8))
        self.script_path = Path(tempfile.gettempdir()) / f"elevator.{rand}.py"
        code = f"""#!/usr/bin/env python3
import os
import sys
import time
import signal
import subprocess

PARENT_PID = os.getppid()

def parent_is_alive() -> bool:
    try:
        os.kill(PARENT_PID, 0)
        return True
    except ProcessLookupError:
        return False

# Background watcher
import threading
def watchdog() -> None:
    while True:
        if not parent_is_alive():
            sys.exit(0)
        time.sleep(1)

threading.Thread(target=watchdog, daemon=True).start()

try:
    os.unlink(__file__)
except Exception as e:
    pass

AUTHED = False
SECRET = {repr(self.secret)}

def readline():
    line = sys.stdin.readline()
    if not line:
        sys.exit(0)
    return line.strip()

while True:
    try:
        line = readline()
        if not AUTHED:
            if line == SECRET:
                AUTHED = True
                print("[[AUTH_OK]]")
                sys.stdout.flush()
            else:
                print("[[AUTH_FAIL]]")
                sys.stdout.flush()
                sys.exit(1)
            continue

        result = subprocess.run(line, shell=True, capture_output=True, text=True)
        print(result.stdout, end='')
        print(result.stderr, end='', file=sys.stderr)
        print("[[EOC]]")
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception as e:
        print(f"ERR: {{e}}", file=sys.stderr)
        print("[[EOC]]", file=sys.stderr)
        sys.stderr.flush()
"""
        self.script_path.write_text(code)
        self.script_path.chmod(0o600)

    def _spawn(self):
        self._make_server_script()
        self.proc = subprocess.Popen(
            ["pkexec", "python3", str(self.script_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        # Send auth key
        self.proc.stdin.write(self.secret + "\n")
        self.proc.stdin.flush()
        response = self.proc.stdout.readline().strip()
        if response != "[[AUTH_OK]]":
            self.script_path.unlink()
            self.proc = None  # Cycle keys for security
            self.secret = secrets.token_hex(32)
            self.script_path = None
            raise RuntimeError("Failed to authenticate with root elevator.")

    def run(self, cmd: str) -> str:
        if self.proc is None or self.proc.poll() is not None:
            self._spawn()

        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()

        output = []
        for line in self.proc.stdout:
            if line.strip() == "[[EOC]]":
                break
            output.append(line)
        return "".join(output)
