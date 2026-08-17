"""Profiles on a unit.

The household model, not the web one: no email, no password, works with
the router unplugged.
"""

import pytest

from matrix_users import Profile, ProfileError, Profiles, slug, validate_avatar


@pytest.fixture
def profiles(tmp_path):
    return Profiles(tmp_path / "users")


def test_a_new_unit_signs_in_the_profile_it_creates(profiles):
    """Nobody should be asked who they are by a matrix with one user."""
    created = profiles.create("Ada")

    assert profiles.active_id() == created.id
    assert profiles.active().name == "Ada"


def test_the_only_profile_is_the_active_one_even_unwritten(profiles):
    """A unit is never in a state where nobody is using it."""
    profiles.create("Ada")
    profiles.state_path.unlink()

    assert profiles.active().name == "Ada"


def test_a_second_profile_does_not_steal_the_session(profiles):
    first = profiles.create("Ada")
    profiles.create("Bob")

    assert profiles.active_id() == first.id, "creating a profile is not signing in as them"


def test_names_that_collide_still_get_their_own_profile(profiles):
    one = profiles.create("Ada")
    two = profiles.create("Ada")

    assert one.id != two.id
    assert {profile.id for profile in profiles.list()} == {one.id, two.id}


@pytest.mark.parametrize("name,expected", [("Ada L.", "ada-l"), ("  spaced  ", "spaced"), ("!!!", "user")])
def test_ids_are_file_safe(name, expected):
    assert slug(name) == expected


def test_a_profile_without_a_pin_does_not_ask_for_one(profiles):
    profiles.create("Ada")

    assert profiles.get("ada").check_pin("") is True


def test_a_pin_is_checked(profiles):
    profiles.create("Ada", pin="1234")

    assert profiles.get("ada").check_pin("1234") is True
    assert profiles.get("ada").check_pin("9999") is False
    assert profiles.get("ada").check_pin("") is False


def test_signing_in_with_the_wrong_pin_changes_nothing(profiles):
    ada = profiles.create("Ada", pin="1234")
    profiles.create("Bob")
    profiles.sign_in("bob")

    with pytest.raises(ProfileError):
        profiles.sign_in(ada.id, "0000")

    assert profiles.active_id() == "bob", "a refused sign-in did not switch anyone"


def test_the_pin_never_leaves_the_device(profiles):
    profiles.create("Ada", pin="1234")

    public = profiles.get("ada").public()

    assert public["hasPin"] is True
    assert "pinHash" not in public and "salt" not in public


def test_a_pin_is_not_stored_in_the_clear(profiles):
    profiles.create("Ada", pin="1234")

    stored = (profiles.directory / "ada.json").read_text(encoding="utf-8")

    assert "1234" not in stored


def test_the_same_pin_hashes_differently_for_two_people(profiles):
    """Per-profile salt, so one cracked PIN does not reveal the other."""
    profiles.create("Ada", pin="1234")
    profiles.create("Bob", pin="1234")

    assert profiles.get("ada").pin_hash != profiles.get("bob").pin_hash


def test_a_pin_must_be_four_digits(profiles):
    profile = Profile(id="ada", name="Ada")

    for bad in ("12", "abcd", "123456"):
        with pytest.raises(ProfileError):
            profile.set_pin(bad)


def test_clearing_a_pin_leaves_nothing_behind(profiles):
    profiles.create("Ada", pin="1234")
    ada = profiles.get("ada")

    ada.set_pin(None)

    assert (ada.pin_hash, ada.salt) == ("", "")
    assert ada.has_pin is False


def test_the_last_profile_cannot_be_deleted(profiles):
    profiles.create("Ada")

    with pytest.raises(ProfileError):
        profiles.delete("ada")


def test_deleting_the_signed_in_profile_signs_in_another(profiles):
    """Otherwise the unit is left with nobody using it and no way to say so."""
    profiles.create("Ada")
    profiles.create("Bob")
    profiles.sign_in("bob")

    profiles.delete("bob")

    assert profiles.active_id() == "ada"


def test_an_avatar_that_would_not_render_is_refused():
    palette = ["#ff0000", "#00ff00"]
    good = ["0" * 16] * 16

    validate_avatar(good, palette)
    validate_avatar([], [])

    with pytest.raises(ProfileError):
        validate_avatar(["0" * 16] * 15, palette)
    with pytest.raises(ProfileError):
        validate_avatar(["0" * 15] * 16, palette)
    with pytest.raises(ProfileError):
        validate_avatar(["9" * 16] * 16, palette)
    with pytest.raises(ProfileError):
        validate_avatar(good, ["red"])


def test_transparent_pixels_are_allowed():
    validate_avatar(["." * 16] * 16, ["#ff0000"])


def test_a_half_written_save_cannot_lose_a_profile(profiles, monkeypatch):
    """Written whole and moved into place, so a power cut mid-save leaves
    the previous profile rather than a truncated file."""
    profiles.create("Ada")
    written = []
    monkeypatch.setattr("os.replace", lambda src, dst: written.append((src, dst)))

    profiles.save(profiles.get("ada"))

    assert written, "the file is moved into place, not written over"


def test_creating_the_first_profile_with_a_pin_still_signs_them_in(profiles):
    """Whoever just chose the PIN is plainly standing there."""
    created = profiles.create("Ada", pin="1234")

    assert profiles.active_id() == created.id


def test_deleting_the_active_profile_does_not_walk_past_a_pin(profiles):
    """With several left, signing one in silently would step straight over
    the PIN that exists to be asked for. Nobody is active, and the unit
    asks who is using it."""
    profiles.create("Ada")
    profiles.create("Bob", pin="1234")
    profiles.create("Cal", pin="9999")
    profiles.sign_in("ada")

    profiles.delete("ada")

    assert profiles.active_id() == ""
    assert profiles.active() is None, "the unit asks rather than guessing"
