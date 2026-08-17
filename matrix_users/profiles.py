"""Who is using this unit.

A profile is a name, a face and optionally a PIN. It exists so that a
high score belongs to somebody, a controller layout survives someone else
using the matrix, and - later - so there is an identity to invite to a
party.

Deliberately not an account. There is no email, no password and no server
here: this is the household model, closer to a games console's than to a
web app's, and it works with the router unplugged. A cloud identity, if it
ever arrives, links to a profile rather than replacing it.

The PIN protects a sibling from spending your coins. It is four digits, so
it is not a secret in any serious sense, and nothing here should suggest
otherwise. It is still hashed and salted, because people reuse digits
across things that do matter.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Cost of hashing a PIN. There are only ten thousand of them, so a
#: determined person with the file wins regardless; this is aimed at making
#: it not free, not at pretending four digits are a password.
PIN_ROUNDS = 200_000

#: Avatars are drawn at 16x16 and shown on a 64x64 panel from across a
#: room. A photograph is unreadable at that size; sixteen squares of colour
#: are not.
AVATAR_SIZE = 16

MAX_NAME = 24
_ID = re.compile(r"^[a-z0-9-]{1,32}$")
_PIN = re.compile(r"^\d{4}$")


class ProfileError(ValueError):
    """Something the person doing it can fix, and should be told about."""


def slug(name: str) -> str:
    """A file-safe id from a display name, e.g. "Ada L." -> "ada-l"."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return cleaned[:32] or "user"


def hash_pin(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), bytes.fromhex(salt), PIN_ROUNDS).hex()


@dataclass
class Profile:
    id: str
    name: str
    #: Row strings of AVATAR_SIZE characters, indexing into ``palette``.
    #: Empty means "no avatar yet", which the UI draws as an initial.
    avatar: list[str] = field(default_factory=list)
    palette: list[str] = field(default_factory=list)
    #: Empty when the profile has no PIN, which is the default: a unit with
    #: one profile should not ask who you are.
    pin_hash: str = ""
    salt: str = ""
    created: float = 0.0
    last_seen: float = 0.0

    @property
    def has_pin(self) -> bool:
        return bool(self.pin_hash)

    def check_pin(self, pin: str) -> bool:
        if not self.has_pin:
            return True
        if not _PIN.match(pin or ""):
            return False
        return secrets.compare_digest(hash_pin(pin, self.salt), self.pin_hash)

    def set_pin(self, pin: str | None) -> None:
        """Set or clear the PIN. Four digits, or nothing at all."""
        if not pin:
            self.pin_hash = ""
            self.salt = ""
            return
        if not _PIN.match(pin):
            raise ProfileError("A PIN is four digits.")
        self.salt = secrets.token_hex(16)
        self.pin_hash = hash_pin(pin, self.salt)

    def public(self) -> dict[str, Any]:
        """What may safely leave the device.

        The hash and salt never appear in an API response. They are only
        useful to somebody attacking the PIN, and four digits need no help.
        """
        return {
            "id": self.id,
            "name": self.name,
            "avatar": list(self.avatar),
            "palette": list(self.palette),
            "hasPin": self.has_pin,
            "created": self.created,
            "lastSeen": self.last_seen,
        }

    def stored(self) -> dict[str, Any]:
        return {**self.public(), "pinHash": self.pin_hash, "salt": self.salt}

    @classmethod
    def load(cls, payload: dict[str, Any]) -> "Profile":
        return cls(
            id=str(payload.get("id", "")),
            name=str(payload.get("name", "")),
            avatar=[str(row) for row in payload.get("avatar", [])],
            palette=[str(colour) for colour in payload.get("palette", [])],
            pin_hash=str(payload.get("pinHash", "")),
            salt=str(payload.get("salt", "")),
            created=float(payload.get("created", 0.0) or 0.0),
            last_seen=float(payload.get("lastSeen", 0.0) or 0.0),
        )


def validate_avatar(avatar: list[str], palette: list[str]) -> None:
    """A drawing that will not render is refused at the door, not at draw time."""
    if not avatar:
        return
    if len(avatar) != AVATAR_SIZE:
        raise ProfileError(f"An avatar is {AVATAR_SIZE} rows.")
    if not palette:
        raise ProfileError("An avatar needs a palette.")
    if len(palette) > 62:
        raise ProfileError("An avatar palette holds at most 62 colours.")
    for colour in palette:
        if not re.match(r"^#[0-9a-fA-F]{6}$", colour):
            raise ProfileError(f"{colour} is not a colour like #ff8800.")
    for row in avatar:
        if len(row) != AVATAR_SIZE:
            raise ProfileError(f"Every avatar row is {AVATAR_SIZE} characters.")
        for character in row:
            if character != "." and not (0 <= _index(character) < len(palette)):
                raise ProfileError("An avatar refers to a colour that is not in its palette.")


