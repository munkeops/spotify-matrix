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

    def status(self) -> dict[str, Any]:
        if not self.available():
            return {"available": False, "powered": False, "adapter": ""}
        ok, output = self._run(["show"])
        powered = "Powered: yes" in output
        name_match = re.search(r"Name:\s*(.+)", output)
        return {"available": True, "powered": powered, "adapter": name_match.group(1).strip() if name_match else ""}

    def set_power(self, on: bool) -> tuple[bool, str]:
        return self._run(["power", "on" if on else "off"])

    def _device_info(self, mac: str) -> dict[str, Any]:
        ok, output = self._run(["info", mac])
        name_match = re.search(r"Name:\s*(.+)", output)
        icon_match = re.search(r"Icon:\s*(.+)", output)
        return {
            "mac": mac,
            "name": name_match.group(1).strip() if name_match else mac,
            "paired": "Paired: yes" in output,
            "connected": "Connected: yes" in output,
            "trusted": "Trusted: yes" in output,
            "icon": icon_match.group(1).strip() if icon_match else "",
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
        return [self._device_info(mac) for mac in macs]

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
        return {"ok": final["connected"], "message": " | ".join(m for m in messages if m), "device": final}

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
