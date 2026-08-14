"""Per-game controller binding routes, one set per input device."""

from __future__ import annotations

from fastapi import APIRouter

from mini_joystick.bindings import DEFAULT_PROFILE, GAMEPAD, MODULE, PROFILES, default_bindings, profile
from src.domain.models.api_schemas import BindingProfile, GameBindingsRequest, GameBindingsResponse
from src.domain.services.config_service import config_service
from src.domain.services.game_service import game_service

router = APIRouter(tags=["assistant-matrix-games"])


def _present(profile_id: str) -> bool:
    """Is a device of this kind actually connected right now?

    Only used to mark the profile in the picker, so a missing service or an
    absent peripheral is not an error.
    """
    try:
        if profile_id == GAMEPAD:
            from src.domain.services.gamepad_service import gamepad_service

            return bool(gamepad_service.status().get("connected"))
        from src.domain.services.joystick_service import joystick_service

        return bool(joystick_service.connected)
    except Exception:
        return False


def _profiles() -> list[BindingProfile]:
    return [
        BindingProfile(
            id=item.id,
            name=item.name,
            controls=list(item.controls),
            labels={control: item.label(control) for control in item.controls},
            present=_present(item.id),
        )
        for item in PROFILES.values()
    ]


def _response(game_id: str, device: str) -> GameBindingsResponse:
    spec = game_service.require_spec(game_id)
    chosen = profile(device)
    actions = list(spec.actions)
    defaults = default_bindings(set(actions), chosen.id)
    saved = config_service.get_config().controller.profiles.get(chosen.id, {}).get(spec.app_id, {})

    # Saved values win, but only where the game still declares that action and
    # this device actually has that control.
    effective = dict(defaults)
    effective.update(
        {
            control: value
            for control, value in saved.items()
            if control in chosen.controls and (value in actions or value == "none")
        }
    )
    return GameBindingsResponse(
        gameId=spec.game_id,
        appId=spec.app_id,
        profile=chosen.id,
        profiles=_profiles(),
        controls=list(chosen.controls),
        actions=actions,
        bindings=effective,
        defaults=defaults,
        customised=sorted(key for key, value in effective.items() if defaults.get(key) != value),
    )


@router.get("/api/games/{game_id}/bindings", response_model=GameBindingsResponse)
async def get_game_bindings(game_id: str, device: str = DEFAULT_PROFILE) -> GameBindingsResponse:
    return _response(game_id, device)


@router.post("/api/games/{game_id}/bindings", response_model=GameBindingsResponse)
async def save_game_bindings(game_id: str, body: GameBindingsRequest) -> GameBindingsResponse:
    spec = game_service.require_spec(game_id)
    chosen = profile(body.profile or DEFAULT_PROFILE)
    if body.profile and body.profile not in PROFILES:
        raise ValueError(f"Unknown device {body.profile}. Try one of: {', '.join(PROFILES)}")

    allowed = set(spec.actions) | {"none"}
    invalid = sorted(value for value in body.bindings.values() if value not in allowed)
    if invalid:
        raise ValueError(f"{spec.name} does not accept: {', '.join(invalid)}")
    unknown = sorted(key for key in body.bindings if key not in chosen.controls)
    if unknown:
        raise ValueError(f"The {chosen.name} has no {', '.join(unknown)}")

    config = config_service.get_config()
    profiles = {name: dict(games) for name, games in config.controller.profiles.items()}
    games = dict(profiles.get(chosen.id, {}))
    games[spec.app_id] = dict(body.bindings)
    profiles[chosen.id] = games
    config.controller.profiles = profiles
    config_service.save_config(config)
    return _response(game_id, chosen.id)


@router.delete("/api/games/{game_id}/bindings", response_model=GameBindingsResponse)
async def reset_game_bindings(game_id: str, device: str = DEFAULT_PROFILE) -> GameBindingsResponse:
    spec = game_service.require_spec(game_id)
    chosen = profile(device)
    config = config_service.get_config()
    profiles = {name: dict(games) for name, games in config.controller.profiles.items()}
    games = dict(profiles.get(chosen.id, {}))
    games.pop(spec.app_id, None)
    profiles[chosen.id] = games
    config.controller.profiles = profiles
    config_service.save_config(config)
    return _response(game_id, chosen.id)
