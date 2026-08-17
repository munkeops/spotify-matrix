"""The profile service and what it lets out of the device."""

import importlib

import pytest


@pytest.fixture
def users(tmp_path, monkeypatch):
    """A service pointed at an empty unit."""
    monkeypatch.setenv("SPOTIFY_MATRIX_DATA_DIR", str(tmp_path / "data"))

    from src.domain.services import config_service as config_module

    importlib.reload(config_module)
    from src.domain.services import user_service as user_module

    importlib.reload(user_module)
    return user_module.user_service


def test_a_unit_that_predates_profiles_gets_one(users):
    """Arriving at a sign-in screen on a device owned for months would be a
    poor way to learn the feature exists."""
    owner = users.ensure_owner()

    assert owner.name == "Owner"
    assert users.state()["activeId"] == owner.id
    assert users.state()["signInRequired"] is False


def test_ensure_owner_does_not_pile_up_owners(users):
    first = users.ensure_owner()

    for _ in range(3):
        users.ensure_owner()

    assert [profile["id"] for profile in users.state()["profiles"]] == [first.id]


def test_the_state_never_carries_a_pin_hash(users):
    users.create("Ada", pin="1234")

    payload = repr(users.state())

    assert "pinHash" not in payload and "salt" not in payload


def test_an_avatar_round_trips(users):
    users.create("Ada")
    avatar = ["0123456789abcdef"] * 16
    palette = [f"#{value:02x}00ff" for value in range(16)]

    saved = users.update("ada", {"avatar": avatar, "palette": palette})

    assert saved["avatar"] == avatar
    assert users.state()["profiles"][0]["palette"] == palette


def test_an_avatar_the_panel_could_not_draw_is_refused(users):
    from matrix_users import ProfileError

    users.create("Ada")

    with pytest.raises(ProfileError):
        users.update("ada", {"avatar": ["0" * 16] * 4, "palette": ["#ffffff"]})


def test_renaming_keeps_the_id(users):
    """Scores and bindings hang off the id, so a rename must not orphan them."""
    created = users.create("Ada")

    renamed = users.update(created["id"], {"name": "Ada Lovelace"})

    assert renamed["id"] == created["id"]
    assert renamed["name"] == "Ada Lovelace"


def test_a_pin_can_be_added_and_removed(users):
    users.create("Ada")

    assert users.update("ada", {"pin": "4321"})["hasPin"] is True
    assert users.update("ada", {"pin": ""})["hasPin"] is False


def test_leaving_the_pin_out_does_not_clear_it(users):
    """Absent and empty have to mean different things, or a rename would
    quietly unlock the profile."""
    users.create("Ada", pin="1234")

    after = users.update("ada", {"name": "Ada L"})

    assert after["hasPin"] is True


def test_data_belongs_to_whoever_is_signed_in(users):
    users.create("Ada")
    users.create("Bob")

    assert users.scope() == "ada"
    users.sign_in("bob")
    assert users.scope() == "bob"


def test_a_unit_with_nobody_signed_in_still_has_somewhere_to_put_things(users):
    """scope() feeds a directory path, so it can never be empty."""
    assert users.scope() == "owner"
