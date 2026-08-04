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

### Which pins? You mostly do not get to choose

Hardware I²C on a Pi is wired to fixed pins. You pick a **bus**, and the bus
determines the pins — you cannot point bus 1 at arbitrary GPIOs.

| Bus | SDA | SCL | Notes |
|---|---|---|---|
| `i2c-1` | GPIO 2 — physical pin **3** | GPIO 3 — physical pin **5** | The default, and what to use |
| `i2c-0` | GPIO 0 — pin 27 | GPIO 1 — pin 28 | Reserved for HAT ID EEPROMs, do not use |
| `i2c-3`…`i2c-6` | various | various | Pi 4/5 only, each needs its own overlay |

**So: SDA to physical pin 3, SCL to physical pin 5, and set `bus` to 1.** If you
wired to different pins, move the wires — that is much the easiest fix.

If you cannot move them (the matrix HAT is using pin 3 or 5, say), add a
*software* I²C bus on whatever pins you do have free. Put this in
`/boot/firmware/config.txt` (`/boot/config.txt` on older releases), substituting
your GPIO numbers, then reboot:

```text
dtoverlay=i2c-gpio,bus=3,i2c_gpio_sda=23,i2c_gpio_scl=24
```

That creates `/dev/i2c-3`; set `bus` to `3` in the joystick settings. Software
I²C is slower, which does not matter for a joystick polled 30 times a second.

Note the RGB matrix HAT already claims a lot of the header. Check its pinout
before choosing, and avoid anything it drives.

### Enable and check the bus

```bash
sudo raspi-config          # Interface Options -> I2C -> Yes, then reboot
sudo apt install -y i2c-tools
i2cdetect -y 1             # the module should appear at 5a
```

### If it still does not work

Open **Settings → Mini-joystick → Detect module** in the app. It scans every
bus, lists what answered, and tells you the next step. What it is checking, in
the order things usually go wrong:

| Symptom | Cause | Fix |
|---|---|---|
| "smbus2 library is missing" | The I²C library is not installed | Rebuild the container, or `pip install smbus2` |
| "No I2C bus exists" | I²C not enabled, or not mapped into Docker | `raspi-config`, reboot, and confirm `devices: - /dev/i2c-1:/dev/i2c-1` in `docker-compose.yml` |
| Bus present but empty | Wrong pins, no power, or SDA/SCL swapped | SDA to pin 3, SCL to pin 5, V to 5V, G to ground |
| Other addresses but not `0x5a` | Wiring is fine, the module is not answering | Check the module's power LED is solid red; check the level shifter |
| Answers on a different bus | The app is set to the wrong bus | Change **I²C bus** in the same panel |

Docker note: the container needs the bus mapped. This repo's `docker-compose.yml`
already does it, but a hand-rolled `docker run` needs `--device /dev/i2c-1`.

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
