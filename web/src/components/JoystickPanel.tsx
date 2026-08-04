import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Card, CardContent, Chip, FormControlLabel, Stack, Switch, TextField, Typography } from "@mui/material";
import { JoystickState, getJoystick, saveJoystickConfig } from "../api";

export default function JoystickPanel() {
  const [state, setState] = useState<JoystickState | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setState(await getJoystick());
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    refresh();
    // Reflect the module being plugged in or pulled out.
    const timer = setInterval(refresh, 4000);
    return () => clearInterval(timer);
  }, [refresh]);

  const update = async (patch: Record<string, unknown>) => {
    setBusy(true);
    try {
      setState(await saveJoystickConfig(patch));
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
            <Typography variant="overline" color="text.secondary" sx={{ flex: 1 }}>Mini-joystick</Typography>
            {state.enabled ? (
              <Chip
                size="small"
                color={state.connected ? "success" : "warning"}
                label={state.connected ? "Connected" : state.running ? "Searching" : "Stopped"}
              />
            ) : null}
          </Stack>

          {error ? <Alert severity="error">{error}</Alert> : null}
          {state.enabled && state.lastError ? <Alert severity="warning">{state.lastError}</Alert> : null}

          <FormControlLabel
            control={<Switch checked={state.enabled} disabled={busy} onChange={(e) => update({ enabled: e.target.checked })} />}
            label="Use the joystick module"
          />

          {state.enabled ? (
            <>
              <Stack direction="row" spacing={1}>
                <TextField
                  label="I²C bus"
                  type="number"
                  size="small"
                  value={state.bus}
                  disabled={busy}
                  onChange={(e) => update({ bus: Number(e.target.value) })}
                  sx={{ width: 110 }}
                />
                <TextField
                  label="Address"
                  size="small"
                  value={`0x${state.address.toString(16)}`}
                  disabled
                  sx={{ width: 110 }}
                />
              </Stack>
              <Typography variant="caption" color="text.secondary">
                Drives whichever game is on the panel, and flicks through plugins when none is.
                The module is 5V — use a level shifter on SDA and SCL.
              </Typography>
              {state.lastAction ? (
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>Last input</Typography>
                  <Typography variant="body2">{state.lastAction}</Typography>
                </Box>
              ) : null}
            </>
          ) : null}
        </Stack>
      </CardContent>
    </Card>
  );
}
