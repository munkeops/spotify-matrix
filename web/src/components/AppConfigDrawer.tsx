import { useEffect, useState } from "react";
import {
  Drawer, Box, Stack, Typography, TextField, MenuItem, Switch, FormControlLabel,
  Button, IconButton, Divider, Alert,
} from "@mui/material";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import {
  LocalApp, getAppConfig, saveAppConfig, applyApp, createPairing,
  gameIdOf, isGame,
} from "../api";
import Gallery from "./Gallery";
import GameControls from "./GameControls";

function ColorField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <Stack direction="row" alignItems="center" justifyContent="space-between">
      <Typography variant="body2">{label}</Typography>
      <input type="color" value={value || "#000000"} onChange={(e) => onChange(e.target.value)} style={{ width: 44, height: 30, border: "none", background: "none" }} />
    </Stack>
  );
}

export default function AppConfigDrawer({
  app, open, onClose, onApplied,
}: {
  app: LocalApp | null;
  open: boolean;
  onClose: () => void;
  onApplied: () => void;
}) {
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [pairingCmd, setPairingCmd] = useState<string>("");

  const id = app?.manifest.id ?? "";
  // Games get a Controls section; nothing else takes controller input.
  const gameId = isGame(app) ? gameIdOf(app) : "";
  const fields = app?.manifest.config ?? [];

  useEffect(() => {
    if (!app || !open) return;
    setError("");
    getAppConfig(id)
      .then((r) => setValues(r.config || {}))
      .catch((e) => setError((e as Error).message));
  }, [id, open, app]);

  const set = (key: string, value: unknown) => setValues((prev) => ({ ...prev, [key]: value }));

  const toggleItem = (name: string) => {
    const items = Array.isArray(values.items) ? [...(values.items as string[])] : [];
    const idx = items.indexOf(name);
    if (idx >= 0) items.splice(idx, 1);
    else items.push(name);
    set("items", items);
  };

  const FIT = ["contain", "cover", "stretch"];

  const doSave = async () => {
    setBusy(true);
    try {
      await saveAppConfig(id, values);
      onApplied();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const doApply = async () => {
    setBusy(true);
    try {
      await applyApp(id, values);
      onApplied();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{ sx: { width: { xs: "100%", sm: 420 }, p: 2, bgcolor: "background.default" } }}
    >
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
        <Typography variant="h6">{app?.manifest.name ?? "App"}</Typography>
        <IconButton onClick={onClose}><CloseRoundedIcon /></IconButton>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{app?.manifest.summary}</Typography>

      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}

      <Stack spacing={2} sx={{ flex: 1, overflowY: "auto" }}>
        {id === "core.spotify" ? (
          <>
            <TextField label="Client ID" size="small" value={String(values.clientId ?? "")} onChange={(e) => set("clientId", e.target.value)} />
            <TextField label="Client Secret" type="password" size="small" placeholder="Leave masked to keep existing" value={String(values.clientSecret ?? "")} onChange={(e) => set("clientSecret", e.target.value)} />
            <TextField label="Redirect URI" size="small" value={String(values.redirectUri ?? "")} onChange={(e) => set("redirectUri", e.target.value)} />
            <TextField select label="Record spin" size="small" value={String(values.spin ?? "auto")} onChange={(e) => set("spin", e.target.value)} helperText="Set to Always if the art won't spin (Spotify reports paused).">
              <MenuItem value="auto">Auto — spin while playing</MenuItem>
              <MenuItem value="always">Always spin</MenuItem>
              <MenuItem value="off">Never spin</MenuItem>
            </TextField>
            <Stack direction="row" spacing={1}>
              <Button variant="outlined" onClick={async () => { await saveAppConfig(id, values); window.location.href = "/api/auth/login"; }}>Open Spotify Login</Button>
              <Button variant="outlined" onClick={async () => {
                try { await saveAppConfig(id, values); const s = await createPairing(); setPairingCmd(s.command.replace(/http:\/\/<pi-host>:\d+/, window.location.origin)); }
                catch (e) { setError((e as Error).message); }
              }}>Pairing Token</Button>
            </Stack>
            {pairingCmd ? (
              <TextField label="Run on your laptop" size="small" multiline value={pairingCmd} InputProps={{ readOnly: true }} />
            ) : (
              <Typography variant="caption" color="text.secondary">Save an HTTPS /api/auth/callback redirect for tunnel login, or create a pairing token for local loopback setup.</Typography>
            )}
          </>
        ) : id === "core.image" ? (
          <>
            <TextField select label="Fit" size="small" value={String(values.fit ?? "contain")} onChange={(e) => set("fit", e.target.value)}>
              {FIT.map((f) => <MenuItem key={f} value={f}>{f}</MenuItem>)}
            </TextField>
            <TextField select label="Rotate" size="small" value={String(values.rotate ?? 0)} onChange={(e) => set("rotate", Number(e.target.value))}>
              {[0, 90, 180, 270].map((r) => <MenuItem key={r} value={String(r)}>{r}°</MenuItem>)}
            </TextField>
            <ColorField label="Background" value={String(values.background ?? "#000000")} onChange={(v) => set("background", v)} />
            <Gallery mode="single" selected={String(values.assetPath ?? "")} onPick={(name) => set("assetPath", name)} />
          </>
        ) : id === "core.slideshow" ? (
          <>
            <TextField label="Seconds per image" type="number" size="small" value={Number(values.intervalSeconds ?? 8)} onChange={(e) => set("intervalSeconds", Number(e.target.value))} />
            <TextField select label="Fit" size="small" value={String(values.fit ?? "cover")} onChange={(e) => set("fit", e.target.value)}>
              {FIT.map((f) => <MenuItem key={f} value={f}>{f}</MenuItem>)}
            </TextField>
            <ColorField label="Background" value={String(values.background ?? "#000000")} onChange={(v) => set("background", v)} />
            <Gallery mode="multi" selected={(values.items as string[]) ?? []} onPick={toggleItem} />
          </>
        ) : (
          <>
        {fields.length === 0 ? (
          <Typography variant="body2" color="text.secondary">This app has no options.</Typography>
        ) : null}
        {fields.map((field) => {
          const value = values[field.key] ?? field.default ?? "";
          if (field.type === "boolean") {
            return (
              <FormControlLabel
                key={field.key}
                control={<Switch checked={Boolean(values[field.key] ?? field.default)} onChange={(e) => set(field.key, e.target.checked)} />}
                label={field.label}
              />
            );
          }
          if (field.type === "select") {
            return (
              <TextField key={field.key} select label={field.label} value={String(value)} onChange={(e) => set(field.key, e.target.value)} fullWidth size="small">
                {(field.options ?? []).map((opt) => (
                  <MenuItem key={String(opt.value)} value={String(opt.value)}>{opt.label}</MenuItem>
                ))}
              </TextField>
            );
          }
          return (
            <TextField
              key={field.key}
              label={field.label}
              type={field.type === "number" ? "number" : field.type === "secret" ? "password" : "text"}
              value={value as string | number}
              placeholder={field.placeholder}
              helperText={field.helpText}
              onChange={(e) => set(field.key, field.type === "number" ? Number(e.target.value) : e.target.value)}
              fullWidth
              size="small"
            />
          );
        })}
          </>
        )}

        {gameId ? (
          <>
            <Divider />
            <GameControls gameId={gameId} />
          </>
        ) : null}
      </Stack>

      <Divider sx={{ my: 2 }} />
      <Stack direction="row" spacing={1}>
        <Button variant="outlined" onClick={doSave} disabled={busy} fullWidth>Save</Button>
        <Button variant="contained" onClick={doApply} disabled={busy} fullWidth>Apply</Button>
      </Stack>
    </Drawer>
  );
}
