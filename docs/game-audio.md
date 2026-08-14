# Game Audio

The arcade has sound. Effects are **generated**, not sampled: a small chiptune
synth writes them into each game package, so retuning a blip is editing a line
rather than finding new audio, and every game sits in the same sonic world.

## Turning it on

**Settings → Game sound**. Pick an output if the Pi has more than one, set the
volume, and press **Test** to hear one immediately — that works before any game
is running, so you can prove the sound card before blaming a game.

Turning it on restarts whatever is on the panel, because the runtime opens the
sound card when it launches.

## How it reaches the speaker

One long-lived `aplay` reads raw PCM from a pipe, fed by a mixer that sums the
active effects. That matters: spawning a process per blip is both slow and
unable to overlap, so a Pac-Man pellet during a ghost turning blue would cut one
of them off. Everything degrades to silence rather than raising, so a matrix
with no sound card still plays its games.

The container needs `/dev/snd` and ALSA tools; the compose file and image
already have both.

```bash
aplay -l                                        # on the Pi: any cards at all?
docker compose exec spotify-matrix aplay -L     # what the container can see
```

## Sound in a game app

A game just plays a name. Whether audio exists is the host's problem:

```python
def _eat(self) -> None:
    self.audio.play("pellet", 0.5)      # optional volume, 0.0 to 1.0
```

Drop WAVs in `sounds/` inside the package and they load automatically, named
after the file. Without a host engine `self.audio` is `SilentAudio` and every
call is a cheap no-op, which is why a app can call `play` unconditionally and
why tests and preview tiles never make a noise.

Every game ships the shared set — `start`, `pause`, `game_over`, `select` — so
the arcade sounds like one machine, plus its own effects.

## Retuning a sound

Effects live in `scripts/generate_game_sounds.py` as a line each:

```python
"eat": lambda: sweep(440, 880, 0.08),
"crash": lambda: sequence(noise(0.14, 0.7), sweep(200, 80, 0.22, wave_shape="triangle")),
```

Edit and regenerate:

```bash
python scripts/generate_game_sounds.py
```

The synth has `tone` (with optional pitch sweep and `square`, `triangle`, `saw`,
`noise` or `sine` shapes), `sequence` to play parts in turn, `layer` to stack
them, and `silence`. A test asserts every sound a game asks for is one it ships,
so a typo fails the build instead of going quietly silent forever.
