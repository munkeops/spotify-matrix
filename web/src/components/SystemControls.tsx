import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, MenuItem, Stack, TextField, Typography } from "@mui/material";
import RestartAltRoundedIcon from "@mui/icons-material/RestartAltRounded";
import { SystemControlsState, getSystemControls, resetSystemControls, saveSystemControls } from "../api";

/**
 * What each button on the mini-joystick does while it is on device duty.
 *
 * The silkscreen order says nothing about where a button sits under a thumb,
 * so brighter and dimmer arrived on buttons that are not a pair. This is the
 * screen for putting them where they belong.
 */
export default function SystemControls() {
  const [state, setState] = useState<SystemControlsState | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setState(await getSystemControls());
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!state) return error ? <Alert severity="error">{error}</Alert> : null;

  const rebind = async (control: string, action: string) => {
    const bindings = { ...state.bindings, [control]: action };
    setState({ ...state, bindings });
    setBusy(true);
    try {
      setState(await saveSystemControls(bindings));
      setError("");
    } catch (e) {
      setError((e as Error).message);
      await load();
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    setBusy(true);
    try {
      setState(await resetSystemControls());
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack spacing={2}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Typography variant="overline" color="text.secondary" sx={{ flex: 1 }}>
          Device buttons
        </Typography>
        {state.customised.length ? (
          <Button size="small" startIcon={<RestartAltRoundedIcon />} onClick={reset} disabled={busy}>
            Reset
          </Button>
        ) : null}
      </Stack>

      <Typography variant="caption" color="text.secondary">
        What each button on the module does while it is on device duty. Pair brighter with
        dimmer, and louder with quieter, on buttons that sit together.
      </Typography>

      {error ? <Alert severity="error">{error}</Alert> : null}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 1.5 }}>
        {state.controls.map((control) => (
          <TextField
            key={control}
            select
            size="small"
            label={state.labels[control] ?? control.toUpperCase()}
            value={state.bindings[control] ?? "none"}
            disabled={busy}
            onChange={(e) => rebind(control, e.target.value)}
            focused={state.customised.includes(control) || undefined}
            color={state.customised.includes(control) ? "primary" : undefined}
          >
            {state.actions.map((action) => (
              <MenuItem key={action.action} value={action.action}>
                {action.label}
              </MenuItem>
            ))}
          </TextField>
        ))}
      </Box>
    </Stack>
  );
}
