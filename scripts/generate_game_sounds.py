#!/usr/bin/env python3
"""Generate the arcade's sound effects into each game package.

Effects are synthesised rather than shipped as found audio: no licensing, no
opaque binaries, and retuning one is a line of code. Re-run after editing:

    python scripts/generate_game_sounds.py
"""

from __future__ import annotations

import sys
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from matrix_audio.synth import layer, sequence, silence, tone, write_wav  # noqa: E402

PACKAGES = ROOT / "store_apps"


def blip(frequency: float, seconds: float = 0.06, **kwargs) -> array:
    return tone(frequency, seconds, attack=0.01, release=0.4, **kwargs)


def sweep(start: float, end: float, seconds: float, **kwargs) -> array:
    return tone(start, seconds, end_frequency=end, **kwargs)


def noise(seconds: float, volume: float = 0.8) -> array:
    return tone(0, seconds, wave_shape="noise", volume=volume, attack=0.005, release=0.6)


# Shared across every game, so the arcade sounds like one machine.
COMMON = {
    "start": lambda: sequence(blip(392, 0.07), blip(523, 0.07), blip(659, 0.12)),
    "pause": lambda: sequence(blip(440, 0.05), blip(330, 0.09)),
    "game_over": lambda: sequence(
        sweep(440, 220, 0.22, wave_shape="square"),
        sweep(220, 110, 0.34, wave_shape="square"),
    ),
    "select": lambda: blip(660, 0.05),
}

SOUNDS: dict[str, dict[str, object]] = {
    "core.tetris": {
        "move": lambda: blip(220, 0.03, volume=0.5),
        "rotate": lambda: blip(520, 0.04, volume=0.6),
        "lock": lambda: sequence(blip(160, 0.05, wave_shape="triangle"), noise(0.03, 0.3)),
        "line": lambda: sequence(blip(523, 0.07), blip(659, 0.07), blip(784, 0.14)),
        "tetris": lambda: sequence(blip(523, 0.06), blip(659, 0.06), blip(784, 0.06), blip(1046, 0.20)),
        "hold": lambda: sweep(300, 500, 0.08),
    },
    "core.pacman": {
        # The waka is two quick sweeps in opposite directions.
        "pellet": lambda: sequence(sweep(440, 620, 0.035, wave_shape="square", volume=0.5)),
        "power": lambda: sequence(sweep(220, 660, 0.14), sweep(660, 220, 0.14)),
        "eat_ghost": lambda: sweep(200, 900, 0.24, wave_shape="square"),
        "death": lambda: sequence(sweep(660, 110, 0.5, wave_shape="triangle"), noise(0.12, 0.4)),
        "level": lambda: sequence(blip(523, 0.08), blip(659, 0.08), blip(880, 0.16)),
    },
    "core.snake": {
        "eat": lambda: sweep(440, 880, 0.08),
        "turn": lambda: blip(300, 0.025, volume=0.35),
        "crash": lambda: sequence(noise(0.14, 0.7), sweep(200, 80, 0.22, wave_shape="triangle")),
    },
    "core.breakout": {
        "paddle": lambda: blip(440, 0.04),
        "brick": lambda: blip(700, 0.045, volume=0.8),
        "wall": lambda: blip(320, 0.03, volume=0.5),
        "lose_life": lambda: sweep(400, 120, 0.3, wave_shape="triangle"),
        "launch": lambda: sweep(300, 700, 0.1),
    },
    "core.invaders": {
        "shoot": lambda: sweep(900, 300, 0.09, wave_shape="square", volume=0.7),
        "hit": lambda: sequence(noise(0.09, 0.8), blip(180, 0.05, wave_shape="triangle")),
        "march": lambda: blip(110, 0.07, wave_shape="triangle", volume=0.7),
        "player_hit": lambda: sequence(noise(0.18, 0.9), sweep(240, 70, 0.3, wave_shape="triangle")),
        "wave": lambda: sequence(blip(440, 0.08), blip(587, 0.08), blip(740, 0.16)),
    },
    "core.flappy": {
        "flap": lambda: sweep(600, 900, 0.05, volume=0.6),
        "score": lambda: sequence(blip(784, 0.05), blip(1046, 0.09)),
        "hit": lambda: sequence(noise(0.1, 0.8), sweep(300, 90, 0.26, wave_shape="triangle")),
    },
    "core.pong": {
        "paddle": lambda: blip(520, 0.04),
        "wall": lambda: blip(340, 0.035, volume=0.6),
        "point": lambda: sequence(blip(660, 0.08), blip(880, 0.14)),
    },
    "core.connect4": {
        "move": lambda: blip(320, 0.03, volume=0.45),
        "drop": lambda: sweep(700, 260, 0.14, wave_shape="triangle"),
        "win": lambda: sequence(blip(523, 0.09), blip(659, 0.09), blip(784, 0.09), blip(1046, 0.22)),
    },
    "core.tron": {
        "turn": lambda: blip(520, 0.025, volume=0.4),
        "crash": lambda: sequence(noise(0.16, 0.9), sweep(300, 70, 0.3, wave_shape="triangle")),
        "win": lambda: sequence(blip(660, 0.07), blip(880, 0.07), blip(1175, 0.16)),
    },
    "core.roadrash": {
        "swing": lambda: sweep(700, 300, 0.07, wave_shape="noise", volume=0.6),
        "knockdown": lambda: sequence(noise(0.12, 0.9), sweep(260, 80, 0.24, wave_shape="triangle")),
        "crash": lambda: sequence(noise(0.24, 1.0), sweep(340, 60, 0.36, wave_shape="triangle")),
        "win": lambda: sequence(blip(523, 0.09), blip(659, 0.09), blip(880, 0.09), blip(1046, 0.22)),
    },
    "core.kong": {
        "jump": lambda: sweep(300, 620, 0.09, volume=0.6),
        "climb": lambda: blip(240, 0.03, volume=0.35),
        "barrel": lambda: sweep(180, 120, 0.12, wave_shape="triangle", volume=0.6),
        "point": lambda: sequence(blip(784, 0.05), blip(1046, 0.08)),
        "hammer": lambda: sequence(blip(523, 0.06), blip(784, 0.06), blip(1046, 0.12)),
        "smash": lambda: sequence(noise(0.08, 0.9), blip(150, 0.06, wave_shape="triangle")),
        "hit": lambda: sequence(sweep(520, 90, 0.36, wave_shape="triangle"), noise(0.1, 0.5)),
        "level": lambda: sequence(blip(440, 0.07), blip(587, 0.07), blip(880, 0.14)),
        "win": lambda: sequence(blip(523, 0.1), blip(659, 0.1), blip(784, 0.1), blip(1046, 0.26)),
    },
    "core.chess": {
        "move": lambda: blip(300, 0.025, volume=0.35),
        "pick": lambda: blip(560, 0.04, volume=0.6),
        "place": lambda: sequence(blip(200, 0.04, wave_shape="triangle"), noise(0.02, 0.25)),
        "capture": lambda: sequence(noise(0.06, 0.6), blip(160, 0.07, wave_shape="triangle")),
        "deny": lambda: blip(140, 0.06, wave_shape="square", volume=0.4),
        "win": lambda: sequence(blip(523, 0.1), blip(659, 0.1), blip(784, 0.1), blip(1046, 0.24)),
    },
    "core.battleship": {
        "move": lambda: blip(300, 0.03, volume=0.4),
        "miss": lambda: sequence(noise(0.14, 0.45), blip(180, 0.07, wave_shape="triangle", volume=0.5)),
        "hit": lambda: sequence(noise(0.2, 0.9), sweep(320, 90, 0.26, wave_shape="triangle")),
        "sunk": lambda: sequence(noise(0.24, 0.9), sweep(240, 60, 0.42, wave_shape="triangle")),
        "win": lambda: sequence(blip(523, 0.09), blip(784, 0.09), blip(1046, 0.2)),
    },
}


