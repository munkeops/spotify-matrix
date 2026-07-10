"""Execute saved display policies."""

from __future__ import annotations

import threading
from typing import Any

from src.domain.models.widget_schemas import DisplayPolicy, DisplayPolicyRuntimeState
from src.domain.services.display_policy_service import display_policy_service
from src.domain.services.widget_registry_service import widget_registry_service


class DisplayPolicyRunnerService:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._state = DisplayPolicyRuntimeState()

    def state(self) -> DisplayPolicyRuntimeState:
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
            self._state.schedulerRunning = running
            return self._state.model_copy()

    def apply_policy(self, policy: DisplayPolicy | None = None) -> tuple[DisplayPolicyRuntimeState, Any]:
        policy = policy or display_policy_service.get_policy()
        display_policy_service.save_policy(policy)
        if policy.mode == "single":
            self.stop()
            _, runtime = widget_registry_service.apply_widget(policy.activeWidgetId)
            with self._lock:
                self._state = DisplayPolicyRuntimeState(schedulerRunning=False, activeWidgetId=policy.activeWidgetId, mode=policy.mode)
            return self.state(), runtime

        enabled_items = [item for item in policy.rotation if item.enabled]
        if not enabled_items:
            raise ValueError("Rotation mode needs at least one enabled widget.")

        self.stop()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_rotation, args=(policy,), name="display-policy-rotation", daemon=True)
        self._thread.start()
        return self.state(), None

    def stop(self) -> DisplayPolicyRuntimeState:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)
        with self._lock:
            self._thread = None
            self._state.schedulerRunning = False
        return self.state()

    def _run_rotation(self, policy: DisplayPolicy) -> None:
        items = [item for item in policy.rotation if item.enabled]
        index = 0
        while not self._stop_event.is_set():
            item = items[index % len(items)]
            try:
                widget_registry_service.apply_widget(item.widgetId)
                with self._lock:
                    self._state = DisplayPolicyRuntimeState(schedulerRunning=True, activeWidgetId=item.widgetId, mode="rotation", lastError=None)
                wait_seconds = max(5, item.durationSeconds)
            except Exception as exc:
                with self._lock:
                    self._state = DisplayPolicyRuntimeState(schedulerRunning=True, activeWidgetId=item.widgetId, mode="rotation", lastError=str(exc))
                wait_seconds = 5
            index += 1
            self._stop_event.wait(wait_seconds)


display_policy_runner_service = DisplayPolicyRunnerService()
