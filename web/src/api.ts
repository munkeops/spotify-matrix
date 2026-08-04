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

export interface WidgetConfigOption {
  label: string;
  value: string | number | boolean;
}

export interface WidgetConfigField {
  key: string;
  label: string;
  type: "string" | "secret" | "number" | "boolean" | "select";
  default?: unknown;
  options?: WidgetConfigOption[];
  required?: boolean;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: number;
  helpText?: string;
}

export interface WidgetManifest {
  id: string;
  name: string;
  version: string;
  summary: string;
  author: string;
  category: string;
  runtime: string;
  /** "game" widgets are driven by a controller and get a gamepad. */
  kind?: "widget" | "game";
  layout?: string;
  actions?: string[];
  config: WidgetConfigField[];
}

type HasManifest = { manifest: WidgetManifest } | null | undefined;

/** Games are plugins, so identify them by manifest rather than a fixed list. */
export const isGame = (widget: HasManifest) => widget?.manifest.kind === "game";
export const gameIdOf = (widget: HasManifest) => gameIdFromWidgetId(widget?.manifest.id ?? "");

/** "core.pacman" -> "pacman", the id the game routes use. */
export const gameIdFromWidgetId = (widgetId: string) => widgetId.replace(/^[^.]+\./, "");

export interface LocalWidget {
  manifest: WidgetManifest;
  installed: boolean;
  builtIn: boolean;
  enabled: boolean;
  configurable: boolean;
  active: boolean;
}

export const listLocalWidgets = () => apiGet<{ widgets: LocalWidget[] }>("/api/widgets/local");
export const getWidgetConfig = (id: string) =>
  apiGet<{ widgetId: string; config: Record<string, unknown> }>(`/api/widgets/local/${encodeURIComponent(id)}/config`);
export const saveWidgetConfig = (id: string, config: Record<string, unknown>) =>
  apiPost(`/api/widgets/local/${encodeURIComponent(id)}/config`, { config });
export const applyWidget = (id: string, config: Record<string, unknown> | null = null) =>
  apiPost(`/api/widgets/local/${encodeURIComponent(id)}/apply`, { config });
export const previewWidget = (widgetId: string, config: Record<string, unknown>) =>
  apiPost<{ dataUrl: string }>("/api/widgets/preview", { widgetId, config });

const CORE_PREVIEWABLE = new Set([
  "core.text", "core.image", "core.draw", "core.slideshow",
  "core.clock", "core.agent", "core.weather", "core.spotify", "core.testPattern",
]);

/** Core widgets render a preview, and so does every game plugin. */
export const canPreview = (widget: HasManifest) =>
  Boolean(widget) && (CORE_PREVIEWABLE.has(widget!.manifest.id) || isGame(widget));

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

export interface RotationItem { widgetId: string; durationSeconds: number; enabled: boolean }
export interface TriggerRule { event: string; widgetId: string; enabled: boolean; priority: number; minDurationSeconds: number }
export interface DisplayPolicy {
  mode: "single" | "rotation";
  activeWidgetId: string;
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
}
export const btStatus = () => apiGet<{ available: boolean; powered: boolean; adapter: string }>("/api/bluetooth/status");
export const btDevices = () => apiGet<{ available: boolean; devices: BtDevice[] }>("/api/bluetooth/devices");
export const btScan = (seconds = 8) => apiPost<{ available: boolean; devices: BtDevice[] }>("/api/bluetooth/scan", { seconds });
export const btConnect = (mac: string) => apiPost("/api/bluetooth/connect", { mac });
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

export interface StoreWidget {
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
export const listStoreWidgets = () => apiGet<{ widgets: StoreWidget[] }>("/api/widgets/store");
export const installWidget = (widgetId: string) => apiPost("/api/widgets/install", { widgetId });
export async function uninstallWidget(widgetId: string) {
  const r = await fetch(`/api/widgets/local/${encodeURIComponent(widgetId)}`, { method: "DELETE" });
  if (!r.ok) throw new Error("Uninstall failed");
  return r.json();
}

export type GameLayout = "dpad" | "horizontal" | "vertical" | "tap" | "tetris";

export interface GameSummary {
  id: string;
  name: string;
  summary: string;
  widgetId: string;
  layout: GameLayout;
  actions: string[];
  active: boolean;
}

export interface GameFrame {
  game: string;
  status: "playing" | "paused" | "gameOver" | "won";
  hud: Record<string, string | number>;
  palette: string[];
  pixels: string[];
  updatedAt: number;
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
