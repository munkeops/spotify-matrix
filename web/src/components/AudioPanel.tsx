import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, Card, CardContent, Chip, FormControlLabel, MenuItem, Slider, Stack, Switch, TextField, Typography } from "@mui/material";
import VolumeUpRoundedIcon from "@mui/icons-material/VolumeUpRounded";
import { AudioState, getAudio, saveAudioConfig, testAudio } from "../api";

export default function AudioPanel() {
  const [state, setState] = useState<AudioState | null>(null);
  const [volume, setVolume] = useState(80);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");

  const refresh = useCallback(async () => {
    try {
      const next = await getAudio();
      setState(next);
      setVolume(next.volume);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const update = async (patch: Record<string, unknown>) => {
    setBusy(true);
    try {
      const next = await saveAudioConfig(patch);
      setState(next);
      setVolume(next.volume);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setBusy(true);
    setResult("");
    try {
      // Play from the API process, so this works before a game is running.
      const response = await testAudio(state?.sounds?.[0] || "start");
      setResult(response.ok ? response.message : response.message || "Nothing played.");
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
            <VolumeUpRoundedIcon fontSize="small" color="primary" />
            <Typography variant="overline" color="text.secondary" sx={{ flex: 1 }}>Game sound</Typography>
            {state.enabled ? <Chip size="small" color={state.available ? "success" : "warning"} label={state.available ? "Ready" : "No output"} /> : null}
          </Stack>

          {error ? <Alert severity="error">{error}</Alert> : null}
          {result ? <Alert severity="info" onClose={() => setResult("")}>{result}</Alert> : null}
          <Alert severity={state.available ? (state.enabled ? "success" : "info") : "warning"}>
            {state.advice}
          </Alert>

          <FormControlLabel
            control={<Switch checked={state.enabled} disabled={busy} onChange={(e) => update({ enabled: e.target.checked })} />}
            label="Play sound effects in games"
          />

          {state.devices.length > 1 ? (
            <TextField
              select
              size="small"
              label="Output"
              value={state.device || ""}
              disabled={busy}
              onChange={(e) => update({ device: e.target.value })}
            >
              <MenuItem value="">Default output</MenuItem>
              {state.devices.map((device) => (
                <MenuItem key={device.name} value={device.name}>{device.name}</MenuItem>
              ))}
            </TextField>
          ) : null}

          <Box>
            <Typography variant="caption" color="text.secondary">Volume</Typography>
            <Slider
              size="small"
              value={volume}
              min={0}
              max={100}
              disabled={busy}
              onChange={(_, value) => setVolume(value as number)}
              onChangeCommitted={(_, value) => update({ volume: value as number })}
              valueLabelDisplay="auto"
            />
          </Box>

          <Box>
            <Button size="small" variant="outlined" onClick={test} disabled={busy || !state.available}>
              Test sound
            </Button>
          </Box>

          <Typography variant="caption" color="text.secondary">
            Effects are generated chiptune, bundled with each game. Turning this on restarts whatever is
            playing, because the runtime opens the sound card at launch.
          </Typography>
        </Stack>
      </CardContent>
    </Card>
  );
}
