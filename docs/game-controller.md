# Bluetooth Game Controller

Any standard gamepad — Xbox, PlayStation, 8BitDo, a cheap USB pad — can drive
the matrix games. BlueZ pairs it, the kernel exposes it as an input device, and
Assistant Matrix reads it and feeds the same command queue the on-screen pad
and the mini-joystick use.

## Before you scan

Pairing needs three things on the Pi. The Bluetooth panel checks all of them and
says which one is missing.

```bash
systemctl is-active bluetooth       # want: active
rfkill list bluetooth               # "Soft blocked: yes" means it is disabled
sudo rfkill unblock bluetooth       # ...so unblock it
bluetoothctl show                   # expect a controller, and Powered: yes
```

`systemctl status` pipes into a pager, which both truncates the log lines and
swallows anything you typed after it on the same line. To read what bluetoothd
is actually complaining about:

```bash
sudo journalctl -u bluetooth -n 30 --no-pager
```

Common lines and what they mean:

| Log line | Meaning |
|---|---|
| `Failed to set mode: Blocked through rfkill` | The adapter is blocked; `sudo rfkill unblock bluetooth` |
| `Failed to start discovery: ... NotReady` | The adapter is off; `bluetoothctl power on` |
| `Failed to connect: ... br-connection-profile-unavailable` | Paired, but nothing on the host can use it — for a speaker that means no A2DP sink |
| `Failed to add UUID` / `Failed to set privacy` | Harmless startup noise |

### Powered: no, PowerState: off-enabling

The adapter was blocked and is coming back up. Unblocking is not instant, so
give it a second:

```bash
sudo rfkill unblock bluetooth
bluetoothctl power on
bluetoothctl show | grep -E "Powered|PowerState"     # want: yes / on
```

An adapter blocked at boot stays blocked, and a scan then finds nothing with no
obvious reason, so make it stick:

```bash
systemctl is-enabled systemd-rfkill.service          # want: enabled
sudo systemctl enable --now systemd-rfkill.service
```

systemd remembers the unblocked state in `/var/lib/systemd/rfkill/` and restores
it on boot. If it still comes back blocked, something is re-blocking it — check
for a `bluetooth` line in `/etc/rc.local` or a conflicting service.

Nothing needs enabling in `config.txt` and no reboot is required — unlike I2C,
Bluetooth is on by default on a Pi with onboard radio. If `bluetoothctl show`
says "No default controller", the daemon is down or the adapter is blocked.

**The device has to be advertising.** Nothing appears in a scan unless the
controller or speaker is actively in pairing mode, and most only advertise for
a minute or two before giving up. Put it in pairing mode, *then* press Scan.

Scanning is not passive: the app runs a timed discovery when you press Scan and
lists what answered. Devices that were not advertising during that window will
not be there, so re-arm the device and scan again.

## Pairing

1. Put the controller in pairing mode.
   - Xbox: hold the small **pair** button on the top until the Xbox light
     flashes quickly.
   - PlayStation: hold **PS + Share** until the light bar flashes.
   - 8BitDo: hold **Start**, then the pair button.
2. Open **Settings → Bluetooth** in the app, press **Scan**, and connect to the
   controller when it appears.
3. Once connected, open **Settings → Game controller** and turn on
   **Use a game controller**.

The panel lists every controller the kernel can see and says what to do if the
list is empty. Pairing survives a reboot, so this is a one-off.

Prefer the command line, or the pad will not pair from the UI:

```bash
bluetoothctl
> power on
> agent on
> scan on          # wait for the controller's MAC to appear
> pair AA:BB:CC:DD:EE:FF
> trust AA:BB:CC:DD:EE:FF     # trust makes it reconnect by itself
> connect AA:BB:CC:DD:EE:FF
> quit
```

Confirm the kernel picked it up:

```bash
ls -l /dev/input/event*
cat /proc/bus/input/devices | grep -A 4 Name
```

## Xbox controllers need ERTM disabled

An Xbox Wireless Controller will not stay connected on Linux with Bluetooth
ERTM enabled. It typically pairs and drops straight away, or refuses to connect
at all. This is a kernel setting, not something the app can change:

```bash
# Permanent
echo 'options bluetooth disable_ertm=1' | sudo tee /etc/modprobe.d/bluetooth.conf
sudo reboot

# Or try it right now, without rebooting
echo 1 | sudo tee /sys/module/bluetooth/parameters/disable_ertm
```

Then forget any half-finished pairing and start again:

```bash
bluetoothctl remove AA:BB:CC:DD:EE:FF
bluetoothctl --timeout 15 scan on
bluetoothctl pair AA:BB:CC:DD:EE:FF
bluetoothctl trust AA:BB:CC:DD:EE:FF
bluetoothctl connect AA:BB:CC:DD:EE:FF
```

Hold the small **pair** button on the top edge until the Xbox light flashes
*quickly* — a slow blink means it is looking for a console, not a computer.

## A scan is mostly nameless addresses

That is normal. A scan hears every nearby radio, and a device reports its name a
moment after it first appears, so the list fills in as it goes. The panel
filters by **Controllers** and **Audio**, sorts anything connected or paired to
the top, and hides nameless strangers behind **Show unnamed**.

If your controller only shows as a MAC, scan again once it has settled, or
switch to **All** and look for the address.

## Controls

The binding adapts to whatever the running game declares, exactly like the
mini-joystick, so one pad works everywhere without per-game setup.

| Pad | Action |
|---|---|
| D-pad or left stick | Move, or aim the cursor |
| **A** (cross) | The game's main action — fire, flap, drop, hard drop |
| **B** (circle) | Rotate the other way, or the secondary action |
| **X** (square) | Hold piece, where a game has one |
| **Y** (triangle) | Secondary |
| **Start** | Pause and resume |
| **Select** | Restart |
| **Start** held | Open the quick wheel |

When no game is on the panel, **Start** opens a plugin menu on the matrix
itself: the d-pad moves the highlight, **Start** or **A** picks, **B** cancels.
With the menu closed, **A** and **B** step the brightness up and down live, and
the d-pad flicks straight between plugins.

Only movement auto-repeats when a direction is held, so holding the stick never
spins a Tetris piece or machine-guns a drop.

## Docker

The service runs `privileged` and shares the host `/dev`, so `/dev/input/*` is
already visible. Nothing to map.

BlueZ itself runs on the host; the container talks to it over the system D-Bus
socket, which the compose file already mounts:

```yaml
volumes:
  - /var/run/dbus:/var/run/dbus
```

## If it does not work

| Symptom | Cause | Fix |
|---|---|---|
| "evdev library is missing" | Gamepad support not installed | Rebuild the container |
| "No controller found" | Not paired, or not connected | Pair under Settings → Bluetooth; check `ls /dev/input/event*` |
| Pairs then drops immediately | Not trusted | `bluetoothctl` → `trust <MAC>` |
| Connected but nothing happens | Reading is switched off | Turn on **Use a game controller** |
| Wrong pad is being read | More than one connected | Pick it in the **Controller** dropdown |

A controller that goes out of range or switches off is noticed, and the service
reconnects on its own when it comes back.
