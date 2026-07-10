"""Display policy persistence for single, rotation, and trigger behavior."""

from __future__ import annotations

import json

from src.domain.models.widget_schemas import DisplayPolicy
from src.domain.services.config_service import config_service
from src.domain.services.widget_registry_service import widget_registry_service


class DisplayPolicyService:
    def __init__(self) -> None:
        self.policy_path = config_service.data_dir / "widgets" / "display_policy.json"

    def get_policy(self) -> DisplayPolicy:
        try:
            with self.policy_path.open("r", encoding="utf-8") as file:
                return DisplayPolicy.model_validate(json.load(file))
        except FileNotFoundError:
            return self.default_policy()

    def save_policy(self, policy: DisplayPolicy) -> DisplayPolicy:
        self._validate_policy(policy)
        self.policy_path.parent.mkdir(parents=True, exist_ok=True)
        with self.policy_path.open("w", encoding="utf-8") as file:
            json.dump(policy.model_dump(), file, indent=2)
            file.write("\n")
        return policy

    def remove_widget_references(self, widget_id: str) -> DisplayPolicy:
        policy = self.get_policy()
        if policy.activeWidgetId == widget_id:
            policy.activeWidgetId = "core.spotify"
            policy.mode = "single"
        policy.rotation = [item for item in policy.rotation if item.widgetId != widget_id]
        policy.triggers = [rule for rule in policy.triggers if rule.widgetId != widget_id]
        self.policy_path.parent.mkdir(parents=True, exist_ok=True)
        with self.policy_path.open("w", encoding="utf-8") as file:
            json.dump(policy.model_dump(), file, indent=2)
            file.write("\n")
        return policy

    def default_policy(self) -> DisplayPolicy:
        local_ids = {widget.manifest.id for widget in widget_registry_service.list_local_widgets()}
        rotation = [
            {"widgetId": widget_id, "durationSeconds": 60, "enabled": True}
            for widget_id in ("core.weather", "core.clock", "core.agent")
            if widget_id in local_ids
        ]
        triggers = [
            {
                "event": "spotify.playback_started",
                "widgetId": "core.spotify",
                "enabled": True,
                "priority": 50,
                "minDurationSeconds": 15,
            }
        ]
        return DisplayPolicy(activeWidgetId="core.spotify", rotation=rotation, triggers=triggers)

    def _validate_policy(self, policy: DisplayPolicy) -> None:
        local_ids = {widget.manifest.id for widget in widget_registry_service.list_local_widgets()}
        referenced_ids = {policy.activeWidgetId}
        referenced_ids.update(item.widgetId for item in policy.rotation)
        referenced_ids.update(rule.widgetId for rule in policy.triggers)
        missing = sorted(widget_id for widget_id in referenced_ids if widget_id not in local_ids)
        if missing:
            raise ValueError(f"Display policy references unknown local widgets: {', '.join(missing)}")
        if policy.mode == "rotation" and not any(item.enabled for item in policy.rotation):
            raise ValueError("Rotation mode needs at least one enabled rotation item.")


display_policy_service = DisplayPolicyService()
