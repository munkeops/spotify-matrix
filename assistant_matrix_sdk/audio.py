"""The sound interface a game plugin sees.

A game just calls ``self.audio.play("blip")``. Whether a sound card exists,
whether audio is switched on, and how mixing works are all the host's problem,
so a plugin never has to check.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Audio(Protocol):
    """Anything that can play a named effect."""

    def play(self, name: str, volume: float = 1.0) -> bool: ...

    def known(self) -> list[str]: ...


class SilentAudio:
    """The default: every call is a no-op.

    Tests, previews and a matrix with no sound card all get this, which is why
    a game can call ``play`` unconditionally.
    """

    enabled = False

    def play(self, name: str, volume: float = 1.0) -> bool:
        return False

    def known(self) -> list[str]:
        return []


__all__ = ["Audio", "SilentAudio"]
