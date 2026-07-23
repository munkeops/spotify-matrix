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
