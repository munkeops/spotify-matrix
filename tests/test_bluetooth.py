

def test_pairing_and_connecting_are_separate_steps(monkeypatch):
    """One button that paired then connected could not say which half went
    wrong, and left no way to keep a device without connecting it."""
    from src.domain.services import bluetooth_service as module

    calls: list[list[str]] = []

    def fake_run(self, args, timeout=20.0):
        calls.append(list(args))
        return True, ""

    monkeypatch.setattr(module.BluetoothService, "_run", fake_run)
    monkeypatch.setattr(module.BluetoothService, "available", lambda self: True)
    monkeypatch.setattr(
        module.BluetoothService, "_device_info",
        lambda self, mac: {"mac": mac, "name": "Pad", "named": True, "paired": False,
                           "connected": False, "trusted": False, "icon": "", "role": "controller"},
    )

    module.bluetooth_service.pair("AA:BB:CC:DD:EE:FF")

    verbs = [call[0] for call in calls]
    assert "pair" in verbs and "trust" in verbs
    assert "connect" not in verbs, "pairing does not connect"


def test_connecting_something_unpaired_says_to_pair_first(monkeypatch):
    from src.domain.services import bluetooth_service as module

    monkeypatch.setattr(module.BluetoothService, "_run", lambda self, args, timeout=20.0: (True, ""))
    monkeypatch.setattr(module.BluetoothService, "available", lambda self: True)
    monkeypatch.setattr(
        module.BluetoothService, "_device_info",
        lambda self, mac: {"mac": mac, "name": "Pad", "named": True, "paired": False,
                           "connected": False, "trusted": False, "icon": "", "role": "controller"},
    )

    result = module.bluetooth_service.connect("AA:BB:CC:DD:EE:FF")

    assert result["ok"] is False
    assert "pair" in result["advice"].lower()


def test_pairing_trusts_so_it_comes_back_by_itself(monkeypatch):
    """An untrusted device needs authorising by hand on every reconnect,
    which on a headless matrix means it silently never returns."""
    from src.domain.services import bluetooth_service as module

    calls: list[list[str]] = []
    monkeypatch.setattr(module.BluetoothService, "_run",
                        lambda self, args, timeout=20.0: (calls.append(list(args)), (True, ""))[1])
    monkeypatch.setattr(module.BluetoothService, "available", lambda self: True)
    monkeypatch.setattr(
        module.BluetoothService, "_device_info",
        lambda self, mac: {"mac": mac, "name": "Speaker", "named": True, "paired": True,
                           "connected": False, "trusted": False, "icon": "", "role": "audio"},
    )

    module.bluetooth_service.pair("AA:BB:CC:DD:EE:FF")

    assert ["trust", "AA:BB:CC:DD:EE:FF"] in calls


def test_the_advice_points_at_a_control_that_exists():
    """It said to turn the adapter on "above" while the panel had no switch:
    the route and the service existed, the control never did."""
    from pathlib import Path

    from src.domain.services.bluetooth_service import bluetooth_service

    advice = bluetooth_service._advice(no_adapter=False, blocked=False, powered=False)
    panel = Path("web/src/components/BluetoothPanel.tsx").read_text(encoding="utf-8")

    assert "switch" in advice.lower()
    assert "<Switch" in panel, "the panel has the switch the advice names"
    assert "btPower" in panel, "and it is wired to the route"


def test_scanning_is_refused_while_the_adapter_is_off():
    """A scan with the adapter off returns nothing and looks like no devices
    rather than no Bluetooth."""
    from pathlib import Path

    panel = Path("web/src/components/BluetoothPanel.tsx").read_text(encoding="utf-8")

    assert "!powered || scanning" in panel


def test_forgetting_disconnects_first(monkeypatch):
    """A connected device will not be cleanly forgotten."""
    from src.domain.services import bluetooth_service as module

    calls: list[list[str]] = []
    monkeypatch.setattr(module.BluetoothService, "_run",
                        lambda self, args, timeout=20.0: (calls.append(list(args)), (True, ""))[1])
    monkeypatch.setattr(module.BluetoothService, "available", lambda self: True)

    states = iter([
        {"mac": "A", "name": "Pad", "named": True, "paired": True, "connected": True, "trusted": True, "icon": "", "role": "controller"},
        {"mac": "A", "name": "Pad", "named": True, "paired": False, "connected": False, "trusted": False, "icon": "", "role": "controller"},
    ])
    monkeypatch.setattr(module.BluetoothService, "_device_info", lambda self, mac: next(states))

    result = module.bluetooth_service.remove("AA:BB:CC:DD:EE:FF")

    verbs = [call[0] for call in calls]
    assert verbs.index("disconnect") < verbs.index("remove"), "disconnect comes first"
    assert result["ok"] is True


