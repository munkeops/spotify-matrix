import SettingsSection from "./SettingsSection";
import VolumeUpRoundedIcon from "@mui/icons-material/VolumeUpRounded";
import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, Chip, FormControlLabel, MenuItem, Slider, Stack, Switch, TextField, Typography } from "@mui/material";
import BluetoothAudioRoundedIcon from "@mui/icons-material/BluetoothAudioRounded";
import HeadphonesRoundedIcon from "@mui/icons-material/HeadphonesRounded";
import SettingsInputHdmiRoundedIcon from "@mui/icons-material/SettingsInputHdmiRounded";
import SpeakerRoundedIcon from "@mui/icons-material/SpeakerRounded";
import UsbRoundedIcon from "@mui/icons-material/UsbRounded";

// An ALSA PCM string says nothing about which box the sound comes out of.
// The icon and the label do, which is the whole point of the list.
const KIND_ICON: Record<string, JSX.Element> = {
  bluetooth: <BluetoothAudioRoundedIcon fontSize="small" color="primary" />,
  headphones: <HeadphonesRoundedIcon fontSize="small" />,
  hdmi: <SettingsInputHdmiRoundedIcon fontSize="small" />,
  usb: <UsbRoundedIcon fontSize="small" />,
  other: <SpeakerRoundedIcon fontSize="small" />,
  default: <SpeakerRoundedIcon fontSize="small" />,
};
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
      // A device that refused the format is a failure, not a status update.
      if (response.ok) setResult(response.message);
      else setError(response.message || "Nothing played.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!state) return null;

  return (
    <SettingsSection
      title="Game sound"
      icon={<VolumeUpRoundedIcon fontSize="small" color="primary" />}
      action={state.enabled ? <Chip size="small" color={state.available ? "success" : "warning"} label={state.available ? "Ready" : "No output"} /> : null}
    >

          {error ? <Alert severity="error">{error}</Alert> : null}
          {result ? <Alert severity="info" onClose={() => setResult("")}>{result}</Alert> : null}
          <Alert severity={state.available ? (state.enabled ? "success" : "info") : "warning"}>
            {state.advice}
          </Alert>
          {state.bridge?.installed && !state.bridge.running ? (
            <Alert severity="warning">{state.bridge.error || "The Bluetooth audio bridge is not running."}</Alert>
          ) : null}

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
              helperText="Bluetooth speakers appear here once they are connected and paired."
            >
              <MenuItem value="">System default</MenuItem>
              {state.devices.map((device) => (
                <MenuItem key={device.name} value={device.name}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    {KIND_ICON[device.kind || "other"] || KIND_ICON.other}
                    <span>{device.label || device.name}</span>
                  </Stack>
                </MenuItem>
              ))}
            </TextField>
          ) : null}

          <TextField
            select
            size="small"
            label="Audio delay"
            value={String(state.bufferMs ?? 120)}
            disabled={busy}
            onChange={(e) => update({ bufferMs: Number(e.target.value) })}
            helperText="How much the sound card may hold. Lower is tighter to the picture; too low and it crackles."
          >
            <MenuItem value="60">Tight (60ms)</MenuItem>
            <MenuItem value="120">Balanced (120ms)</MenuItem>
            <MenuItem value="250">Safe (250ms)</MenuItem>
          </TextField>

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
    </SettingsSection>
  );
}