#: What the loudest effect in the whole set should peak at, of 32767.
#:
#: Synthesised at their natural levels the effects topped out around a third
#: of full scale, so every game was quiet and the volume control had to make
#: up the difference - which it cannot do past 100.
TARGET_PEAK = 29000


def amplify(samples: array, gain: float) -> array:
    """Scale a waveform, clipping rather than wrapping."""
    return array("h", [max(-32768, min(32767, int(value * gain))) for value in samples])


def main() -> int:
    if not PACKAGES.is_dir():
        print(f"no packages at {PACKAGES}")
        return 1

    # Build everything first, so one gain can be found for the whole set. A
    # per-file normalisation would flatten the dynamics instead: a move blip
    # is meant to sit under a game-over fanfare, not match it.
    built: list[tuple[Path, str, array]] = []
    for package in sorted(PACKAGES.iterdir()):
        if not package.is_dir():
            continue
        effects = dict(COMMON)
        effects.update(SOUNDS.get(package.name, {}))  # type: ignore[arg-type]
        for name, build in effects.items():
            built.append((package / "sounds", name, build()))  # type: ignore[operator]
        print(f"  {package.name:20s} {len(effects)} effects")

    peak = max((max((abs(v) for v in samples), default=0) for _, _, samples in built), default=0)
    gain = TARGET_PEAK / peak if peak else 1.0

    for directory, name, samples in built:
        write_wav(directory / f"{name}.wav", amplify(samples, gain))
    print(f"{len(built)} sound files written, gain {gain:.2f}x to peak {TARGET_PEAK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