def _index(character: str) -> int:
    """Base62 digit to number, matching how frames are encoded elsewhere."""
    if character.isdigit():
        return int(character)
    if "a" <= character <= "z":
        return ord(character) - ord("a") + 10
    if "A" <= character <= "Z":
        return ord(character) - ord("A") + 36
    return -1


class Profiles:
    """Every profile on this unit, and which one is using it."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.state_path = directory / "state.json"

    # --- storage ---------------------------------------------------------

    def _path(self, profile_id: str) -> Path:
        if not _ID.match(profile_id or ""):
            raise ProfileError("That is not a valid profile id.")
        return self.directory / f"{profile_id}.json"

    def list(self) -> list[Profile]:
        try:
            files = sorted(self.directory.glob("*.json"))
        except OSError:
            return []
        profiles = []
        for path in files:
            if path.name == "state.json":
                continue
            try:
                profiles.append(Profile.load(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(profiles, key=lambda profile: (-profile.last_seen, profile.name.lower()))

    def get(self, profile_id: str) -> Profile | None:
        try:
            return Profile.load(json.loads(self._path(profile_id).read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ProfileError):
            return None

    def save(self, profile: Profile) -> Profile:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(profile.id)
        # Written whole and moved into place: a unit losing power midway
        # through a save should not leave somebody without a profile.
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(profile.stored(), indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
        return profile

    # --- lifecycle -------------------------------------------------------

    def create(self, name: str, pin: str | None = None) -> Profile:
        name = (name or "").strip()
        if not name:
            raise ProfileError("A profile needs a name.")
        if len(name) > MAX_NAME:
            raise ProfileError(f"A name is at most {MAX_NAME} characters.")

        taken = {profile.id for profile in self.list()}
        base = slug(name)
        profile_id = base
        suffix = 2
        while profile_id in taken:
            profile_id = f"{base}-{suffix}"
            suffix += 1

        profile = Profile(id=profile_id, name=name, created=time.time())
        if pin:
            profile.set_pin(pin)
        self.save(profile)
        if len(taken) == 0:
            # The first profile is signed in without being asked for the PIN
            # it was just given: whoever set it is plainly standing there.
            self._set_active(profile)
        return profile

    def delete(self, profile_id: str) -> None:
        remaining = [profile for profile in self.list() if profile.id != profile_id]
        if not remaining:
            raise ProfileError("This is the only profile; a unit always has one.")
        try:
            self._path(profile_id).unlink()
        except OSError as error:
            raise ProfileError(f"Could not remove that profile: {error}") from error

        if self.active_id() != profile_id:
            return
        if len(remaining) == 1:
            # Their unit now.
            self._set_active(remaining[0])
        else:
            # Signing somebody in silently would walk straight past a PIN
            # that exists to be asked for. Nobody is active, and the unit
            # asks who is using it.
            self._clear_active()

    # --- who is using it -------------------------------------------------

    def active_id(self) -> str:
        try:
            return str(json.loads(self.state_path.read_text(encoding="utf-8")).get("activeId", ""))
        except (OSError, json.JSONDecodeError):
            return ""

    def active(self) -> Profile | None:
        """The signed-in profile, falling back to the only one there is.

        A unit is never in a state where nobody is using it: a single
        profile is that unit's user whether or not anything was written.
        """
        current = self.get(self.active_id()) if self.active_id() else None
        if current is not None:
            return current
        profiles = self.list()
        return profiles[0] if len(profiles) == 1 else None

    def sign_in(self, profile_id: str, pin: str = "") -> Profile:
        profile = self.get(profile_id)
        if profile is None:
            raise ProfileError("No such profile.")
        if not profile.check_pin(pin):
            raise ProfileError("That PIN is not right.")
        return self._set_active(profile)

    def _set_active(self, profile: Profile) -> Profile:
        self.directory.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps({"activeId": profile.id}, indent=2) + "\n", encoding="utf-8")
        profile.last_seen = time.time()
        return self.save(profile)

    def _clear_active(self) -> None:
        try:
            self.state_path.unlink()
        except OSError:
            pass
