import { useCallback, useEffect, useState } from "react";
import {
  Alert, Box, Button, Chip, MenuItem, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography,
} from "@mui/material";
import RestartAltRoundedIcon from "@mui/icons-material/RestartAltRounded";
import { GameBindings, getGameBindings, resetGameBindings, saveGameBindings } from "../api";

/** Turn a camelCase action into something readable: rotateCcw -> Rotate ccw. */
function actionLabel(action: string): string {
  const spaced = action.replace(/([A-Z])/g, " $1").toLowerCase().trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

const DIRECTIONS = ["up", "down", "left", "right"];

export default function GameControls({ gameId }: { gameId: string }) {
  const [device, setDevice] = useState<string>("");
  const [state, setState] = useState<GameBindings | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    async (which: string) => {
      try {
        const next = await getGameBindings(gameId, which);
        setState(next);
        setDevice(next.profile);
        setError("");
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [gameId],
  );

  useEffect(() => {
    if (gameId) void load(device);
    // Only reload when the game or the chosen device changes.
  }, [gameId, device, load]);

  if (!state) {
    return error ? <Alert severity="error">{error}</Alert> : null;
  }

  const rebind = async (control: string, action: string) => {
    const bindings = { ...state.bindings, [control]: action };
    setState({ ...state, bindings });
    setBusy(true);
    try {
      setState(await saveGameBindings(gameId, state.profile, bindings));
      setError("");
    } catch (e) {
      setError((e as Error).message);
      await load(state.profile);
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    setBusy(true);
    try {
      setState(await resetGameBindings(gameId, state.profile));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const sticks = state.controls.filter((c) => DIRECTIONS.includes(c));
  const buttons = state.controls.filter((c) => !DIRECTIONS.includes(c));

  const row = (control: string) => (
    <TextField
      key={control}
      select
      size="small"
      fullWidth
      label={state.labels?.[control] ?? control.toUpperCase()}
      value={state.bindings[control] ?? "none"}
      disabled={busy}
      onChange={(e) => rebind(control, e.target.value)}
      // A control the player has moved off its default is worth pointing out,
      // otherwise a surprising mapping looks like a bug rather than a choice.
      color={state.customised.includes(control) ? "primary" : undefined}
      focused={state.customised.includes(control) || undefined}
    >
      <MenuItem value="none">
        <em>Nothing</em>
      </MenuItem>
      {state.actions.map((action) => (
        <MenuItem key={action} value={action}>
          {actionLabel(action)}
        </MenuItem>
      ))}
    </TextField>
  );

  return (
    <Stack spacing={2}>
      <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap" useFlexGap>
        <Typography variant="overline" color="text.secondary" sx={{ flex: 1 }}>
          Controls
        </Typography>
        {state.customised.length ? (
          <Button size="small" startIcon={<RestartAltRoundedIcon />} onClick={reset} disabled={busy}>
            Reset
          </Button>
        ) : null}
      </Stack>

      <ToggleButtonGroup
        size="small"
        exclusive
        value={state.profile}
        onChange={(_, next) => next && setDevice(next)}
        fullWidth
      >
        {state.profiles.map((profile) => (
          <ToggleButton key={profile.id} value={profile.id} sx={{ textTransform: "none" }}>
            <Stack direction="row" alignItems="center" spacing={0.75}>
              <span>{profile.name}</span>
              {profile.present ? <Chip size="small" color="success" label="on" /> : null}
            </Stack>
          </ToggleButton>
        ))}
      </ToggleButtonGroup>

      <Typography variant="caption" color="text.secondary">
        Each device keeps its own mapping, so changing this one leaves the other alone.
      </Typography>

      {error ? <Alert severity="error">{error}</Alert> : null}

      <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1.5 }}>{sticks.map(row)}</Box>
      <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1.5 }}>{buttons.map(row)}</Box>
    </Stack>
  );
}
