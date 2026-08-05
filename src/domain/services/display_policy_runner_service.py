"""Execute saved display policies."""

from __future__ import annotations

import threading
from typing import Any

from src.domain.models.app_schemas import DisplayPolicy, DisplayPolicyRuntimeState
from src.domain.services.display_policy_service import display_policy_service
from src.domain.services.app_registry_service import app_registry_service


class DisplayPolicyRunnerService:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._trigger_timer: threading.Timer | None = None
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
        self._cancel_trigger_timer()
        if policy.mode == "single":
            self.stop()
            _, runtime = app_registry_service.apply_app(policy.activeAppId)
            with self._lock:
                self._state = DisplayPolicyRuntimeState(schedulerRunning=False, activeAppId=policy.activeAppId, mode=policy.mode)
            return self.state(), runtime

        enabled_items = [item for item in policy.rotation if item.enabled]
        if not enabled_items:
            raise ValueError("Rotation mode needs at least one enabled app.")

        self.stop()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_rotation, args=(policy,), name="display-policy-rotation", daemon=True)
        self._thread.start()
        return self.state(), None

    def stop(self) -> DisplayPolicyRuntimeState:
        self._cancel_trigger_timer()
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)
        with self._lock:
            self._thread = None
            self._state.schedulerRunning = False
        return self.state()

    def trigger_event(self, event: str) -> tuple[DisplayPolicyRuntimeState, Any, str | None]:
        policy = display_policy_service.get_policy()
        matching_rules = [rule for rule in policy.triggers if rule.enabled and rule.event == event]
        if not matching_rules:
            with self._lock:
                self._state.lastError = None
            return self.state(), None, None

        rule = sorted(matching_rules, key=lambda item: item.priority, reverse=True)[0]
        self.stop()
        _, runtime = app_registry_service.apply_app(rule.appId)
        with self._lock:
            self._state = DisplayPolicyRuntimeState(
                schedulerRunning=False,
                activeAppId=rule.appId,
                mode=policy.mode,
                activeEvent=event,
                lastError=None,
            )

        duration = max(0, rule.minDurationSeconds)
        if duration:
            self._trigger_timer = threading.Timer(duration, self._resume_policy_after_trigger, args=(policy,))
            self._trigger_timer.daemon = True
            self._trigger_timer.start()
        return self.state(), runtime, rule.appId

    def _cancel_trigger_timer(self) -> None:
        timer = self._trigger_timer
        if timer is not None:
            timer.cancel()
        self._trigger_timer = None

    def _resume_policy_after_trigger(self, policy: DisplayPolicy) -> None:
        self._trigger_timer = None
        try:
            self.apply_policy(policy)
        except Exception as exc:
            with self._lock:
                self._state.lastError = str(exc)

    def _run_rotation(self, policy: DisplayPolicy) -> None:
        items = [item for item in policy.rotation if item.enabled]
        index = 0
        while not self._stop_event.is_set():
            item = items[index % len(items)]
            try:
                app_registry_service.apply_app(item.appId)
                with self._lock:
                    self._state = DisplayPolicyRuntimeState(schedulerRunning=True, activeAppId=item.appId, mode="rotation", lastError=None)
                wait_seconds = max(5, item.durationSeconds)
            except Exception as exc:
                with self._lock:
                    self._state = DisplayPolicyRuntimeState(schedulerRunning=True, activeAppId=item.appId, mode="rotation", lastError=str(exc))
                wait_seconds = 5
            index += 1
            self._stop_event.wait(wait_seconds)


display_policy_runner_service = DisplayPolicyRunnerService()
