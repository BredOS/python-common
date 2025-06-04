import os
import re
import shlex
import hashlib
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

dts_cache = {}
DTB_PATH = Path("/boot/dtbs")
PROC_DT = Path("/proc/device-tree")


def force_quote(val: int | str) -> str:
    if isinstance(val, int):
        return str(val)
    return "'" + str(val).replace("'", "'\"'\"'") + "'"


def parse_uboot() -> dict:
    config = {"U_BOOT_IS_SETUP": "false", "U_BOOT_PARAMETERS": "splash quiet"}
    try:
        with open("/etc/default/u-boot") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    try:
                        val = shlex.split(val, posix=True)
                        val = val[0] if len(val) == 1 else val
                        if isinstance(val, list):
                            for i in range(len(val)):
                                if val[i].isdigit():
                                    try:
                                        val[i] = int(val[i])
                                    except:
                                        pass
                        elif isinstance(val, str):
                            if val.isdigit():
                                try:
                                    val = int(val)
                                except:
                                    pass
                        config[key] = val
                    except ValueError:
                        config[key] = val.strip()
    except:
        pass
    return config


def encode_uboot(config: dict) -> str:
    lines = [
        "## /etc/default/u-boot - configuration file",
    ]
    for key, val in config.items():
        if isinstance(val, list):
            # Join multi-word values if they were stored as list
            val_str = " ".join(val)
        else:
            val_str = val

        quoted_val = force_quote(val_str)
        lines.append(f"{key}={quoted_val}")
    return "\n".join(lines)


def parse_grub() -> dict:
    config = {}
    with open("/etc/default/grub") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                try:
                    val = shlex.split(val, posix=True)
                    val = val[0] if len(val) == 1 else val
                    if isinstance(val, list):
                        for i in range(len(val)):
                            if val[i].isdigit():
                                try:
                                    val[i] = int(val[i])
                                except:
                                    pass
                    elif isinstance(val, str):
                        if val.isdigit():
                            try:
                                val = int(val)
                            except:
                                pass
                    config[key] = val
                except ValueError:
                    config[key] = val.strip()
    return config


def encode_grub(config: dict) -> str:
    lines = [
        "## /etc/default/grub - configuration file",
    ]
    for key, val in config.items():
        if isinstance(val, list):
            # Join multi-word values if they were stored as list
            val_str = " ".join(val)
        else:
            val_str = val

        quoted_val = force_quote(val_str)
        lines.append(f"{key}={quoted_val}")
    return "\n".join(lines)


def parse_extlinux_conf(source) -> dict:
    if hasattr(source, "read"):
        lines = source.read().splitlines()
    else:
        lines = source.splitlines()

    config = {"global": {}, "labels": {}}

    current_label = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.lower().startswith("label "):
            current_label = line[6:].strip()
            config["labels"][current_label] = {}
            continue

        key_value = line.split(None, 1)
        if len(key_value) == 2:
            key, value = key_value
            key = key.lower()
            value = value.strip()

            if key == "fdtoverlays":
                value = value.split()

            if current_label:
                config["labels"][current_label][key] = value
            else:
                config["global"][key] = value
        else:
            key = key_value[0].lower()
            if current_label:
                config["labels"][current_label][key] = None
            else:
                config["global"][key] = None

    return config


def serialize_extlinux_conf(config: dict) -> str:
    lines = []

    for key, value in config.get("global", {}).items():
        if value is None:
            lines.append(key.upper())
        else:
            lines.append(f"{key.upper()} {value}")

    if lines:
        lines.append("")

    for label, directives in config.get("labels", {}).items():
        lines.append(f"LABEL {label}")
        for key, value in directives.items():
            if value is None:
                lines.append(f"    {key.upper()}")
            elif key == "fdtoverlays" and isinstance(value, list):
                joined = " ".join(value)
                lines.append(f"    {key.upper()} {joined}")
            else:
                lines.append(f"    {key.upper()} {value}")
        lines.append("")

    return "\n".join(lines).rstrip()


def gencache() -> dict:
    res = {"base": {}, "overlays": {}}
    try:
        dtb_root = Path("/boot/dtbs")

        base_files = list(dtb_root.rglob("*.dtb"))
        overlay_files = list(dtb_root.rglob("*.dtbo"))

        with ThreadPoolExecutor() as executor:
            future_to_path_base = {
                executor.submit(extract_dtb_info, path): path for path in base_files
            }
            future_to_path_overlay = {
                executor.submit(extract_dtb_info, path): path for path in overlay_files
            }

            for future in as_completed(future_to_path_base):
                path = future_to_path_base[future]
                result = future.result()
                if result:
                    res["base"][str(path)] = result

            for future in as_completed(future_to_path_overlay):
                path = future_to_path_overlay[future]
                result = future.result()
                if result:
                    res["overlays"][str(path)] = result
    except KeyboardInterrupt:
        pass
    except:
        pass
    return res


def detect_live() -> tuple:
    live_dts = fdt_hash_from_proc()
    if live_dts is None:
        return None, "Could not read live FDT"

    live_dts_str = live_dts.decode()
    live_hash = hash_str(live_dts_str)
    candidates = list(DTB_PATH.rglob("*.dtb"))

    best_match = None
    best_dts = None
    overlay_diff = []
    min_diff = float("inf")

    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(dt_process_candidate, dtb, live_hash): dtb
            for dtb in candidates
        }

        for future in as_completed(futures):
            result = future.result()
            if result is None:
                continue
            dtb_relpath, candidate_hash, candidate_dts = result
            if candidate_hash == live_hash:
                return dtb_relpath, []
            else:
                diff_len = len(diff_dts(candidate_dts, live_dts_str))
                if diff_len < min_diff:
                    min_diff = diff_len
                    best_match = dtb_relpath
                    best_dts = candidate_dts

    if best_dts:
        overlay_diff = diff_dts(best_dts, live_dts_str)
        return best_match, overlay_diff

    return None, "No match found"


