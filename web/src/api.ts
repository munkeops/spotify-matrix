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
  config: WidgetConfigField[];
}

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

export const PREVIEWABLE = new Set([
  "core.text", "core.image", "core.draw", "core.slideshow",
  "core.clock", "core.agent", "core.weather", "core.spotify", "core.testPattern",
]);

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
