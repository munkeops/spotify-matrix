import { useEffect, useState } from "react";
import { Typography, Stack, TextField, MenuItem, Switch, FormControlLabel, Button, Box, Alert, Snackbar, CircularProgress } from "@mui/material";
import { getConfig, saveConfig } from "../api";
import BluetoothPanel from "../components/BluetoothPanel";
import JoystickPanel from "../components/JoystickPanel";
import GamepadPanel from "../components/GamepadPanel";
import AudioPanel from "../components/AudioPanel";
import DisplayPreview from "../components/DisplayPreview";
import DriverSelect from "../components/DriverSelect";
import Field from "../components/Field";
import SettingsSection from "../components/SettingsSection";
import TuneRoundedIcon from "@mui/icons-material/TuneRounded";
import StorefrontRoundedIcon from "@mui/icons-material/StorefrontRounded";

const MATRIX_NUMBERS: { key: string; label: string; help?: string }[] = [
  { key: "rows", label: "Rows" },
  { key: "cols", label: "Cols" },
  { key: "chainLength", label: "Chain" },
  { key: "parallel", label: "Parallel" },
  { key: "brightness", label: "Brightness", help: "0-100. The panel's duty cycle." },
  { key: "gpioSlowdown", label: "GPIO slowdown", help: "Lowest value that is stable. Higher costs refresh, and so brightness." },
  { key: "pwmBits", label: "PWM bits", help: "Colour depth. 11 is richest, 8 refreshes far faster and looks brighter." },
  { key: "pwmDitherBits", label: "Dither bits", help: "Spreads the lowest colour bits across frames. 1 buys a lot of refresh for little depth." },
  { key: "pwmLsbNanoseconds", label: "LSB nanoseconds", help: "Time for the shortest colour pulse. 130 is standard; raising it costs refresh fast." },
  { key: "limitRefreshRateHz", label: "Refresh cap", help: "0 removes the cap. A steady capped rate flickers less than a higher wandering one." },
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

      <SettingsSection title="Matrix Hardware" icon={<TuneRoundedIcon fontSize="small" color="primary" />}>

          <Box sx={{ mb: 2.5 }}>
            <DisplayPreview
              rotation={Number(config.matrix?.rotation ?? 0)}
              brightness={Number(config.matrix?.brightness ?? 100)}
              rows={Number(config.matrix?.rows ?? 64)}
              cols={Number(config.matrix?.cols ?? 64)}
            />
          </Box>

          <Box sx={{ mb: 2 }}>
            <DriverSelect
              hardwareMapping={String(config.matrix?.hardwareMapping ?? "")}
              onSwitched={(saved) => setConfig(saved)}
            />
          </Box>

          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", sm: "1fr 1fr 1fr" }, gap: 1.5 }}>
            {MATRIX_NUMBERS.map((f) => (
              <Field key={f.key} label={f.label} help={f.help}>
                <TextField
                  type="number"
                  value={config.matrix?.[f.key] ?? ""}
                  onChange={(e) => setMatrix(f.key, Number(e.target.value))}
                />
              </Field>
            ))}
            <Field label="Hardware mapping">
              <TextField value={config.matrix?.hardwareMapping ?? ""} onChange={(e) => setMatrix("hardwareMapping", e.target.value)} />
            </Field>
            <Field label="Rotation" help="Previewed above.">
              <TextField select value={String(config.matrix?.rotation ?? 0)} onChange={(e) => setMatrix("rotation", Number(e.target.value))}>
                {[0, 90, 180, 270].map((r) => <MenuItem key={r} value={String(r)}>{r}°</MenuItem>)}
              </TextField>
            </Field>
            <Field label="Panel type" help="Blank for most. FM6126A panels need naming here or they stay dark.">
              <TextField select value={String(config.matrix?.panelType ?? "")} onChange={(e) => setMatrix("panelType", e.target.value)}>
                <MenuItem value="">Standard</MenuItem>
                <MenuItem value="FM6126A">FM6126A</MenuItem>
                <MenuItem value="FM6127">FM6127</MenuItem>
              </TextField>
            </Field>
          </Box>
          <FormControlLabel
            sx={{ mt: 1 }}
            control={<Switch checked={Boolean(config.matrix?.noHardwarePulse)} onChange={(e) => setMatrix("noHardwarePulse", e.target.checked)} />}
            label="Disable hardware pulsing"
          />
          <Typography variant="caption" color="text.secondary" component="p">
            On, the panel is driven by a software timer, which costs a lot of refresh and
            is the single biggest reason a matrix looks dim. It is only needed while the
            Pi's onboard sound driver is loaded. Game sound here goes out over HDMI or
            Bluetooth, neither of which uses it, so on most setups you can blacklist
            snd_bcm2835 on the Pi and turn this off.
          </Typography>
          <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 1 }}>
            If it is still dim with all of the above, it is usually the supply: a 64x64
            panel at full white pulls close to 4A at 5V, and thin wiring drops enough
            volts to grey the whites out.
          </Typography>
      </SettingsSection>

      <SettingsSection title="App Store" icon={<StorefrontRoundedIcon fontSize="small" color="primary" />}>
          <TextField fullWidth size="small" label="Store index URL" value={config.store?.indexUrl ?? ""} onChange={(e) => setStore(e.target.value)} />
      </SettingsSection>

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
