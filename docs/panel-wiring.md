# Panel wiring

The same install drives a panel on an Adafruit HAT and a panel wired
straight to the Pi's header. Which one it expects is a setting: **Settings →
Matrix Hardware → Wiring**.

Picking a wiring fills in three values and nothing else:

| Setting | Why it belongs to the wiring |
| --- | --- |
| `hardwareMapping` | Which GPIO carries which signal. |
| `noHardwarePulse` | Whether OE landed on a pin the Pi can pulse in hardware. |
| `gpioSlowdown` | A starting point for how hard the Pi may drive the lines. |

Everything else — rows, columns, chain, brightness, rotation — describes the
panel rather than how it is plugged in, and survives switching untouched.

Save applies it. All three are constructor arguments to the panel driver, so
the matrix restarts and blanks for a moment.

## The drivers

### Direct wiring (`regular`)

Panel to header, no board in between. BCM pins:

| R1 | G1 | B1 | R2 | G2 | B2 | A | B | C | D | E | CLK | LAT | OE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 27 | 7 | 8 | 9 | 10 | 22 | 23 | 24 | 25 | 15 | 17 | 4 | 18 |

**E on GPIO 15** is the line a 64×64 panel needs and a 32-row panel does
not. If the picture arrives as two half-height copies, that is the one to
check first.

OE on GPIO 18 means the Pi's hardware pulse generator can drive it, so this
wiring gets the best refresh available — around 135 Hz on a Pi 4 at the
default settings.

The slowdown starts at 2, which is what the library picks for a Pi 4 by
itself. A direct connection is clean, not fast: a Pi 4 switches its GPIOs
quickly enough that the panel's shift registers miss edges, and the picture
shakes. **A shaking or tearing picture is the slowdown, nine times out of
ten** — raise it by one before changing anything else. On a Pi 3 or older,
1 is right and worth trying.

Two things on the Pi itself, both required:

```bash
# /boot/firmware/config.txt
dtparam=audio=off

# and stop the module reloading
echo 'blacklist snd_bcm2835' | sudo tee /etc/modprobe.d/blacklist-rgb-matrix.conf
```

The onboard analogue audio holds the same hardware the panel needs for
timing. Game sound goes out over Bluetooth, which does not use it.

Worth adding once it is working:

```
# /boot/firmware/cmdline.txt, appended to the single line
isolcpus=3
```

That hands one core to the panel driver so scheduling cannot jitter the
refresh.

### Adafruit HAT (`adafruit-hat`)

The HAT or Bonnet as sold. The board does the wiring; the pin table in the
settings page is for reference only.

| R1 | G1 | B1 | R2 | G2 | B2 | A | B | C | D | E | CLK | LAT | OE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 13 | 6 | 12 | 16 | 23 | 22 | 26 | 27 | 20 | 24 | 17 | 21 | 4 |

OE is on GPIO 4, which the pulse generator cannot reach, so this wiring is
stuck with software pulsing. The panel will look dimmer than the same one
wired directly. That is the board, not a setting.

### Adafruit HAT with the PWM mod (`adafruit-hat-pwm`)

One wire soldered between GPIO 4 and GPIO 18 moves OE onto a pin the
hardware can pulse. Identical to the HAT above in every other respect, and
the single biggest brightness win available to a HAT.

## Adding another

`matrix_display/drivers.py` holds the definitions. A new one is a `Driver`
entry added to `DRIVERS`; the settings page and its pin table are generated
from that, and the tests check every signal is wired, that no two share a
pin, and that `no_hardware_pulse` agrees with where OE landed.

Pin numbers are taken from `lib/hardware-mapping.c` in
hzeller/rpi-rgb-led-matrix, which is the code that actually drives them.
