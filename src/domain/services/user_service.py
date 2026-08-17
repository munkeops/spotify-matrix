"""Profiles on this unit, and what belongs to whoever is signed in."""

from __future__ import annotations

from typing import Any

from matrix_users import Profile, ProfileError, Profiles, validate_avatar
from src.domain.services.config_service import config_service


class UserService:
    @property
    def profiles(self) -> Profiles:
        # Read the data dir each time rather than at import: the tests
        # relocate it, and so does anyone running two units from one repo.
        return Profiles(config_service.data_dir / "users")

    def ensure_owner(self) -> Profile:
        """Guarantee somebody is using this unit.

        Called at startup. An install that predates profiles has none, and
        arriving at a sign-in screen on a device you have owned for months
        would be a poor way to learn the feature exists.
        """
        current = self.profiles.active()
        if current is not None:
            return current
        existing = self.profiles.list()
        if existing:
            return existing[0]
        return self.profiles.create("Owner")

    def state(self) -> dict[str, Any]:
        active = self.profiles.active()
        return {
            "profiles": [profile.public() for profile in self.profiles.list()],
            "activeId": active.id if active else "",
            #: True when the unit has to ask: several profiles and nobody
            #: chosen, or the chosen one wants a PIN.
            "signInRequired": active is None,
        }

    def create(self, name: str, pin: str | None = None) -> dict[str, Any]:
        return self.profiles.create(name, pin).public()

    def update(self, profile_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        profile = self.profiles.get(profile_id)
        if profile is None:
            raise ProfileError("No such profile.")

        if "name" in changes:
            name = str(changes["name"] or "").strip()
            if not name:
                raise ProfileError("A profile needs a name.")
            profile.name = name[:24]

        if "avatar" in changes or "palette" in changes:
            avatar = [str(row) for row in (changes.get("avatar") or profile.avatar)]
            palette = [str(colour) for colour in (changes.get("palette") or profile.palette)]
            validate_avatar(avatar, palette)
            profile.avatar, profile.palette = avatar, palette

        if "pin" in changes:
            # An empty string clears it; absent leaves it alone. The two
            # have to be different, or nobody could ever remove a PIN.
            profile.set_pin(str(changes["pin"]) if changes["pin"] else None)

        return self.profiles.save(profile).public()

    def delete(self, profile_id: str) -> dict[str, Any]:
        self.profiles.delete(profile_id)
        return self.state()

    def sign_in(self, profile_id: str, pin: str = "") -> dict[str, Any]:
        self.profiles.sign_in(profile_id, pin)
        return self.state()

    # --- what belongs to a person ----------------------------------------

    def scope(self) -> str:
        """Directory name for the signed-in profile's own data.

        High scores and controller bindings belong to a person; installed
        apps and panel settings belong to the unit. A single-profile unit
        still gets a directory of its own, so adding a second profile later
        does not have to move anything.
        """
        active = self.profiles.active()
        return active.id if active else "owner"


user_service = UserService()
