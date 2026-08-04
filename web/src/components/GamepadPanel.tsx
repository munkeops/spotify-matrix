import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Card, CardContent, Chip, FormControlLabel, MenuItem, Stack, Switch, TextField, Typography } from "@mui/material";
import { GamepadState, getGamepad, saveGamepadConfig } from "../api";

export default function GamepadPanel() {
  const [state, setState] = useState<GamepadState | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setState(await getGamepad());
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    refresh();
    // A pad can be paired at any moment, so keep looking.
    const timer = setInterval(refresh, 4000);
    return () => clearInterval(timer);
  }, [refresh]);

  const update = async (patch: Record<string, unknown>) => {
    setBusy(true);
    try {
      setState(await saveGamepadConfig(patch));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!state) return null;

  return (
    <Card>
      <CardContent>
        <Stack spacing={1.5}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <Typography variant="overline" color="text.secondary" sx={{ flex: 1 }}>Game controller</Typography>
            {state.enabled ? (
              <Chip
                size="small"
                color={state.connected ? "success" : "warning"}
                label={state.connected ? state.deviceName || "Connected" : state.running ? "Searching" : "Stopped"}
              />
            ) : null}
          </Stack>

          {error ? <Alert severity="error">{error}</Alert> : null}
          {state.lastError ? <Alert severity="warning">{state.lastError}</Alert> : null}

          <FormControlLabel
            control={<Switch checked={state.enabled} disabled={busy} onChange={(e) => update({ enabled: e.target.checked })} />}
            label="Use a game controller"
          />

          <Alert severity={state.connected ? "success" : state.devices.length ? "info" : "warning"}>
            <Typography variant="body2">{state.advice}</Typography>
          </Alert>

          {state.devices.length > 1 ? (
            <TextField
              select
              size="small"
              label="Controller"
              value={state.device || ""}
              disabled={busy}
              onChange={(e) => update({ device: e.target.value })}
            >
              <MenuItem value="">First one found</MenuItem>
              {state.devices.map((device) => (
                <MenuItem key={device.path} value={device.path}>
                  {device.name}{device.wireless ? " (bluetooth)" : ""}
                </MenuItem>
              ))}
            </TextField>
          ) : null}

          {!state.devices.length && state.inputDevices?.length ? (
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                Input devices the container can see
              </Typography>
              {state.inputDevices.map((device) => (
                <Typography key={device.path} variant="caption" sx={{ display: "block", fontFamily: "monospace" }}>
                  {device.name} — {device.buttons} keys, {device.axes} axes
                  {device.isGamepad ? "  (gamepad)" : ""}
                </Typography>
              ))}
            </Box>
          ) : null}

          {state.devices.length ? (
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>Detected</Typography>
              {state.devices.map((device) => (
                <Typography key={device.path} variant="caption" sx={{ display: "block", fontFamily: "monospace" }}>
                  {device.name} — {device.path}{device.wireless ? "  (bluetooth)" : ""}
                </Typography>
              ))}
            </Box>
          ) : null}

          <Typography variant="caption" color="text.secondary">
            D-pad or left stick moves, A is the action button, B and X rotate or hold, Start pauses.
            Pair the pad under Bluetooth below first.
          </Typography>
        </Stack>
      </CardContent>
    </Card>
  );
}
