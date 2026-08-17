"""API request and response schemas for Spotify Matrix."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SpotifyConfig(BaseModel):
    clientId: str = ""
    clientSecret: str = ""
    redirectUri: str = "http://127.0.0.1:8888/callback"
    spin: Literal["auto", "always", "off"] = "auto"


class MatrixConfig(BaseModel):
    rows: int = 64
    cols: int = 64
    chainLength: int = 1
    parallel: int = 1
    brightness: int = 65
    gpioSlowdown: int = 4
    hardwareMapping: str = "adafruit-hat"
    pwmBits: int = 11
    #: Time given to the shortest colour pulse. The library's default; raising
    #: it costs refresh quickly.
    pwmLsbNanoseconds: int = 130
    #: Spreads the lowest colour bits over successive frames, buying a lot of
    #: refresh for a little colour depth.
    pwmDitherBits: int = 0
    #: Initialisation some panels need, e.g. FM6126A. Blank for most.
    panelType: str = ""
    limitRefreshRateHz: int = 120
    noHardwarePulse: bool = True
    #: Panel tuning kept per wiring, so swapping between a HAT and direct
    #: wiring restores what was tuned for it rather than losing it.
    profiles: dict[str, dict[str, Any]] = Field(default_factory=dict)
    pollSeconds: float = 2
    fps: float = 20
    rpm: float = 20
    rotation: Literal[0, 90, 180, 270] = 0


class RuntimeConfig(BaseModel):
    mockOutput: str = ""
    testPattern: bool = False


class DisplayConfig(BaseModel):
    mode: Literal["spotify", "clock", "agent", "weather", "text", "image", "draw", "slideshow", "testPattern", "app"] = "spotify"
    appId: str = ""


class ClockConfig(BaseModel):
    face: Literal["analog", "digital", "minimal"] = "analog"
    use24Hour: bool = False
    showSeconds: bool = False
    timezone: str = ""


class AgentConfig(BaseModel):
    faceStyle: Literal["classic", "wide", "sleepy", "happy", "cool"] = "classic"
    animationSpeed: Literal["slow", "normal", "fast"] = "normal"


class WeatherConfig(BaseModel):
    label: str = "Local weather"
    postalCode: str = ""
    countryCode: str = "US"
    latitude: float | None = None
    longitude: float | None = None
    temperatureUnit: Literal["fahrenheit", "celsius"] = "fahrenheit"
    faceAccessory: Literal["auto", "none", "sunglasses", "umbrella"] = "auto"
    refreshMinutes: int = 15
    metricsSeconds: int = 45
    sceneSeconds: int = 20


class TextConfig(BaseModel):
    text: str = "HELLO"
    color: str = "#ffffff"
    background: str = "#000000"
    scroll: bool = False
    scrollSpeed: Literal["slow", "normal", "fast"] = "normal"
    fontSize: Literal["small", "medium", "large"] = "medium"
    align: Literal["left", "center", "right"] = "center"
    fontFamily: Literal["pixel", "sans", "mono", "devanagari"] = "pixel"
    bold: bool = False
    italic: bool = False
    wrap: bool = False
    fit: bool = False


class ImageConfig(BaseModel):
    assetPath: str = ""
    fit: Literal["contain", "cover", "stretch"] = "contain"
    background: str = "#000000"
    rotate: Literal[0, 90, 180, 270] = 0


class DrawShape(BaseModel):
    type: Literal["rect", "circle", "line", "text", "pixel"] = "rect"
    color: str = "#ffffff"
    x: int = 0
    y: int = 0
    w: int = 8
    h: int = 8
    radius: int = 4
    x2: int = 16
    y2: int = 16
    text: str = ""
    size: Literal["small", "medium", "large"] = "small"
    fill: bool = True
    fontFamily: Literal["pixel", "sans", "mono", "devanagari"] = "pixel"
    bold: bool = False
    italic: bool = False


class DrawConfig(BaseModel):
    background: str = "#000000"
    shapes: list[DrawShape] = Field(default_factory=list)


class SlideshowConfig(BaseModel):
    items: list[str] = Field(default_factory=list)
    intervalSeconds: int = 8
    fit: Literal["contain", "cover", "stretch"] = "cover"
    background: str = "#000000"
    rotate: Literal[0, 90, 180, 270] = 0
    shuffle: bool = False


class JoystickConfig(BaseModel):
    """Mini-joystick module (I2C 0x5A). See docs/mini-joystick.md for wiring."""

    enabled: bool = False
    #: What the module is for.
    #:
    #: "system" - device control: the wheel, switching apps, brightness and
    #: volume, available even while a game is running on a gamepad. This is
    #: the default, because the module is bolted to the matrix and a pad is
    #: what you actually play with.
    #: "player" - a game controller like any other.
    role: str = "system"
    #: Which control does which system action, by control id.
    #:
    #: Empty means the defaults. Which button is where under a thumb is not
    #: something the silkscreen order knows, so this is the owner's to set.
    systemBindings: dict[str, str] = Field(default_factory=dict)
    bus: int = 1
    address: int = 0x5A
    deadzone: float = 0.35
    invertX: bool = False
    invertY: bool = False
    repeatDelay: float = 0.28
    repeatInterval: float = 0.09
    #: Use a repeated START instead of the vendor's write-STOP-read pair.
    combinedRead: bool = False


class GamepadConfig(BaseModel):
    """Bluetooth or USB game controller, read through evdev."""

    enabled: bool = False
    #: Empty means take the first controller found.
    device: str = ""
    deadzone: float = 0.5


class AudioConfig(BaseModel):
    """Sound effects for the games."""

    enabled: bool = False
    #: Empty means the ALSA default device.
    device: str = ""
    volume: int = 80
    #: How much audio the sound card may hold, in milliseconds.
    #:
    #: The ceiling on how late an effect can be. Lower is tighter to the
    #: picture; too low and the output crackles. Bluetooth needs more slack
    #: than HDMI, and adds 100ms or so of its own on top whatever this says.
    bufferMs: int = 120


class ControllerConfig(BaseModel):
    """Controller bindings, keyed by device profile, app id, then control.

    The profile comes first because the mini-joystick module and a gamepad
    are not the same shape: the module has five buttons, a pad has thirteen.
    One mapping shared between them meant rebinding for one silently rebound
    the other, and the pad's spare buttons had nowhere to go.
    """

    profiles: dict[str, dict[str, dict[str, str]]] = Field(default_factory=dict)


class StoreConfig(BaseModel):
    indexUrl: str = "configs/app_store_index.json"


class AssetUploadRequest(BaseModel):
    name: str = ""
    data: str


class AssetUploadResponse(BaseModel):
    ok: bool
    assetPath: str
    url: str


class AssetItem(BaseModel):
    name: str
    url: str
    animated: bool = False


class AssetListResponse(BaseModel):
    assets: list[AssetItem] = Field(default_factory=list)


class MatrixDriver(BaseModel):
    """A named panel wiring, as the settings page lists it."""

    id: str
    name: str
    summary: str = ""
    hardwareMapping: str = ""
    gpioSlowdown: int = 1
    noHardwarePulse: bool = False
    #: Signal name to BCM pin, in wiring order.
    pins: dict[str, int] = Field(default_factory=dict)
    notes: str = ""


class MatrixDriversResponse(BaseModel):
    drivers: list[MatrixDriver] = Field(default_factory=list)
    #: The driver the saved settings describe, or "custom".
    active: str = "custom"
    #: Signal order, so the panel's pin table reads the way you wire it.
    pinOrder: list[str] = Field(default_factory=list)
    #: Driver ids with tuning remembered from last time they were used.
    remembered: list[str] = Field(default_factory=list)


class MatrixDriverRequest(BaseModel):
    id: str


class BluetoothDevice(BaseModel):
    mac: str
    name: str = ""
    paired: bool = False
    connected: bool = False
    trusted: bool = False
    icon: str = ""
    #: False when the device has only reported its address so far.
    named: bool = False
    #: controller, audio, input, phone, computer, display or other.
    role: str = "other"


class BluetoothStatusResponse(BaseModel):
    available: bool
    powered: bool = False
    adapter: str = ""
    blocked: bool = False
    powerState: str = ""
    #: None when the kernel setting is not visible from here.
    ertmDisabled: bool | None = None
    advice: str = ""


class BluetoothDevicesResponse(BaseModel):
    available: bool
    devices: list[BluetoothDevice] = Field(default_factory=list)


class BluetoothScanRequest(BaseModel):
    seconds: int = 8


class BluetoothPowerRequest(BaseModel):
    on: bool = True


class BluetoothActionRequest(BaseModel):
    mac: str


class BluetoothActionResponse(BaseModel):
    ok: bool
    message: str = ""
    device: BluetoothDevice | None = None
    advice: str = ""


class AppConfig(BaseModel):
    spotify: SpotifyConfig = Field(default_factory=SpotifyConfig)
    matrix: MatrixConfig = Field(default_factory=MatrixConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    clock: ClockConfig = Field(default_factory=ClockConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    weather: WeatherConfig = Field(default_factory=WeatherConfig)
    text: TextConfig = Field(default_factory=TextConfig)
    image: ImageConfig = Field(default_factory=ImageConfig)
    draw: DrawConfig = Field(default_factory=DrawConfig)
    slideshow: SlideshowConfig = Field(default_factory=SlideshowConfig)
    joystick: JoystickConfig = Field(default_factory=JoystickConfig)
    gamepad: GamepadConfig = Field(default_factory=GamepadConfig)
    controller: ControllerConfig = Field(default_factory=ControllerConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    store: StoreConfig = Field(default_factory=StoreConfig)


class TokenStatus(BaseModel):
    present: bool
    hasRefreshToken: bool = False
    expiresAt: float | None = None


class RuntimeExit(BaseModel):
    code: int | None = None
    signal: str | None = None
    at: str | None = None


class RuntimeState(BaseModel):
    running: bool
    pid: int | None = None
    startedAt: str | None = None
    lastExit: RuntimeExit | None = None


class StatusResponse(BaseModel):
    configured: bool
    missing: list[str]
    token: TokenStatus
    runtime: RuntimeState
    dataDir: str


class AuthSessionResponse(BaseModel):
    pairingToken: str
    expiresInSeconds: int
    command: str


class AuthSessionSecrets(BaseModel):
    clientId: str
    clientSecret: str
    scope: str


class SpotifyToken(BaseModel):
    access_token: str | None = None
    token_type: str | None = None
    scope: str | None = None
    expires_in: int = 3600
    refresh_token: str

    class Config:
        extra = "allow"


class TokenRequest(BaseModel):
    pairingToken: str
    token: SpotifyToken


class TokenSaveResponse(BaseModel):
    ok: bool
    token: TokenStatus


class RuntimeActionResponse(BaseModel):
    runtime: RuntimeState


class CommandRequest(BaseModel):
    command: Literal["set_mode", "set_app", "set_clock_face", "set_brightness", "trigger_event", "start_runtime", "stop_runtime"]
    value: str | int | None = None


TetrisAction = Literal["left", "right", "softDrop", "hardDrop", "rotateCw", "rotateCcw", "hold", "pause", "resume", "togglePause", "restart"]

GameAction = Literal[
    "up", "down", "left", "right",
    "softDrop", "hardDrop", "rotateCw", "rotateCcw", "hold",
    "fire", "flap", "drop", "start",
    "p2Up", "p2Down",
    "pause", "resume", "togglePause", "restart",
]


class GameInputRequest(BaseModel):
    action: GameAction


class GameAudioState(BaseModel):
    """Whether the runtime can actually make a noise for this game."""

    enabled: bool = False
    device: str = ""
    error: str = ""
    #: How many effects were loaded. Zero with sound on means none were found.
    sounds: int = 0


class GameFrame(BaseModel):
    """A rendered panel frame: a colour palette plus one index string per row."""

    game: str = ""
    status: str = "playing"
    hud: dict[str, Any] = Field(default_factory=dict)
    palette: list[str] = Field(default_factory=list)
    pixels: list[str] = Field(default_factory=list)
    updatedAt: float = 0.0
    #: Reported by the runtime, which is the only process that knows.
    audio: GameAudioState | None = None


class GameSummary(BaseModel):
    id: str
    name: str
    summary: str
    appId: str
    layout: str
    actions: list[str] = Field(default_factory=list)
    active: bool = False


class GameListResponse(BaseModel):
    games: list[GameSummary] = Field(default_factory=list)
    activeGameId: str = ""
    running: bool = False


class GameStateResponse(BaseModel):
    gameId: str
    live: bool
    running: bool
    active: bool
    state: GameFrame | None = None


class GameInputResponse(BaseModel):
    ok: bool
    gameId: str
    seq: int
    action: str


class TetrisInputRequest(BaseModel):
    action: TetrisAction


class TetrisState(BaseModel):
    board: list[str] = Field(default_factory=list)
    active: list[list[int]] = Field(default_factory=list)
    activeType: str = ""
    ghost: list[list[int]] = Field(default_factory=list)
    next: str = ""
    hold: str = ""
    holdLocked: bool = False
    score: int = 0
    lines: int = 0
    level: int = 1
    gameOver: bool = False
    paused: bool = False
    updatedAt: float = 0.0


class TetrisStateResponse(BaseModel):
    live: bool
    running: bool
    active: bool
    state: TetrisState | None = None


class TetrisInputResponse(BaseModel):
    ok: bool
    seq: int
    action: str


class CommandResponse(BaseModel):
    ok: bool
    config: AppConfig
    runtime: Any = None
    matched: bool | None = None
    appId: str | None = None


class PlayerSeat(BaseModel):
    """One player slot in the game currently on the panel."""

    seat: int
    player: int
    device: str = ""
    kind: str = ""
    id: str = ""
    taken: bool = False


class JoystickStateResponse(BaseModel):
    enabled: bool
    #: Empty unless the running game takes more than one player.
    seats: list[PlayerSeat] = Field(default_factory=list)
    #: "system" (device control) or "player" (a game controller).
    role: str = "system"
    running: bool
    connected: bool
    bus: int = 1
    address: int = 0x5A
    lastError: str = ""
    lastAction: str = ""
    #: The physical control last used, so a diagram can highlight it.
    lastControl: str = ""
    lastControlAt: float = 0.0
    lastActionAt: float = 0.0
    eventsSeen: int = 0


class SystemControlsResponse(BaseModel):
    """The module's buttons and what each is set to do."""

    controls: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    actions: list[dict[str, str]] = Field(default_factory=list)
    bindings: dict[str, str] = Field(default_factory=dict)
    defaults: dict[str, str] = Field(default_factory=dict)
    customised: list[str] = Field(default_factory=list)


