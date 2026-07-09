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

    def _args(self) -> list[str]:
        config = config_service.get_config()
        matrix = config.matrix
        args = [
            str(self.runtime_script),
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
            "--no-browser",
        ]
        if matrix.noHardwarePulse:
            args.append("--no-hardware-pulse")
        if config.runtime.mockOutput:
            args.extend(["--mock-output", config.runtime.mockOutput])
        if config.runtime.testPattern:
            args.append("--test-pattern")
        return args


runtime_service = RuntimeService()
