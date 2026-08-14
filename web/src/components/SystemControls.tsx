import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Button, MenuItem, Stack, TextField, Typography } from "@mui/material";
import RestartAltRoundedIcon from "@mui/icons-material/RestartAltRounded";
import { SystemControlsState, getJoystick, getSystemControls, resetSystemControls, saveSystemControls } from "../api";
import Field from "./Field";
import ModuleDiagram, { ModuleControl } from "./ModuleDiagram";

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
  const [selected, setSelected] = useState<ModuleControl>("a");
  // Which control the module last reported, so the diagram can light it up.
  const [pressed, setPressed] = useState("");
  const seenAt = useRef(0);

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

  // Poll for presses. The module is the only thing that knows which button
  // is which, so watching it is how the diagram earns its labels.
  useEffect(() => {
    let alive = true;
    const timer = window.setInterval(async () => {
      try {
        const joystick = await getJoystick();
        if (!alive || !joystick.lastControl) return;
        if (joystick.lastControlAt > seenAt.current) {
          seenAt.current = joystick.lastControlAt;
          setPressed(joystick.lastControl);
          setSelected((current) =>
            ["a", "b", "c", "d", "ok"].includes(joystick.lastControl)
              ? (joystick.lastControl as ModuleControl)
              : current,
          );
          window.setTimeout(() => alive && setPressed(""), 350);
        }
      } catch {
        // The module may be absent; the editor still works by tapping.
      }
    }, 400);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

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

      <ModuleDiagram
        bindings={state.bindings}
        labels={state.labels}
        actionLabels={Object.fromEntries(state.actions.map((a) => [a.action, a.label]))}
        selected={selected}
        pressed={pressed}
        onSelect={(control) => setSelected(control)}
      />

      <Field label={`What ${state.labels[selected] ?? selected.toUpperCase()} does`}>
        <TextField
          select
          value={state.bindings[selected] ?? "none"}
          disabled={busy}
          onChange={(e) => rebind(selected, e.target.value)}
        >
          {state.actions.map((action) => (
            <MenuItem key={action.action} value={action.action}>
              {action.label}
            </MenuItem>
          ))}
        </TextField>
      </Field>
    </Stack>
  );
}