def test_an_unanswered_query_is_not_reported_as_the_adapter_being_off(monkeypatch):
    """A timeout, a dead bluetoothd and a D-Bus refusal all used to read as
    "The adapter is off", sending you to a switch that could not help."""
    from src.domain.services import bluetooth_service as module

    service = module.BluetoothService()
    monkeypatch.setattr(module.BluetoothService, "available", lambda self: True)
    monkeypatch.setattr(module.BluetoothService, "blocked", lambda self: False)
    monkeypatch.setattr(
        module.BluetoothService, "_run",
        lambda self, args, timeout=20.0: (False, "bluetoothctl show timed out."),
    )

    state = service.status()

    assert state["powerState"] == "unknown", "we did not learn the state"
    assert "adapter is off" not in state["advice"].lower()
    assert "timed out" in state["advice"]


def test_an_adapter_stuck_enabling_stops_saying_give_it_a_second(monkeypatch):
    """BlueZ leaves PowerState at off-enabling when the kernel refuses the
    power-on, so the reassuring message would never clear."""
    from src.domain.services import bluetooth_service as module

    service = module.BluetoothService()
    monkeypatch.setattr(module.BluetoothService, "available", lambda self: True)
    monkeypatch.setattr(module.BluetoothService, "blocked", lambda self: False)
    monkeypatch.setattr(
        module.BluetoothService, "_run",
        lambda self, args, timeout=20.0: (True, "Powered: no\n\tPowerState: off-enabling"),
    )

    clock = iter([100.0, 100.0, 200.0, 200.0])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))

    assert "second" in service.status()["advice"], "just now, it really is coming up"
    assert "dmesg" in service.status()["advice"], "a minute later, it is not"


def test_a_refused_power_on_says_why_rather_than_reading_the_state_back(monkeypatch):
    """'Failed to set power on: org.bluez.Error.Failed' is the whole answer,
    and it is gone by the time you ask the adapter how it is."""
    from src.domain.services import bluetooth_service as module

    service = module.BluetoothService()
    monkeypatch.setattr(module.BluetoothService, "available", lambda self: True)
    monkeypatch.setattr(module.BluetoothService, "blocked", lambda self: False)
    monkeypatch.setattr(
        module.BluetoothService, "set_power",
        lambda self, on: (False, "Failed to set power on: org.bluez.Error.Failed"),
    )
    monkeypatch.setattr(
        module.BluetoothService, "status",
        lambda self: {"available": True, "powered": False, "blocked": False,
                      "powerState": "off-enabling", "adapter": "matrix", "advice": "coming up"},
    )

    state = service.power(True)

    assert "org.bluez.Error.Failed" in state["advice"]
    assert "dmesg" in state["advice"], "and what to look at next"


def test_the_adapter_is_switched_on_at_startup():
    """BlueZ need not power it at boot and an rfkill block survives one, so
    the matrix could come up with working hardware that finds nothing."""
    from pathlib import Path

    server = Path("src/server.py").read_text(encoding="utf-8")

    assert "ensure_powered()" in server


def test_startup_does_not_fight_rfkill_or_a_silent_daemon(monkeypatch):
    """Powering on cannot win against either, and retrying just delays boot."""
    from src.domain.services import bluetooth_service as module

    service = module.BluetoothService()
    attempts: list[bool] = []
    monkeypatch.setattr(module.BluetoothService, "set_power", lambda self, on: attempts.append(on))
    monkeypatch.setattr(
        module.BluetoothService, "status",
        lambda self: {"available": True, "powered": False, "blocked": True,
                      "powerState": "off", "advice": "rfkill"},
    )

    powered, why = service.ensure_powered()

    assert powered is False and why == "rfkill"
    assert attempts == [], "it did not try anyway"


def test_forgetting_reports_what_bluez_says_not_the_exit_code(monkeypatch):
    """bluetoothctl exits 0 whether or not it removed anything, so a forget
    that silently did nothing reported success."""
    from src.domain.services import bluetooth_service as module

    monkeypatch.setattr(module.BluetoothService, "_run", lambda self, args, timeout=20.0: (True, ""))
    monkeypatch.setattr(module.BluetoothService, "available", lambda self: True)
    # Still paired afterwards: the remove did not take.
    monkeypatch.setattr(
        module.BluetoothService, "_device_info",
        lambda self, mac: {"mac": mac, "name": "Pad", "named": True, "paired": True,
                           "connected": False, "trusted": True, "icon": "", "role": "controller"},
    )

    result = module.bluetooth_service.remove("AA:BB:CC:DD:EE:FF")

    assert result["ok"] is False, "exit 0 is not proof it worked"
    assert "bluetoothctl remove" in result["advice"]
