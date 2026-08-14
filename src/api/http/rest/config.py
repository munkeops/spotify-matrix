"""Configuration REST routes."""

from __future__ import annotations

from fastapi import APIRouter

from matrix_display import drivers
from src.domain.models.api_schemas import AppConfig, MatrixDriver, MatrixDriversResponse
from src.domain.services.config_service import config_service

router = APIRouter(tags=["spotify-matrix-config"])


@router.get("/api/config", response_model=AppConfig)
async def get_config() -> AppConfig:
    return config_service.get_public_config()


@router.get("/api/matrix/drivers", response_model=MatrixDriversResponse)
async def matrix_drivers() -> MatrixDriversResponse:
    """The wirings this install can drive, and which one is in use.

    The definitions live on the server so the settings page and the runtime
    cannot drift apart about what "direct wiring" means.
    """
    matrix = config_service.get_config().matrix
    return MatrixDriversResponse(
        drivers=[
            MatrixDriver(
                id=driver.id,
                name=driver.name,
                summary=driver.summary,
                hardwareMapping=driver.hardware_mapping,
                gpioSlowdown=driver.gpio_slowdown,
                noHardwarePulse=driver.no_hardware_pulse,
                pins=driver.pins,
                notes=driver.notes,
            )
            for driver in drivers.DRIVERS
        ],
        active=drivers.detect(matrix.hardwareMapping),
        pinOrder=list(drivers.PIN_ORDER),
    )


#: Matrix settings the runtime only reads when it starts.
RESTART_ON_CHANGE = (
    "rows",
    "cols",
    "chainLength",
    "parallel",
    "gpioSlowdown",
    "hardwareMapping",
    "pwmBits",
    "limitRefreshRateHz",
    "noHardwarePulse",
    "rotation",
)


@router.post("/api/config", response_model=AppConfig)
async def save_config(body: AppConfig) -> AppConfig:
    """Save, and make the panel reflect what was saved.

    Writing the file used to be the whole job, so changing brightness here
    did nothing until something else restarted the runtime - the setting
    moved, the matrix did not.
    """
    before = config_service.get_config().matrix
    saved = config_service.save_config(body)
    after = config_service.get_config().matrix

    if any(getattr(before, name, None) != getattr(after, name, None) for name in RESTART_ON_CHANGE):
        # These are constructor arguments to the panel driver; nothing short
        # of a restart picks them up.
        from src.domain.services.runtime_service import runtime_service

        runtime_service.apply()
    elif before.brightness != after.brightness:
        # Brightness the binding takes live, so no restart and no flicker.
        from src.domain.services.joystick_service import joystick_service

        joystick_service.publish_brightness(after.brightness)
    return saved
