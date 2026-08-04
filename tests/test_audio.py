from __future__ import annotations

import struct
import types
import wave
from array import array
from pathlib import Path

import pytest

import matrix_games as mg
from assistant_matrix_sdk.audio import SilentAudio
from matrix_audio import AudioEngine
from matrix_audio.mixer import MAX_VOICES, Mixer
from matrix_audio.output import list_output_devices
from matrix_audio.synth import SAMPLE_RATE, layer, read_wav, sequence, silence, tone, write_wav

ALL_GAMES = sorted(mg.discover())


class Recorder:
    """Stands in for an engine so a game's sound calls can be observed."""

    def __init__(self) -> None:
        self.played: list[str] = []

    def play(self, name: str, volume: float = 1.0) -> bool:
        self.played.append(name)
        return True

    def known(self) -> list[str]:
        return []


# --- synth ---------------------------------------------------------------


def test_a_tone_is_the_length_it_says():
    samples = tone(440, 0.1)
    assert len(samples) == pytest.approx(SAMPLE_RATE * 0.1, rel=0.01)
    assert any(samples), "a tone should not be silent"
    assert max(abs(value) for value in samples) <= 32767


def test_the_envelope_fades_in_and_out():
    samples = tone(440, 0.2, attack=0.2, release=0.4)
    head = abs(samples[0])
    middle = max(abs(value) for value in samples[len(samples) // 3 : len(samples) // 2])
    tail = abs(samples[-1])
    assert head < middle and tail < middle, "a blip should not start or end abruptly"


@pytest.mark.parametrize("shape", ["square", "triangle", "saw", "noise", "sine"])
def test_every_waveform_makes_sound(shape):
    assert any(tone(300, 0.05, wave_shape=shape))


def test_a_sweep_changes_pitch():
    flat = tone(400, 0.15)
    swept = tone(200, 0.15, end_frequency=1200)
    assert list(flat) != list(swept)


def test_silence_is_silent():
    assert not any(silence(0.05))


def test_sequence_and_layer():
    first, second = tone(400, 0.05), tone(600, 0.05)
    assert len(sequence(first, second)) == len(first) + len(second)
    mixed = layer(first, second)
    assert len(mixed) == max(len(first), len(second))
    assert max(abs(v) for v in mixed) <= 32767, "layering must clip, not wrap"


def test_wav_round_trip(tmp_path):
    path = tmp_path / "blip.wav"
    original = tone(440, 0.05)
    write_wav(path, original)

    assert path.exists()
    restored = read_wav(path)
    assert list(restored) == list(original)


def test_a_stereo_file_is_read_as_mono(tmp_path):
    path = tmp_path / "stereo.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(struct.pack("<4h", 100, 300, -100, -300))

    samples = read_wav(path)
    assert list(samples) == [200, -200], "channels are averaged"


def test_an_odd_sample_rate_is_resampled(tmp_path):
    path = tmp_path / "slow.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE // 2)
        handle.writeframes(array("h", [1000] * 100).tobytes())

    assert len(read_wav(path)) == pytest.approx(200, rel=0.05)


# --- mixer ---------------------------------------------------------------


def test_an_unknown_sound_is_refused():
    mixer = Mixer()
    assert mixer.play("nope") is False
    assert mixer.active == 0


def test_playing_and_finishing():
    mixer = Mixer()
    mixer.load("blip", tone(440, 0.02))
    assert mixer.play("blip") is True
    assert mixer.active == 1

    rendered = mixer.render(int(SAMPLE_RATE * 0.02) + 64)
    assert any(rendered)
    assert mixer.active == 0, "a finished voice is dropped"


def test_silence_when_nothing_plays():
    mixer = Mixer()
    assert not any(mixer.render(128))


def test_sounds_overlap():
    mixer = Mixer()
    mixer.load("a", tone(440, 0.1))
    mixer.load("b", tone(660, 0.1))
    mixer.play("a")
    mixer.play("b")
    assert mixer.active == 2

    both = mixer.render(256)
    assert any(both), "two voices mix into one stream"


def test_the_mixer_has_a_voice_limit():
    mixer = Mixer()
    mixer.load("blip", tone(440, 0.5))
    started = [mixer.play("blip") for _ in range(MAX_VOICES + 5)]
    assert started.count(True) == MAX_VOICES
    assert started.count(False) == 5


def test_master_volume_scales_and_mutes():
    mixer = Mixer(volume=1.0)
    mixer.load("blip", tone(440, 0.05))
    mixer.play("blip")
    loud = max(abs(value) for value in array("h", mixer.render(512)))

    mixer.volume = 0.0
    mixer.play("blip")
    assert not any(mixer.render(512)), "zero volume is silence"
    assert loud > 0


def test_render_of_nothing_is_empty():
    assert Mixer().render(0) == b""


def test_loading_a_directory(tmp_path):
    write_wav(tmp_path / "one.wav", tone(400, 0.02))
    write_wav(tmp_path / "two.wav", tone(500, 0.02))
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")

    mixer = Mixer()
    assert sorted(mixer.load_directory(tmp_path)) == ["one", "two"]
    assert mixer.known() == ["one", "two"]


def test_a_broken_sound_file_is_skipped(tmp_path):
    write_wav(tmp_path / "good.wav", tone(400, 0.02))
    (tmp_path / "bad.wav").write_bytes(b"not a wav at all")

    mixer = Mixer()
    assert mixer.load_directory(tmp_path) == ["good"], "one bad file must not lose the rest"


# --- engine --------------------------------------------------------------


def test_a_disabled_engine_stays_quiet(tmp_path):
    write_wav(tmp_path / "blip.wav", tone(440, 0.02))
    engine = AudioEngine(enabled=False)
    engine.load_directory(tmp_path)

    assert engine.play("blip") is False
    assert engine.running is False


def test_an_enabled_engine_plays_into_the_mixer(tmp_path):
    write_wav(tmp_path / "blip.wav", tone(440, 0.02))
    engine = AudioEngine(enabled=True)
    engine.load_directory(tmp_path)

    assert engine.play("blip") is True
    assert engine.mixer.active == 1


def test_volume_is_clamped():
    engine = AudioEngine(enabled=True)
    engine.set_volume(5.0)
    assert engine.mixer.volume == 1.0
    engine.set_volume(-2.0)
    assert engine.mixer.volume == 0.0


def test_listing_devices_never_raises():
    assert isinstance(list_output_devices(), list)


# --- games ---------------------------------------------------------------


@pytest.mark.parametrize("game_id", ALL_GAMES)
def test_every_game_ships_its_sounds(game_id):
    spec = mg.discover()[game_id]
    files = sorted(path.stem for path in spec.sounds_dir.glob("*.wav"))
    assert files, f"{game_id} ships no sounds"
    # The shared set means the arcade sounds like one machine.
    for common in ("start", "pause", "game_over", "select"):
        assert common in files, f"{game_id} is missing {common}"


@pytest.mark.parametrize("game_id", ALL_GAMES)
def test_a_game_is_silent_by_default(game_id):
    game = mg.create_game(game_id, {}, seed=1)
    assert isinstance(game.audio, SilentAudio)
    # Calling play unconditionally has to be safe.
    assert game.audio.play("anything") is False


@pytest.mark.parametrize("game_id", ALL_GAMES)
def test_every_sound_a_game_asks_for_exists(game_id):
    """A typo in a game would otherwise be a silent no-op forever."""
    spec = mg.discover()[game_id]
    available = {path.stem for path in spec.sounds_dir.glob("*.wav")}

    source = (spec.package_dir / "renderer" / "widget.py").read_text(encoding="utf-8")
    import re

    asked = set(re.findall(r'self\.audio\.play\(\s*"([a-z_]+)"', source))
    missing = sorted(asked - available)
    assert not missing, f"{game_id} plays sounds it does not ship: {missing}"


def test_snake_makes_a_noise_when_it_eats():
    recorder = Recorder()
    game = mg.create_game("snake", {}, seed=1, audio=recorder)
    head_x, head_y = game.body[0]
    game.food = (head_x + 1, head_y)

    game._move()

    assert "eat" in recorder.played


def test_snake_crashing_is_audible():
    recorder = Recorder()
    game = mg.create_game("snake", {"walls": True}, seed=2, audio=recorder)
    game.body = [(0, 5), (1, 5)]
    game.direction = (-1, 0)

    game._move()

    assert game.game_over is True
    assert "crash" in recorder.played


def test_tetris_lines_and_locks_sound_different():
    tetris = mg.plugin_module("tetris")
    recorder = Recorder()
    game = mg.create_game("tetris", {}, seed=1, audio=recorder)

    game.hard_drop()
    assert "lock" in recorder.played
    assert "line" not in recorder.played

    recorder.played.clear()
    for column in range(tetris.TETRIS_COLS):
        game.board[tetris.TETRIS_ROWS - 1][column] = "" if column == 0 else "J"
    game.piece_type, game.rotation, game.piece_x, game.piece_y = "I", 1, -2, 0
    game.hard_drop()
    assert "line" in recorder.played


def test_flappy_flaps_and_dies_audibly():
    recorder = Recorder()
    game = mg.create_game("flappy", {}, seed=3, audio=recorder)

    game.command("flap")
    assert "flap" in recorder.played

    game.bird_y = 500.0
    game.step(0.05)
    assert "hit" in recorder.played


APLAY_L = """default
    Playback/recording through the PulseAudio sound server
null
    Discard all samples (playback) or generate zero samples (capture)
sysdefault:CARD=vc4hdmi0
    vc4-hdmi-0, MAI PCM i2s-hifi-0
    Default Audio Device
hw:CARD=vc4hdmi0,DEV=0
    vc4-hdmi-0, MAI PCM i2s-hifi-0
    Direct hardware device without any conversions
plughw:CARD=vc4hdmi0,DEV=0
    vc4-hdmi-0, MAI PCM i2s-hifi-0
    Hardware device with all software conversions
dmix:CARD=vc4hdmi0,DEV=0
    vc4-hdmi-0, MAI PCM i2s-hifi-0
    Direct sample mixing device
hw:CARD=vc4hdmi1,DEV=0
    vc4-hdmi-1, MAI PCM i2s-hifi-0
    Direct hardware device without any conversions
bluealsa:DEV=F4:6A:D7:6E:8C:90,PROFILE=a2dp
    JBL Flip 5
    Bluetooth Audio
"""


def _fake_aplay(monkeypatch, listing=APLAY_L):
    from matrix_audio import output as module

    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/aplay")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: types.SimpleNamespace(stdout=listing, returncode=0),
    )
    return module


def test_output_list_hides_the_plumbing(monkeypatch):
    """One speaker should be one entry, not four ways of reaching it."""
    module = _fake_aplay(monkeypatch)

    devices = module.list_output_devices()
    names = [device["name"] for device in devices]

    assert not any(name.startswith(("plughw:", "dmix:", "sysdefault:")) for name in names)
    assert not any(name.startswith("null") for name in names)
    # Two HDMI ports, one Bluetooth speaker, one default.
    assert sum(1 for device in devices if device["kind"] == "hdmi") == 2


def test_output_list_names_things_a_person_would_recognise(monkeypatch):
    module = _fake_aplay(monkeypatch)

    labels = {device["kind"]: device["label"] for device in module.list_output_devices()}

    assert labels["bluetooth"] == "JBL Flip 5"
    assert labels["hdmi"].startswith("HDMI")
    assert labels["default"] == "System default"


def test_bluetooth_speaker_is_offered_first(monkeypatch):
    """It is the one you went to the trouble of pairing."""
    module = _fake_aplay(monkeypatch)

    assert module.list_output_devices()[0]["kind"] == "bluetooth"


def test_the_raw_list_is_still_reachable(monkeypatch):
    module = _fake_aplay(monkeypatch)

    raw = module.list_output_devices(include_plumbing=True)

    assert any(device["name"].startswith("dmix:") for device in raw)
    assert any(device["plumbing"] for device in raw)


def test_test_button_plays_a_sound_the_panel_offered():
    """The panel listed the active game's effects, the test loaded another
    game's directory, so picking one answered "No sound called flap"."""
    from src.domain.services.audio_service import audio_service

    offered = audio_service.sounds()
    assert offered, "some game ships effects"

    spec = audio_service._test_spec()
    shipped = {path.stem for path in spec.sounds_dir.glob("*.wav")}

    assert set(offered) <= shipped, "every offered sound is one the test can find"


REAL_PI = """default
    Playback through the default device
sysdefault
    Default Audio Device
bluealsa
    Bluetooth Audio Hub
bluealsa:DEV=F4:6A:D7:6E:8C:90,PROFILE=a2dp
    JBL Flip 5, trusted, A2DP (playback)
    Bluetooth Audio
hw:CARD=vc4hdmi0,DEV=0
    vc4-hdmi-0, MAI PCM i2s-hifi-0
sysdefault:CARD=vc4hdmi0
    vc4-hdmi-0, MAI PCM i2s-hifi-0
plughw:CARD=vc4hdmi0,DEV=0
    vc4-hdmi-0, MAI PCM i2s-hifi-0
hw:CARD=vc4hdmi1,DEV=0
    vc4-hdmi-1, MAI PCM i2s-hifi-0
"""


def test_a_real_pi_listing_becomes_four_choices(monkeypatch):
    """What a Pi with bluealsa and two HDMI ports should offer."""
    module = _fake_aplay(monkeypatch, REAL_PI)

    listed = [(device["kind"], device["label"]) for device in module.list_output_devices()]

    assert listed == [
        ("bluetooth", "JBL Flip 5"),
        ("hdmi", "HDMI 1"),
        ("hdmi", "HDMI 2"),
        ("default", "System default"),
    ]


def test_the_bare_bluealsa_alias_is_dropped_once_a_speaker_is_named(monkeypatch):
    """It means "whichever speaker", so beside a real one it reads as a
    duplicate - which is how the panel came to show bluealsa twice."""
    module = _fake_aplay(monkeypatch, REAL_PI)

    bluetooth = [d for d in module.list_output_devices() if d["kind"] == "bluetooth"]

    assert len(bluetooth) == 1
    assert bluetooth[0]["name"].startswith("bluealsa:DEV=")


def test_the_bare_alias_survives_when_it_is_all_there_is(monkeypatch):
    module = _fake_aplay(monkeypatch, "bluealsa\n    Bluetooth Audio Hub\ndefault\n    Default\n")

    labels = [d["label"] for d in module.list_output_devices() if d["kind"] == "bluetooth"]

    assert labels == ["Bluetooth speaker"]


def test_bare_sysdefault_is_plumbing_too(monkeypatch):
    """The filter matched "sysdefault:" with the colon, so the bare entry -
    which is what a Pi actually lists - went straight through."""
    module = _fake_aplay(monkeypatch, REAL_PI)

    assert not any(d["name"] == "sysdefault" for d in module.list_output_devices())


def test_the_api_actually_sends_the_label_and_kind():
    """The panel showed raw PCM strings because the response model named only
    `name` and `description`, so pydantic dropped everything else."""
    from src.domain.models.api_schemas import AudioDevice

    device = AudioDevice(
        name="bluealsa:DEV=F4:6A:D7:6E:8C:90,PROFILE=a2dp",
        description="JBL Flip 5",
        label="JBL Flip 5",
        kind="bluetooth",
    )
    payload = device.model_dump()

    assert payload["label"] == "JBL Flip 5"
    assert payload["kind"] == "bluetooth"


def test_output_is_wrapped_so_alsa_converts_the_format():
    """The mixer renders 22050Hz mono. HDMI accepts that; the bluealsa PCM
    does not, because A2DP is 44100Hz stereo - so a speaker that connected
    perfectly well played nothing at all."""
    from matrix_audio.output import plug_device

    assert plug_device("") == "", "the default device is left alone"
    assert plug_device("plughw:CARD=x") == "plughw:CARD=x", "already converting"
    assert plug_device("hw:CARD=vc4hdmi0,DEV=0") == 'plug:{SLAVE="hw:CARD=vc4hdmi0,DEV=0"}'


def test_a_bluealsa_name_survives_being_wrapped():
    """`plug:bluealsa:DEV=x,PROFILE=a2dp` would have ALSA read PROFILE as an
    argument to plug rather than to bluealsa, so the slave is named."""
    from matrix_audio.output import plug_device

    wrapped = plug_device("bluealsa:DEV=F4:6A:D7:6E:8C:90,PROFILE=a2dp")

    assert wrapped == 'plug:{SLAVE="bluealsa:DEV=F4:6A:D7:6E:8C:90,PROFILE=a2dp"}'
    assert "PROFILE=a2dp" in wrapped.split('SLAVE="', 1)[1]


def test_the_command_asks_for_the_wrapped_device():
    from matrix_audio.mixer import Mixer
    from matrix_audio.output import AlsaOutput

    output = AlsaOutput(Mixer(), device="bluealsa")

    command = output._command()

    assert command[command.index("-D") + 1] == 'plug:{SLAVE="bluealsa"}'


def test_the_test_button_admits_when_nothing_came_out(monkeypatch):
    """It reported "Playing death." for a device that never opened."""
    from src.domain.services import audio_service as module

    class DeadEngine:
        error = "ALSA: Channels count non available"

        def __init__(self, *args, **kwargs):
            pass

        def load_directory(self, *args, **kwargs):
            return []

        def start(self):
            return None

        def play(self, name):
            return True

        def stop(self):
            return None

    monkeypatch.setattr(module, "AudioEngine", DeadEngine)
    result = module.audio_service.play_test("death")

    assert result["ok"] is False
    assert "Channels count non available" in result["message"]
