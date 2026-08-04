# Mini-Joystick Module

Python SDK and Assistant Matrix integration for the NULLLAB mini-joystick
module ([nulllaborg/mini-joystick-module](https://github.com/nulllaborg/mini-joystick-module)):
one analog stick plus five buttons (A, B, C, D, and OK under the stick), read
over I²C.

## Wiring

> **The module is a 5V device and the Pi's GPIO is 3.3V only.**
>
> The board is specified for DC 5V, and its I²C lines are pulled up to its own
> supply. Wiring SDA/SCL straight to the Pi puts 5V on 3.3V-tolerant pins,
> which can damage the SoC. Use a **bidirectional I²C level shifter** (any
> BSS138-based Qwiic/Stemma-style board works) between the module and the Pi.
> Power the module side from the Pi's 5V pin and the Pi side from 3.3V.

| Module | Level shifter | Pi |
|---|---|---|
| `V` | HV | 5V (pin 2 or 4) |
| `G` | GND | GND (pin 6) |
| `SDA` | HV1 → LV1 | GPIO 2 / SDA1 (pin 3) |
| `SCL` | HV2 → LV2 | GPIO 3 / SCL1 (pin 5) |

Enable I²C once with `sudo raspi-config` (Interface Options → I2C), then
confirm the module answers at `0x5a`:

```bash
sudo apt install -y i2c-tools python3-smbus
i2cdetect -y 1
```

## Protocol

Taken from the vendor's Arduino library (`JoystickHandle.h` / `.cpp`, release
V1.0.0). The README documents the Arduino API but not the registers, so these
values come from the library source.

| Register | Meaning |
|---|---|
| `0x10` | Stick X, `0`–`255`, centre `128` |
| `0x11` | Stick Y, `0`–`255`, centre `128` |
| `0x12` / `0x13` | Right stick X/Y — defined by the library, unpopulated on this board |
| `0x20` | Button OK |
| `0x21` | Button C |
| `0x22` | Button A |
| `0x23` | Button B |
| `0x24` | Button D |

Button values: `0` press-down, `1` press-up, `2` repeat, `3` single-click,
`4` double-click, `5` long-press-start, `6` long-press-hold, `8` idle. The
module answers `0xFF` when asked for a button that does not exist.

A read is *write the register byte, STOP, then read one byte* — two
transactions, which is what the Arduino library does. `SMBusTransport` does the
same by default; pass `combined=True` to use a repeated START instead.

> Note that `0xFF` is **not** an error sentinel for the axes: `255` is a valid
> full-deflection reading. The transport layer reports a failed read as `None`
> so full deflection is never mistaken for a dead bus.

## SDK

```python
from mini_joystick import Button, MiniJoystick, SMBusTransport

with MiniJoystick(SMBusTransport(bus=1)) as pad:
    state = pad.read()
    print(state.stick.direction(), state.stick.x, state.stick.y)
    print(state.is_held(Button.A), state.clicked(Button.OK))
```

`MiniJoystick` takes `deadzone`, `invert_x` and `invert_y` so you can match how
the module ends up mounted.

Edge detection and auto-repeat come from `JoystickReader`, which turns levels
into discrete events:

```python
from mini_joystick import JoystickReader, MiniJoystick, SMBusTransport

reader = JoystickReader(MiniJoystick(SMBusTransport()))
for event in reader.stream(poll_hz=30):
    print(event.kind, event.name, "repeat" if event.repeat else "")
```

Events are `direction` (once on push, then repeating while held), `button`
(only on a change), and `disconnected` / `reconnected`.

Develop without hardware using `FakeTransport`:

```python
from mini_joystick import FakeTransport, MiniJoystick
from mini_joystick.protocol import REG_LEFT_X

transport = FakeTransport({REG_LEFT_X: 255, 0x11: 128})
assert MiniJoystick(transport).read_stick().direction().value == "right"
```

## Assistant Matrix integration

Enable it from the API (or set `joystick.enabled` in `data/config.json`):

```bash
curl -X POST http://<pi-host>:3000/api/joystick/config \
  -H "Content-Type: application/json" \
  -d '{"config":{"enabled":true,"bus":1,"deadzone":0.35}}'
curl http://<pi-host>:3000/api/joystick
```

The service polls on a background thread at 30 Hz and behaves differently
depending on what is on the panel:

**While a game is running** the joystick drives it through the same command
queue the web gamepad uses. Each game declares its own actions, so the binding
adapts rather than assuming a d-pad:

| Input | Pac-Man / Snake | Tetris | Breakout / Invaders | Flappy | Connect Four |
|---|---|---|---|---|---|
| Stick ←/→ | move | move | move | — | move cursor |
| Stick ↑ | move | rotate | fire | flap | — |
| Stick ↓ | move | soft drop | — | — | drop |
| A | — | hard drop | fire | flap | drop |
| B | — | rotate back | fire | flap | — |
| C | — | hold | — | — | — |
| OK | pause | pause | pause | pause | pause |
| OK held | restart | restart | restart | restart | restart |
| D held | restart | restart | restart | restart | restart |

Only movement auto-repeats when the stick is held — a held stick never spins a
Tetris piece or machine-guns a drop.

**When no game is running** the stick walks the plugin list and applies as it
goes, so you can flick through Spotify, the clock, weather and the rest without
touching a phone:

| Input | Action |
|---|---|
| Stick →/↓ | next plugin |
| Stick ←/↑ | previous plugin |
| OK or A | re-apply the current plugin |
| B | jump to the arcade |
| D held | start/stop the matrix runtime |

### Settings

`joystick` in `data/config.json`:

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `false` | Start the poller with the service |
| `bus` | `1` | Linux I²C bus number |
| `address` | `90` (`0x5A`) | Device address |
| `deadzone` | `0.35` | Fraction of deflection before a push registers |
| `invertX` / `invertY` | `false` | Flip an axis to match the mounting |
| `repeatDelay` | `0.28` | Seconds held before auto-repeat starts |
| `repeatInterval` | `0.09` | Seconds between repeats |
| `combinedRead` | `false` | Use a repeated START instead of write-STOP-read |

The poller survives an unplugged module: it reports `disconnected`, retries the
bus every five seconds, and logs `reconnected` when the module answers again.
