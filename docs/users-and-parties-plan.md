# Users, friends and parties

A plan for turning a single-owner appliance into something several people
use, on one unit and across several.

Four things are being asked for, and they are not equally hard:

| | Needs a server anyone pays for | Works with the power cut to the router |
| --- | --- | --- |
| Users on a unit | no | yes |
| LAN parties | no | yes |
| Accounts across units | **yes** | no |
| Cloud parties | **yes** | no |

The order below follows that table. Everything local ships first and keeps
working forever; the cloud half waits on a decision that costs money and
carries a duty of care, and is deliberately not started until that decision
is made.

## What already exists and should be reused

- **Seats.** `matrix_input/seats.py` already decides which controller is
  which player. A LAN party is the same idea with the seats on different
  units, so `Seats` grows a notion of a remote device rather than being
  replaced.
- **The frame encoding.** Apps already serialise a 64x64 frame as a palette
  plus base62 rows for the web preview. That is a ready-made wire format
  for "host draws, guests display".
- **The app store.** Installing and uninstalling already works. Users need
  to own installs, not a new mechanism.
- **`GameApp.handle(action, player)`.** Games already accept an action on
  behalf of a numbered player, which is exactly what arrives over a wire.

## M0 - Stop shipping games as installed

`AppRegistryService.list_local_apps` gates built-in widgets on
`BUILTIN_MODE` but appends bundled game packages unconditionally, and
`discover()` always includes the bundled directory. So a fresh unit shows
fifteen games it never installed, and the store has nothing to offer.

Bundled games become available-to-install rather than installed. The files
stay in the image - that is what makes installing them instant and offline
- but a game is listed as installed only when it is in `installed.json`.

Small, and it unblocks the store being the way you get things.

## M1 - Users on a unit

A **profile**: id, display name, avatar, PIN, created date. Stored under
`data/users/`, one file each.

- **Avatar.** A 16x16 pixel image, drawn in the web UI or picked from a
  set. It has to read at a glance on a 64x64 panel from across a room,
  which rules out photographs.
- **Signing in.** Password entry on a 64x64 panel with a joystick is
  miserable, so: a **4-digit PIN** on the unit, and a full sign-in in the
  web UI. The wheel gets a "switch user" entry.
- **What a user owns.** High scores, installed apps, controller bindings,
  and their party identity. Panel settings stay per unit: brightness and
  wiring belong to the hardware, not to whoever is holding the controller.
- **The owner.** First run creates one profile and signs it in, so a unit
  is never unusable for want of an account. Adding a second profile is
  what turns sign-in on.

Storage: PINs hashed with a slow hash and a per-user salt, never stored or
logged in the clear. A PIN is four digits and therefore weak - it protects
a games high score from a sibling, not a bank account, and the UI should
not imply otherwise.

## M2 - Units find each other on the LAN

Each unit advertises itself over mDNS (`_matrix._tcp`), carrying its name,
its signed-in user's display name and avatar hash, and what it is doing.
Discovery is passive: a unit lists the others it can see, and nothing
happens without an invitation being accepted on both ends.

No accounts involved. Two units on the same network can party with no
internet connection at all.

## M3 - LAN parties

A party is a host and up to three guests. The host runs the app; guests
send input and receive frames.

- **Input** goes guest to host as the same actions the local controller
  produces, tagged with the guest's seat.
- **Frames** go host to guests as the existing palette-plus-rows encoding,
  at the app's own frame rate. A 64x64 frame compresses to about a
  kilobyte, which is nothing on a LAN.
- **Transport** is a WebSocket per guest.

Rendering on the host and shipping pixels is chosen over running the game
on every unit and syncing state, because it cannot desynchronise and needs
no determinism from app authors. The cost is that every guest's picture is
one network hop behind, which on a LAN is a few milliseconds.

Order of delivery: **Pong** first (two seats, tiny state, obvious when it
works), then **Tron**, then a **shared canvas** for the "just draw
something together" case, which needs no game logic at all and is the best
demonstration that the transport is sound.

## M4 - Accounts across units (blocked on a decision)

Everything above works with no server. This does not: for a friend on
another network to be a stable identity, something has to hold the list.

The decision is who runs that and what it costs. Three shapes, in
increasing order of what they ask of you:

1. **No cloud.** Friends are per-LAN. Nothing to run, nothing to pay for,
   nothing to breach.
2. **A small hosted service.** Accounts, friends, and a rendezvous point.
   Cloudflare Workers plus D1 or a small VPS; single-digit pounds a month
   at this scale.
3. **Bring your own.** The service is open source and self-hostable, and
   your units point at whatever instance you choose - including one on a
   Pi behind the tunnel this project already uses.

This carries obligations the local half does not: storing other people's
email addresses and password hashes, a way to delete an account and mean
it, and a breach being someone else's problem too. Worth being deliberate
about rather than drifting into.

## M5 - Cloud parties (blocked on M4)

Same transport as M3, reaching across networks. Two units behind different
NATs need either a relay - simple, and every frame passes through your
server, which is the cost - or hole punching, which is cheaper to run and
much harder to make reliable. Start with a relay; a party is a kilobyte a
frame and the traffic is small.

## Open questions

1. **Which of the three shapes in M4?** Nothing before M4 is blocked on
   the answer, so this can be decided late - but not silently.
2. **Do profiles gate the unit?** "Each unit must have a user logged in"
   reads as mandatory. Confirm that a guest who wants to play Tetris has
   to pick a profile first.
3. **Do installed apps belong to a user or a unit?** Per user is tidier
   and matches the phrase "they download content from the app store"; per
   unit means one install serves the household. Per user costs disk on a
   Pi and can surprise people.
