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
        
def get_ram_size(unit: str = 'KB') -> int:
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
                    if unit == 'KB':
                        return int(line.split()[1])
                    elif unit == 'MB':
                        return int(line.split()[1]) / 1024
                    elif unit == 'GB':
                        return int(line.split()[1]) / 1024 / 1024
                    elif unit == 'bytes':
                        return int(line.split()[1]) * 1024
    except FileNotFoundError:
        return 0
    return 0