def identify_base_dtb() -> tuple | None:
    live_dts = fdt_hash_from_proc()
    if live_dts is None:
        return None, "Failed to read live FDT"

    live_hash = hash_str(live_dts.decode())

    candidates = list(DTB_PATH.rglob("*.dtb"))
    matches = []
    for dtb in candidates:
        dts = dtb_to_dts(dtb)
        if dts is None:
            continue
        if hash_str(dts) == live_hash:
            matches.append(dtb.relative_to(DTB_PATH))

    if matches:
        return matches[0], None
    else:
        return None, "No exact match found (overlays likely applied)"


# FIXME: Use /proc/mounts instead
def detect_efidir() -> str | None:
    try:
        df_output = subprocess.check_output(["df"], text=True)
    except subprocess.CalledProcessError:
        return None

    boot_mounts = set()
    for line in df_output.splitlines()[1:]:  # Skip header
        parts = line.split()
        if len(parts) < 6:
            continue
        mount_point = parts[5]
        if mount_point.startswith("/boot"):
            boot_mounts.add(mount_point)

    if "/boot/efi" in boot_mounts:
        return "/boot/efi"
    elif "/boot" in boot_mounts:
        return "/boot"
    else:
        return None


def identify_overlays() -> list:
    res = []
    if booted_with_edk():
        efi = detect_efidir()
        if efi is None:
            raise OSError("Failed to identify EFI Directory")

        overlays_path = Path(efi) / "dtb" / "overlays"
        if not overlays_path.exists() or not overlays_path.is_dir():
            return res  # No overlays directory found

        try:
            for dtbo in overlays_path.rglob("*.dtbo"):
                # Sanity check: only real files, not broken symlinks, etc.
                if dtbo.is_file() and not dtbo.is_symlink():
                    dtbof = str(dtbo.resolve(strict=True))
                    dtbof = dtbof[dtbof.rfind("/") + 1 :]
                    res.append(dtbof)
        except:
            pass
    elif extlinux_exists():
        extcfg = dt.parse_extlinux_conf(
            Path("/boot/extlinux/extlinux.conf").read_text()
        )
        if "fdtoverlays" in extlinux:
            res += extcfg["fdtoverlays"]
    return res


def uefi_overriden() -> bool:
    for path in ("/boot/efi/dtb/base/", "/boot/dtb/base/"):
        try:
            if os.path.isdir(path):
                with os.scandir(path) as entries:
                    if any(entry.is_file() for entry in entries):
                        return True
        except:
            continue
    return False


def diff_dts(base_dts, live_dts) -> list:
    base_lines = set(base_dts.splitlines())
    live_lines = set(live_dts.splitlines())
    return list(live_lines - base_lines)


def dt_process_candidate(dtb_path, live_hash) -> tuple | None:
    dts = dtb_to_dts(dtb_path)
    if dts is None:
        return None
    h = hash_str(dts)
    return (dtb_path.relative_to(DTB_PATH), h, dts)


def safe_exists(path: str) -> bool:
    try:
        real_path = os.path.realpath(path)

        boot_path = os.path.dirname(path)
        if not os.path.isdir(boot_path):
            return False

        return os.path.isfile(real_path)
    except Exception:
        return False


def grub_exists() -> bool:
    return safe_exists("/boot/grub/grub.cfg")


def extlinux_exists() -> bool:
    return safe_exists("/boot/extlinux/extlinux.conf")


def booted_with_edk() -> bool:
    try:
        output = subprocess.check_output(["journalctl", "-b"], text=True)
        lines = output.splitlines()[:20]
        pattern = re.compile(r"efi: EFI v[\d.]+ by .+", re.IGNORECASE)
        return any(pattern.search(line) for line in lines)
    except subprocess.CalledProcessError:
        return False


def extract_dtb_info(dtb_path: Path) -> dict | None:
    output = dtb_to_dts(dtb_path)

    description = None
    compatible = []

    for line in output.splitlines():
        line = line.strip()
        if line.startswith("description =") and description is not None:
            description = line.split("=", 1)[1].strip().strip('"').strip(";")
        elif line.startswith("compatible =") and not compatible:
            compat_str = line.split("=", 1)[1].strip().strip(";")
            compatible = [compat_str.strip().strip('"')]

    name = str(dtb_path)
    name = name[name.rfind("/") + 1 : name.rfind(".")]

    return {
        "name": name,
        "description": description,
        "compatible": compatible,
    }


def dtb_to_dts(dtb_path) -> str | None:
    global dts_cache
    if dtb_path in dts_cache:
        return dts_cache[dtb_path]
    try:
        res = subprocess.check_output(
            ["dtc", "-I", "dtb", "-O", "dts", "-q", str(dtb_path)],
            stderr=subprocess.DEVNULL,
        ).decode()

        dts_cache[dtb_path] = res
        return res
    except subprocess.CalledProcessError:
        return None


def fdt_hash_from_proc() -> str | None:
    try:
        return subprocess.check_output(
            ["dtc", "-I", "fs", "-O", "dts", "/proc/device-tree"],
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


def hash_str(data):
    return hashlib.sha256(data.encode()).hexdigest()
