import { useEffect, useState } from "react";
import { Card, CardContent, Typography, Stack, TextField, MenuItem, Switch, FormControlLabel, Button, Box, Alert, Snackbar, CircularProgress } from "@mui/material";
import { getConfig, saveConfig } from "../api";
import BluetoothPanel from "../components/BluetoothPanel";
import JoystickPanel from "../components/JoystickPanel";
import GamepadPanel from "../components/GamepadPanel";
import AudioPanel from "../components/AudioPanel";

const MATRIX_NUMBERS: { key: string; label: string }[] = [
  { key: "rows", label: "Rows" },
  { key: "cols", label: "Cols" },
  { key: "chainLength", label: "Chain" },
  { key: "parallel", label: "Parallel" },
  { key: "brightness", label: "Brightness" },
  { key: "gpioSlowdown", label: "GPIO slowdown" },
  { key: "pwmBits", label: "PWM bits" },
  { key: "limitRefreshRateHz", label: "Refresh cap" },
  { key: "pollSeconds", label: "Poll seconds" },
  { key: "fps", label: "FPS" },
  { key: "rpm", label: "RPM" },
];

export default function Settings() {
  const [config, setConfig] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getConfig().then(setConfig).catch((e) => setError((e as Error).message));
  }, []);

  const setMatrix = (key: string, value: unknown) =>
    setConfig((prev) => (prev ? { ...prev, matrix: { ...prev.matrix, [key]: value } } : prev));

  const setStore = (value: string) =>
    setConfig((prev) => (prev ? { ...prev, store: { ...prev.store, indexUrl: value } } : prev));

  const save = async () => {
    if (!config) return;
    setBusy(true);
    try {
      const updated = await saveConfig(config);
      setConfig(updated);
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!config) {
    return error ? <Alert severity="error">{error}</Alert> : <Box sx={{ display: "grid", placeItems: "center", py: 8 }}><CircularProgress /></Box>;
  }

  return (
    <Stack spacing={2}>
      {error ? <Alert severity="error">{error}</Alert> : null}

      <Card>
        <CardContent>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>Matrix Hardware</Typography>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", sm: "1fr 1fr 1fr" }, gap: 1.5 }}>
            {MATRIX_NUMBERS.map((f) => (
              <TextField key={f.key} label={f.label} type="number" size="small" value={config.matrix?.[f.key] ?? ""} onChange={(e) => setMatrix(f.key, Number(e.target.value))} />
            ))}
            <TextField label="Hardware mapping" size="small" value={config.matrix?.hardwareMapping ?? ""} onChange={(e) => setMatrix("hardwareMapping", e.target.value)} />
            <TextField select label="Rotation" size="small" value={String(config.matrix?.rotation ?? 0)} onChange={(e) => setMatrix("rotation", Number(e.target.value))}>
              {[0, 90, 180, 270].map((r) => <MenuItem key={r} value={String(r)}>{r}°</MenuItem>)}
            </TextField>
          </Box>
          <FormControlLabel
            sx={{ mt: 1 }}
            control={<Switch checked={Boolean(config.matrix?.noHardwarePulse)} onChange={(e) => setMatrix("noHardwarePulse", e.target.checked)} />}
            label="Disable hardware pulsing"
          />
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>Widget Store</Typography>
          <TextField fullWidth size="small" label="Store index URL" value={config.store?.indexUrl ?? ""} onChange={(e) => setStore(e.target.value)} />
        </CardContent>
      </Card>

      <AudioPanel />
      <GamepadPanel />
      <JoystickPanel />
      <BluetoothPanel />

      <Button variant="contained" onClick={save} disabled={busy} sx={{ alignSelf: "flex-start" }}>
        {busy ? "Saving…" : "Save settings"}
      </Button>

      <Snackbar open={saved} autoHideDuration={2000} onClose={() => setSaved(false)} message="Settings saved" />
    </Stack>
  );
}