class SystemControlsRequest(BaseModel):
    bindings: dict[str, str] = Field(default_factory=dict)


class JoystickConfigRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class I2CBusInfo(BaseModel):
    bus: int
    addresses: list[str] = Field(default_factory=list)
    joystickFound: bool = False
    error: str = ""


class JoystickDiagnostics(BaseModel):
    """Everything needed to work out why the module is not responding."""

    libraryInstalled: bool
    buses: list[I2CBusInfo] = Field(default_factory=list)
    configuredBus: int = 1
    configuredAddress: str = "0x5a"
    detected: bool = False
    #: Plain-language next step when the module is not detected.
    advice: str = ""


class GameScoreEntry(BaseModel):
    score: int
    at: float = 0.0


class GameScoresResponse(BaseModel):
    gameId: str
    best: int = 0
    plays: int = 0
    scores: list[GameScoreEntry] = Field(default_factory=list)
    values: dict[str, Any] = Field(default_factory=dict)


class GamepadDevice(BaseModel):
    path: str
    name: str
    wireless: bool = False


class GamepadStateResponse(BaseModel):
    enabled: bool
    running: bool
    connected: bool
    libraryInstalled: bool
    device: str = ""
    deviceName: str = ""
    devices: list[GamepadDevice] = Field(default_factory=list)
    #: Every evdev device, so a pad on the wrong driver is still visible.
    inputDevices: list[dict[str, Any]] = Field(default_factory=list)
    lastError: str = ""
    advice: str = ""


class GamepadConfigRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class BindingProfile(BaseModel):
    """One input device, and what its controls should be called on screen."""

    id: str
    name: str
    controls: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    #: Whether a device of this kind is plugged in or paired right now.
    present: bool = False


class GameBindingsResponse(BaseModel):
    gameId: str
    appId: str
    #: The profile these bindings are for.
    profile: str = ""
    profiles: list[BindingProfile] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    bindings: dict[str, str] = Field(default_factory=dict)
    defaults: dict[str, str] = Field(default_factory=dict)
    #: Which controls the player has changed from the default.
    customised: list[str] = Field(default_factory=list)


class GameBindingsRequest(BaseModel):
    profile: str = ""
    bindings: dict[str, str] = Field(default_factory=dict)


class AudioDevice(BaseModel):
    """One playback device, as the settings panel should show it.

    The label and kind are the whole point of the list - without them the
    panel falls back to the ALSA PCM string, which is what it was doing
    before because this model quietly dropped any field it did not name.
    """

    name: str
    description: str = ""
    #: Something a person would recognise: "HDMI 1", or the speaker's name.
    label: str = ""
    #: bluetooth | headphones | hdmi | usb | default | other
    kind: str = "other"
    #: True for the rate-converting and mixing wrappers, hidden by default.
    plumbing: bool = False


class AudioBridge(BaseModel):
    """State of the Bluetooth-to-ALSA daemon, so the panel can explain itself."""

    installed: bool = False
    running: bool = False
    error: str = ""
    binary: str = ""
    #: Speakers that have registered a playback PCM, not merely paired.
    speakers: int = 0
    #: Who this process is to the system bus, which is what bluealsa judges.
    uid: int = -1
    inAudioGroup: bool = False
    #: False when the bus policy would refuse us whatever else is right.
    permitted: bool = True


class AudioStateResponse(BaseModel):
    enabled: bool
    available: bool
    device: str = ""
    volume: int = 80
    devices: list[AudioDevice] = Field(default_factory=list)
    sounds: list[str] = Field(default_factory=list)
    advice: str = ""
    bufferMs: int = 120
    bridge: AudioBridge = Field(default_factory=AudioBridge)


class AudioConfigRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class AudioTestRequest(BaseModel):
    sound: str = "start"
