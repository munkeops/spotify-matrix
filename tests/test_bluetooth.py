

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
