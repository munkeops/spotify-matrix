"""A unit out of the box.

Games ship inside the image so that installing one is instant and works
with no network. That is not the same as having installed them, and a unit
somebody just unboxed should not arrive with fifteen games on it and an
empty store.
"""

import pytest


@pytest.fixture
def store_mode(monkeypatch):
    """A unit configured as a pure app host, as the compose file ships it."""
    from src.domain.services import app_registry_service as module

    monkeypatch.setattr(module, "BUILTIN_MODE", "store")
    return module


def test_a_fresh_unit_has_no_games_installed(store_mode, monkeypatch):
    monkeypatch.setattr(store_mode.AppRegistryService, "_installed_ids", lambda self: set())

    apps = store_mode.app_registry_service.list_local_apps()

    assert apps == [], "nothing is installed until somebody installs it"


def test_installing_one_makes_it_appear(store_mode, monkeypatch):
    monkeypatch.setattr(store_mode.AppRegistryService, "_installed_ids", lambda self: {"core.tetris"})

    ids = [app.manifest.id for app in store_mode.app_registry_service.list_local_apps()]

    assert ids == ["core.tetris"]


def test_the_store_offers_every_bundled_game():
    """A game bundled here but missing from the published index could
    previously be neither installed nor seen: it did not exist as far as
    anyone using the unit could tell."""
    from src.domain.services.app_registry_service import app_registry_service
    from src.domain.services.app_store_service import app_store_service

    bundled = {manifest.id for manifest in app_registry_service.bundled_manifests()}
    offered = {app.id for app in app_store_service.list_apps().apps}

    assert bundled, "expected games to ship in the image"
    assert bundled <= offered, f"not offered anywhere: {sorted(bundled - offered)}"


def test_the_newer_games_are_reachable():
    """These arrived after the published index was written."""
    from src.domain.services.app_store_service import app_store_service

    offered = {app.id for app in app_store_service.list_apps().apps}

    for app_id in ("core.chess", "core.tron", "core.centipede", "core.2048", "core.kong"):
        assert app_id in offered, f"{app_id} cannot be installed by anyone"
