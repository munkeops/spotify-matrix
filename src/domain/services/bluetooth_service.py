"""Bluetooth device management via the BlueZ bluetoothctl CLI.

This drives the Pi's Bluetooth stack; on hosts without bluetoothctl (for
example a developer laptop) every call degrades gracefully to "unavailable"
instead of raising, so the UI can still render.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any

from loguru import logger

_DEVICE_LINE = re.compile(r"^Device\s+([0-9A-Fa-f:]{17})\s+(.*)$")
_MAC = re.compile(r"^[0-9A-Fa-f:]{17}$")

# BlueZ's Icon tells you what a device is, which is what lets the UI separate a
# controller from a speaker from the pile of nameless things a scan turns up.
_ROLE_BY_ICON = {
    "audio-card": "audio",
    "audio-headset": "audio",
    "audio-headphones": "audio",
    "audio-speaker": "audio",
    "input-gaming": "controller",
    "input-gamepad": "controller",
    "input-joystick": "controller",
    "input-keyboard": "input",
    "input-mouse": "input",
    "input-tablet": "input",
    "phone": "phone",
    "computer": "computer",
    "video-display": "display",
}

#: Names that give a device away when BlueZ has not worked out an icon yet.
_ROLE_BY_NAME = (
    ("controller", ("xbox", "dualshock", "dualsense", "wireless controller", "8bitdo", "gamepad", "joy-con", "stadia")),
    ("audio", ("speaker", "soundbar", "headphone", "headset", "buds", "airpods", "jbl", "bose", "sony wh", "echo", "soundcore", "anker", "boom", "flip", "charge")),
)


def ertm_disabled() -> bool | None:
    """Whether Bluetooth ERTM is off. None when the setting is not visible.

    Xbox Wireless Controllers will not stay connected on Linux with ERTM on,
    which is the single most common reason an Xbox pad refuses to pair.
    """
    from pathlib import Path as _Path

    node = _Path("/sys/module/bluetooth/parameters/disable_ertm")
    try:
        return node.read_text(encoding="utf-8").strip().upper() in ("Y", "1")
    except OSError:
        return None


ERTM_HELP = (
    "Xbox controllers need Bluetooth ERTM disabled on Linux or they will not stay connected. "
    "Run: echo 'options bluetooth disable_ertm=1' | sudo tee /etc/modprobe.d/bluetooth.conf "
    "then reboot. To try it now without rebooting: "
    "echo 1 | sudo tee /sys/module/bluetooth/parameters/disable_ertm"
)


def classify(icon: str, name: str) -> str:
    """Best guess at what a device is, for grouping the scan results."""
    role = _ROLE_BY_ICON.get((icon or "").strip().lower())
    if role:
        return role
    lowered = (name or "").lower()
    for candidate, needles in _ROLE_BY_NAME:
        if any(needle in lowered for needle in needles):
            return candidate
    return "other"


class BluetoothService:
    def _binary(self) -> str | None:
        return shutil.which("bluetoothctl")

    def available(self) -> bool:
        return self._binary() is not None

    def _run(self, args: list[str], timeout: float = 20.0) -> tuple[bool, str]:
        binary = self._binary()
        if binary is None:
            return False, "Bluetooth is not available on this device."
        try:
            result = subprocess.run([binary, *args], capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            return False, "bluetoothctl not found."
        except subprocess.TimeoutExpired:
            return False, f"bluetoothctl {' '.join(args)} timed out."
        except OSError as error:
            return False, str(error)
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode == 0, output.strip()

    def _safe_mac(self, mac: str) -> str:
        candidate = (mac or "").strip().upper()
        if not _MAC.match(candidate):
            raise ValueError("Invalid Bluetooth address.")
        return candidate

    def blocked(self) -> bool:
        """True when rfkill has Bluetooth soft or hard blocked.

        Read from sysfs rather than the rfkill binary, so this works on a bare
        install and inside a container without the tool present.
        """
        from pathlib import Path

        root = Path("/sys/class/rfkill")
        try:
            entries = list(root.iterdir()) if root.is_dir() else []
        except OSError:
            entries = []
        for entry in entries:
            try:
                if (entry / "type").read_text(encoding="utf-8").strip() != "bluetooth":
                    continue
                for name in ("soft", "hard"):
                    if (entry / name).read_text(encoding="utf-8").strip() == "1":
                        return True
            except OSError:
                continue
        if entries:
            return False

        # No sysfs view, so fall back to the tool if it happens to be there.
        binary = shutil.which("rfkill")
        if binary is None:
            return False
        try:
            result = subprocess.run([binary, "list", "bluetooth"], capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return "blocked: yes" in (result.stdout or "").lower()

    def status(self) -> dict[str, Any]:
        if not self.available():
            return {
                "available": False,
                "powered": False,
                "adapter": "",
                "blocked": False,
                "advice": (
                    "bluetoothctl is not present. On the Pi install it with 'sudo apt install bluez'; "
                    "in Docker rebuild the image."
                ),
            }
        ok, output = self._run(["show"])
        powered = "Powered: yes" in output
        name_match = re.search(r"Name:\s*(.+)", output)
        state_match = re.search(r"PowerState:\s*(\S+)", output)
        power_state = state_match.group(1).strip() if state_match else ("on" if powered else "off")
        no_adapter = "No default controller" in output
        blocked = self.blocked()
        return {
            "available": True,
            "powered": powered,
            "adapter": name_match.group(1).strip() if name_match else "",
            "blocked": blocked,
            "powerState": power_state,
            "ertmDisabled": ertm_disabled(),
            "advice": self._advice(no_adapter, blocked, powered, power_state),
        }

    def _advice(self, no_adapter: bool, blocked: bool, powered: bool, power_state: str = "") -> str:
        # "off-enabling" is the adapter coming up, typically right after an
        # rfkill unblock. Saying "it is off" there would send you round again.
        if power_state.endswith("-enabling"):
            return "The adapter is powering on. Give it a second and this will clear."
        if power_state.endswith("-disabling"):
            return "The adapter is powering off."
        if no_adapter:
            return (
                "No Bluetooth adapter is visible. Check the bluetooth service is running "
                "('sudo systemctl status bluetooth'), and that the container can reach the host D-Bus socket."
            )
        if blocked:
            return "Bluetooth is blocked by rfkill. Unblock it with 'sudo rfkill unblock bluetooth'."
        if not powered:
            return "The adapter is off. Turn it on above, or run 'bluetoothctl power on'."
        return (
            "Ready. Put the device into pairing mode first - most controllers and speakers only "
            "advertise for a minute or two - then press Scan."
        )

    def set_power(self, on: bool) -> tuple[bool, str]:
        return self._run(["power", "on" if on else "off"])

    def _device_info(self, mac: str) -> dict[str, Any]:
        ok, output = self._run(["info", mac])
        name_match = re.search(r"Name:\s*(.+)", output)
        icon_match = re.search(r"Icon:\s*(.+)", output)
        name = name_match.group(1).strip() if name_match else ""
        icon = icon_match.group(1).strip() if icon_match else ""
        return {
            "mac": mac,
            # A device that has not answered a name request yet only has its
            # address, which is most of what a scan turns up.
            "name": name or mac,
            "named": bool(name),
            "paired": "Paired: yes" in output,
            "connected": "Connected: yes" in output,
            "trusted": "Trusted: yes" in output,
            "icon": icon,
            "role": classify(icon, name),
        }

    def _parse_device_list(self, output: str) -> list[str]:
        macs: list[str] = []
        for line in output.splitlines():
            match = _DEVICE_LINE.match(line.strip())
            if match:
                macs.append(match.group(1).upper())
        return macs

    def list_devices(self) -> list[dict[str, Any]]:
        if not self.available():
            return []
        ok, output = self._run(["devices"])
        macs = self._parse_device_list(output)
        devices = [self._device_info(mac) for mac in macs]
        # Connected first, then paired, then anything that told us its name.
        # Nameless strangers sink to the bottom where the UI can hide them.
        return sorted(
            devices,
            key=lambda device: (
                not device["connected"],
                not device["paired"],
                not device["named"],
                device["role"] == "other",
                device["name"].lower(),
            ),
        )

    def scan(self, seconds: int = 8) -> list[dict[str, Any]]:
        if not self.available():
            return []
        seconds = max(2, min(30, int(seconds)))
        self._run(["power", "on"])
        # bluetoothctl --timeout N scan on runs a timed discovery then exits.
        self._run(["--timeout", str(seconds), "scan", "on"], timeout=seconds + 10)
        return self.list_devices()

    def connect(self, mac: str) -> dict[str, Any]:
        address = self._safe_mac(mac)
        if not self.available():
            return {"ok": False, "message": "Bluetooth is not available on this device."}
        self._run(["power", "on"])
        info = self._device_info(address)
        messages: list[str] = []
        if not info["paired"]:
            ok, output = self._run(["pair", address], timeout=30)
            messages.append(f"pair: {output}")
        self._run(["trust", address])
        ok, output = self._run(["connect", address], timeout=30)
        messages.append(f"connect: {output}")
        final = self._device_info(address)
        return {
            "ok": final["connected"],
            "message": " | ".join(m for m in messages if m),
            "device": final,
            "advice": "" if final["connected"] else self._connect_advice(final, " ".join(messages)),
        }

    def _connect_advice(self, device: dict[str, Any], output: str) -> str:
        """Why a connect failed, in terms of what to do about it."""
        lowered = (output or "").lower()
        name = (device.get("name") or "").lower()
        is_xbox = "xbox" in name or device.get("role") == "controller"

        if is_xbox and ertm_disabled() is False:
            return ERTM_HELP
        if "authentication" in lowered or "failed" in lowered and device.get("paired"):
            return (
                "Pairing exists but the connection failed. Remove the device and pair again: "
                f"bluetoothctl remove {device.get('mac', '')}"
            )
        if "not available" in lowered or "does not exist" in lowered:
            return "The device stopped advertising. Put it back into pairing mode and scan again."
        if "in progress" in lowered:
            return "A connection is already in progress. Give it a few seconds and check again."
        if is_xbox:
            return ERTM_HELP
        return (
            "Put the device back into pairing mode and try again. If it keeps failing, remove it first "
            f"with: bluetoothctl remove {device.get('mac', '')}"
        )

    def disconnect(self, mac: str) -> dict[str, Any]:
        address = self._safe_mac(mac)
        if not self.available():
            return {"ok": False, "message": "Bluetooth is not available on this device."}
        ok, output = self._run(["disconnect", address])
        return {"ok": ok, "message": output, "device": self._device_info(address)}

    def remove(self, mac: str) -> dict[str, Any]:
        address = self._safe_mac(mac)
        if not self.available():
            return {"ok": False, "message": "Bluetooth is not available on this device."}
        ok, output = self._run(["remove", address])
        return {"ok": ok, "message": output}


bluetooth_service = BluetoothService()
