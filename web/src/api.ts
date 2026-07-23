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

export const PREVIEWABLE = new Set(["core.text", "core.image", "core.draw", "core.slideshow"]);
