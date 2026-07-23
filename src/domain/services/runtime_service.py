"""Python matrix runtime supervisor."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from configs import base_config
from src.domain.models.api_schemas import RuntimeExit, RuntimeState
from src.domain.services.config_service import config_service


class RuntimeService:
    def __init__(self) -> None:
        runtime_config = base_config["runtime"]
        paths = base_config["paths"]
        self.python_bin = os.environ.get("PYTHON_BIN", str(runtime_config["python_bin"]))
        if os.name == "nt" and self.python_bin == "python3":
            self.python_bin = "python"
        self.runtime_script = Path(paths["runtime_script"]).resolve()
        self.process: subprocess.Popen | None = None
        self.started_at: str | None = None
        self.last_exit: RuntimeExit | None = None

    def state(self) -> RuntimeState:
        running = self.process is not None and self.process.poll() is None
        if self.process is not None and not running and self.last_exit is None:
            self.last_exit = RuntimeExit(code=self.process.returncode, signal=None, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        return RuntimeState(
            running=running,
            pid=self.process.pid if running and self.process else None,
            startedAt=self.started_at,
            lastExit=self.last_exit,
        )

    def start(self) -> RuntimeState:
        if self.process is not None and self.process.poll() is None:
            return self.state()

        config = config_service.get_config()
        missing = config_service.missing_values(config)
        if missing:
            raise ValueError(f"Missing {', '.join(missing)}")

        self.process = subprocess.Popen(
            [self.python_bin, *self._args()],
            cwd=Path.cwd(),
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        self.started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.last_exit = None
        return self.state()

    def stop(self) -> RuntimeState:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.process is not None and self.process.poll() is not None:
            self.last_exit = RuntimeExit(code=self.process.returncode, signal=None, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        return self.state()

    def apply(self) -> RuntimeState:
        was_running = self.process is not None and self.process.poll() is None
        if was_running:
            self.stop()
        return self.start()

    def _args(self) -> list[str]:
        config = config_service.get_config()
        matrix = config.matrix
        http_config = base_config["http"]
        event_api_url = os.environ.get("ASSISTANT_MATRIX_EVENT_API_URL", f"http://127.0.0.1:{http_config['port']}/api/display/events")
        args = [
            str(self.runtime_script),
            "--display-mode",
            "testPattern" if config.runtime.testPattern else config.display.mode,
            "--clock-face",
            config.clock.face,
            "--agent-face-style",
            config.agent.faceStyle,
            "--agent-animation-speed",
            config.agent.animationSpeed,
            "--weather-label",
            config.weather.label,
            "--weather-postal-code",
            config.weather.postalCode,
            "--weather-country-code",
            config.weather.countryCode,
            "--weather-temperature-unit",
            config.weather.temperatureUnit,
            "--weather-face-accessory",
            config.weather.faceAccessory,
            "--weather-refresh-minutes",
            str(config.weather.refreshMinutes),
            "--weather-metrics-seconds",
            str(config.weather.metricsSeconds),
            "--weather-scene-seconds",
            str(config.weather.sceneSeconds),
            "--config-path",
            str(config_service.config_path),
            "--token-cache",
            str(config_service.token_path),
            "--rows",
            str(matrix.rows),
            "--cols",
            str(matrix.cols),
            "--chain-length",
            str(matrix.chainLength),
            "--parallel",
            str(matrix.parallel),
            "--brightness",
            str(matrix.brightness),
            "--gpio-slowdown",
            str(matrix.gpioSlowdown),
            "--hardware-mapping",
            matrix.hardwareMapping,
            "--pwm-bits",
            str(matrix.pwmBits),
            "--limit-refresh-rate-hz",
            str(matrix.limitRefreshRateHz),
            "--poll-seconds",
            str(matrix.pollSeconds),
            "--fps",
            str(matrix.fps),
            "--rpm",
            str(matrix.rpm),
            "--event-api-url",
            event_api_url,
            "--rotation",
            str(matrix.rotation),
            "--no-browser",
        ]
        if matrix.noHardwarePulse:
            args.append("--no-hardware-pulse")
        if config.runtime.mockOutput:
            args.extend(["--mock-output", config.runtime.mockOutput])
        if config.clock.use24Hour:
            args.append("--clock-24-hour")
        if config.clock.showSeconds:
            args.append("--clock-show-seconds")
        if config.clock.timezone:
            args.extend(["--clock-timezone", config.clock.timezone])
        if config.weather.latitude is not None:
            args.extend(["--weather-latitude", str(config.weather.latitude)])
        if config.weather.longitude is not None:
            args.extend(["--weather-longitude", str(config.weather.longitude)])
        args.extend(
            [
                "--text-value",
                config.text.text,
                "--text-color",
                config.text.color,
                "--text-background",
                config.text.background,
                "--text-scroll-speed",
                config.text.scrollSpeed,
                "--text-font-size",
                config.text.fontSize,
                "--text-align",
                config.text.align,
            ]
        )
        if config.text.scroll:
            args.append("--text-scroll")
        if config.runtime.testPattern:
            args.append("--test-pattern")
        if config.display.mode == "widget" and config.display.widgetId:
            widget_id = config.display.widgetId
            args.extend(
                [
                    "--widget-id",
                    widget_id,
                    "--widget-dir",
                    str(config_service.data_dir / "widgets" / "packages" / widget_id),
                    "--widget-config",
                    str(config_service.data_dir / "widgets" / "config" / f"{widget_id}.json"),
                ]
            )
        return args


runtime_service = RuntimeService()
