// Minimal typed client for the FastAPI backend. Paths are origin-absolute
// (/api/...), so they work regardless of the /app base path.

async function handle<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((payload as any).detail || (payload as any).message || "Request failed");
  }
  return payload as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return handle<T>(await fetch(path));
}

export async function apiPost<T>(path: string, body: unknown = {}): Promise<T> {
  return handle<T>(
    await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function apiDelete<T>(path: string): Promise<T> {
  return handle<T>(await fetch(path, { method: "DELETE" }));
}

export interface RuntimeState {
  running: boolean;
  pid?: number | null;
  startedAt?: string | null;
  lastExit?: { code?: number | null; at?: string | null } | null;
}

export interface StatusResponse {
  configured: boolean;
  missing: string[];
  runtime: RuntimeState;
  dataDir: string;
}

export interface AppConfigOption {
  label: string;
  value: string | number | boolean;
}

export interface AppConfigField {
  key: string;
  label: string;
  type: "string" | "secret" | "number" | "boolean" | "select";
  default?: unknown;
  options?: AppConfigOption[];
  required?: boolean;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: number;
  helpText?: string;
}

export interface AppManifest {
  id: string;
  name: string;
  version: string;
  summary: string;
  author: string;
  category: string;
  runtime: string;
  /** "game" apps are driven by a controller and get a gamepad. */
  kind?: "app" | "game";
  layout?: string;
  actions?: string[];
  config: AppConfigField[];
}

type HasManifest = { manifest: AppManifest } | null | undefined;

/** Games are apps, so identify them by manifest rather than a fixed list. */
export const isGame = (app: HasManifest) => app?.manifest.kind === "game";
export const gameIdOf = (app: HasManifest) => gameIdFromAppId(app?.manifest.id ?? "");

/** "core.pacman" -> "pacman", the id the game routes use. */
export const gameIdFromAppId = (appId: string) => appId.replace(/^[^.]+\./, "");

export interface LocalApp {
  manifest: AppManifest;
  installed: boolean;
  builtIn: boolean;
  enabled: boolean;
  configurable: boolean;
  active: boolean;
}

export const listLocalApps = () => apiGet<{ apps: LocalApp[] }>("/api/apps/local");
export const getAppConfig = (id: string) =>
  apiGet<{ appId: string; config: Record<string, unknown> }>(`/api/apps/local/${encodeURIComponent(id)}/config`);
export const saveAppConfig = (id: string, config: Record<string, unknown>) =>
  apiPost(`/api/apps/local/${encodeURIComponent(id)}/config`, { config });
export const applyApp = (id: string, config: Record<string, unknown> | null = null) =>
  apiPost(`/api/apps/local/${encodeURIComponent(id)}/apply`, { config });
export const previewApp = (appId: string, config: Record<string, unknown>) =>
  apiPost<{ dataUrl: string }>("/api/apps/preview", { appId, config });

const CORE_PREVIEWABLE = new Set([
  "core.text", "core.image", "core.draw", "core.slideshow",
  "core.clock", "core.agent", "core.weather", "core.spotify", "core.testPattern",
]);

/** Core apps render a preview, and so does every game app. */
export const canPreview = (app: HasManifest) =>
  Boolean(app) && (CORE_PREVIEWABLE.has(app!.manifest.id) || isGame(app));

export type TetrisAction =
  | "left" | "right" | "softDrop" | "hardDrop"
  | "rotateCw" | "rotateCcw" | "hold"
  | "pause" | "resume" | "togglePause" | "restart";

export interface TetrisState {
  board: string[];
  active: number[][];
  activeType: string;
  ghost: number[][];
  next: string;
  hold: string;
  holdLocked: boolean;
  score: number;
  lines: number;
  level: number;
  gameOver: boolean;
  paused: boolean;
  updatedAt: number;
}

export interface TetrisStateResponse {
  live: boolean;
  running: boolean;
  active: boolean;
  state: TetrisState | null;
}

export const getTetrisState = () => apiGet<TetrisStateResponse>("/api/tetris/state");
export const sendTetrisInput = (action: TetrisAction) =>
  apiPost<{ ok: boolean; seq: number }>("/api/tetris/input", { action });

export const getConfig = () => apiGet<Record<string, any>>("/api/config");
export const saveConfig = (config: Record<string, unknown>) => apiPost<Record<string, any>>("/api/config", config);

export const createPairing = () =>
  apiPost<{ pairingToken: string; expiresInSeconds: number; command: string }>("/api/auth/session", {});

export interface RotationItem { appId: string; durationSeconds: number; enabled: boolean }
export interface TriggerRule { event: string; appId: string; enabled: boolean; priority: number; minDurationSeconds: number }
export interface DisplayPolicy {
  mode: "single" | "rotation";
  activeAppId: string;
  rotation: RotationItem[];
  triggers: TriggerRule[];
}
export const getPolicy = () => apiGet<{ policy: DisplayPolicy }>("/api/display/policy");
export const savePolicy = (policy: DisplayPolicy) => apiPost<{ policy: DisplayPolicy }>("/api/display/policy", { policy });
export const applyPolicy = () => apiPost("/api/display/policy/apply", {});
export const stopPolicy = () => apiPost("/api/display/policy/stop", {});

export interface BtDevice {
  mac: string;
  name: string;
  paired: boolean;
  connected: boolean;
  trusted: boolean;
  icon: string;
  named: boolean;
  role: "controller" | "audio" | "input" | "phone" | "computer" | "display" | "other";
}
export const btStatus = () =>
  apiGet<{ available: boolean; powered: boolean; adapter: string; blocked: boolean; powerState: string; ertmDisabled: boolean | null; advice: string }>("/api/bluetooth/status");
export const btDevices = () => apiGet<{ available: boolean; devices: BtDevice[] }>("/api/bluetooth/devices");
export const btScan = (seconds = 8) => apiPost<{ available: boolean; devices: BtDevice[] }>("/api/bluetooth/scan", { seconds });
export const btConnect = (mac: string) =>
  apiPost<{ ok: boolean; message: string; advice: string }>("/api/bluetooth/connect", { mac });
export const btDisconnect = (mac: string) => apiPost("/api/bluetooth/disconnect", { mac });
export const btRemove = (mac: string) => apiPost("/api/bluetooth/remove", { mac });

export interface Asset {
  name: string;
  url: string;
  animated: boolean;
}
export const listAssets = () => apiGet<{ assets: Asset[] }>("/api/assets");
export const uploadAsset = (name: string, data: string) =>
  apiPost<{ ok: boolean; assetPath: string; url: string }>("/api/assets/upload", { name, data });
export async function deleteAsset(name: string) {
  const r = await fetch(`/api/assets/${encodeURIComponent(name)}`, { method: "DELETE" });
  if (!r.ok) throw new Error("Delete failed");
  return r.json();
}

export interface StoreApp {
  id: string;
  name: string;
  version: string;
  summary: string;
  category: string;
  author: string;
  runtime: string;
  installed: boolean;
  previewGifUrl: string;
  matrixPreviewUrl: string;
}
export const listStoreApps = () => apiGet<{ apps: StoreApp[] }>("/api/apps/store");
export const installApp = (appId: string) => apiPost("/api/apps/install", { appId });
export async function uninstallApp(appId: string) {
  const r = await fetch(`/api/apps/local/${encodeURIComponent(appId)}`, { method: "DELETE" });
  if (!r.ok) throw new Error("Uninstall failed");
  return r.json();
}

export type GameLayout = "dpad" | "horizontal" | "vertical" | "tap" | "tetris";

export interface GameSummary {
  id: string;
  name: string;
  summary: string;
  appId: string;
  layout: GameLayout;
  actions: string[];
  active: boolean;
}

export interface GameAudioState {
  enabled: boolean;
  device: string;
  error: string;
  sounds: number;
}

export interface GameFrame {
  game: string;
  status: "playing" | "paused" | "gameOver" | "won";
  hud: Record<string, string | number>;
  palette: string[];
  pixels: string[];
  updatedAt: number;
  /** Reported by the runtime, the only process that knows. */
  audio?: GameAudioState;
}

export interface GameStateResponse {
  gameId: string;
  live: boolean;
  running: boolean;
  active: boolean;
  state: GameFrame | null;
}

export const listGames = () =>
  apiGet<{ games: GameSummary[]; activeGameId: string; running: boolean }>("/api/games");
export const getGameState = (id: string) =>
  apiGet<GameStateResponse>(`/api/games/${encodeURIComponent(id)}/state`);
export const sendGameInput = (id: string, action: string) =>
  apiPost<{ ok: boolean; seq: number }>(`/api/games/${encodeURIComponent(id)}/input`, { action });

export interface JoystickState {
  enabled: boolean;
  /** "system" drives the matrix; "player" drives the game. */
  role: string;
  running: boolean;
  connected: boolean;
  bus: number;
  address: number;
  lastError: string;
  lastAction: string;
  lastActionAt: number;
  eventsSeen: number;
}

export const getJoystick = () => apiGet<JoystickState>("/api/joystick");
export const saveJoystickConfig = (config: Record<string, unknown>) =>
  apiPost<JoystickState>("/api/joystick/config", { config });

export interface I2CBusInfo {
  bus: number;
  addresses: string[];
  joystickFound: boolean;
  error: string;
}

export interface JoystickDiagnostics {
  libraryInstalled: boolean;
  buses: I2CBusInfo[];
  configuredBus: number;
  configuredAddress: string;
  detected: boolean;
  advice: string;
}

export const getJoystickDiagnostics = () => apiGet<JoystickDiagnostics>("/api/joystick/diagnostics");

export interface GameScores {
  gameId: string;
  best: number;
  plays: number;
  scores: { score: number; at: number }[];
}

export const getGameScores = (id: string) =>
  apiGet<GameScores>(`/api/games/${encodeURIComponent(id)}/scores`);

export interface GamepadDevice {
  path: string;
  name: string;
  wireless: boolean;
}

export interface GamepadState {
  enabled: boolean;
  running: boolean;
  connected: boolean;
  libraryInstalled: boolean;
  device: string;
  deviceName: string;
  devices: GamepadDevice[];
  inputDevices: { path: string; name: string; isGamepad: boolean; buttons: number; axes: number }[];
  lastError: string;
  advice: string;
}

export const getGamepad = () => apiGet<GamepadState>("/api/gamepad");
export const saveGamepadConfig = (config: Record<string, unknown>) =>
  apiPost<GamepadState>("/api/gamepad/config", { config });

export interface AudioDevice {
  name: string;
  description: string;
  /** Something a person would recognise, e.g. "HDMI 1" or the speaker's name. */
  label: string;
  /** bluetooth | headphones | hdmi | usb | default | other */
  kind: string;
  plumbing: boolean;
}

export interface AudioBridge {
  installed: boolean;
  running: boolean;
  error: string;
  binary: string;
}

export interface AudioState {
  enabled: boolean;
  available: boolean;
  device: string;
  volume: number;
  devices: AudioDevice[];
  sounds: string[];
  advice: string;
  /** Sound card buffer in ms: the ceiling on how late an effect can be. */
  bufferMs?: number;
  /** The Bluetooth-to-ALSA daemon; without it a speaker cannot be an output. */
  bridge?: AudioBridge;
}

export const getAudio = () => apiGet<AudioState>("/api/audio");
export const saveAudioConfig = (config: Record<string, unknown>) =>
  apiPost<AudioState>("/api/audio/config", { config });
export const testAudio = (sound: string) =>
  apiPost<{ ok: boolean; message: string }>("/api/audio/test", { sound });


export interface BindingProfile {
  id: string;
  name: string;
  controls: string[];
  labels: Record<string, string>;
  /** Whether a device of this kind is connected right now. */
  present: boolean;
}

export interface GameBindings {
  gameId: string;
  appId: string;
  /** The device these bindings are for. */
  profile: string;
  profiles: BindingProfile[];
  controls: string[];
  actions: string[];
  bindings: Record<string, string>;
  defaults: Record<string, string>;
  customised: string[];
  /** Convenience: the chosen profile's labels, filled in by getGameBindings. */
  labels?: Record<string, string>;
}

function withLabels(state: GameBindings): GameBindings {
  const chosen = state.profiles.find((p) => p.id === state.profile);
  return { ...state, labels: chosen?.labels ?? {} };
}

export const getGameBindings = (gameId: string, device = "") =>
  apiGet<GameBindings>(`/api/games/${gameId}/bindings${device ? `?device=${encodeURIComponent(device)}` : ""}`).then(withLabels);

export const saveGameBindings = (gameId: string, profile: string, bindings: Record<string, string>) =>
  apiPost<GameBindings>(`/api/games/${gameId}/bindings`, { profile, bindings }).then(withLabels);

export const resetGameBindings = (gameId: string, device: string) =>
  apiDelete<GameBindings>(`/api/games/${gameId}/bindings?device=${encodeURIComponent(device)}`).then(withLabels);


export interface SystemControlsState {
  controls: string[];
  labels: Record<string, string>;
  actions: { action: string; label: string }[];
  bindings: Record<string, string>;
  defaults: Record<string, string>;
  customised: string[];
}

export const getSystemControls = () => apiGet<SystemControlsState>("/api/joystick/system-controls");
export const saveSystemControls = (bindings: Record<string, string>) =>
  apiPost<SystemControlsState>("/api/joystick/system-controls", { bindings });
export const resetSystemControls = () => apiDelete<SystemControlsState>("/api/joystick/system-controls");
