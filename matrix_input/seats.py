"""Which input device drives which player.

A seat is a player slot in the running game. Devices claim one by being used:
press anything on a second controller and it takes seat 2, which is how an
arcade cabinet has always worked and needs no setup screen to get going.

Identity matters more than kind here. Two Xbox pads are two devices, so they
are told apart by address; the I2C module is the only one of its kind and
needs no address at all.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Device:
    """One thing a person can hold."""

    #: "module" for the I2C board, "gamepad" for a pad. Matches the binding
    #: profiles, so a seat and a key mapping talk about the same devices.
    kind: str
    #: Address or event path. Empty for the I2C module, which is a singleton.
    id: str = ""

    def label(self) -> str:
        if self.kind == "module":
            return "Mini-joystick module"
        return f"Gamepad {self.id}" if self.id else "Gamepad"


class Seats:
    """Seat assignments for the game currently on the matrix.

    Deliberately in memory only. A seat means "this pad is player two in the
    game running right now"; remembering it across a reboot would hand seat
    two to whoever happened to hold that controller last time.
    """

    def __init__(self, capacity: int = 1) -> None:
        self._capacity = max(1, int(capacity))
        self._seats: dict[int, Device] = {}

    @property
    def capacity(self) -> int:
        return self._capacity

    def set_capacity(self, capacity: int) -> None:
        """Resize for a different game, dropping anyone past the new end."""
        self._capacity = max(1, int(capacity))
        for seat in [seat for seat in self._seats if seat >= self._capacity]:
            del self._seats[seat]

    def seat_of(self, device: Device) -> int | None:
        for seat, seated in self._seats.items():
            if seated == device:
                return seat
        return None

    def claim(self, device: Device) -> int | None:
        """Put a device in the lowest free seat. None when the game is full."""
        existing = self.seat_of(device)
        if existing is not None:
            return existing
        for seat in range(self._capacity):
            if seat not in self._seats:
                self._seats[seat] = device
                return seat
        return None

    def seat_for(self, device: Device) -> int | None:
        """The seat this device drives, claiming one on first use.

        This is the join-on-press rule: a device that has not played yet takes
        the next free seat, and once the game is full further devices are
        ignored rather than stealing someone's paddle.
        """
        return self.claim(device)

    def release(self, device: Device) -> None:
        seat = self.seat_of(device)
        if seat is not None:
            del self._seats[seat]

    def reset(self) -> None:
        self._seats.clear()

    def occupied(self) -> dict[int, Device]:
        return dict(sorted(self._seats.items()))

    def free(self) -> list[int]:
        return [seat for seat in range(self._capacity) if seat not in self._seats]

    def describe(self) -> list[dict[str, object]]:
        """One entry per seat, for the app to show who is playing."""
        return [
            {
                "seat": seat,
                "player": seat + 1,
                "device": self._seats[seat].label() if seat in self._seats else "",
                "kind": self._seats[seat].kind if seat in self._seats else "",
                "id": self._seats[seat].id if seat in self._seats else "",
                "taken": seat in self._seats,
            }
            for seat in range(self._capacity)
        ]


__all__ = ["Device", "Seats"]
