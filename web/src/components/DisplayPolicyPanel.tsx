import { useEffect, useState } from "react";
import {
  Accordion, AccordionSummary, AccordionDetails, Typography, Stack, TextField, MenuItem,
  Button, Box, Switch, FormControlLabel, Alert,
} from "@mui/material";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import { DisplayPolicy, getPolicy, savePolicy, applyPolicy, stopPolicy, listLocalWidgets, LocalWidget } from "../api";

export default function DisplayPolicyPanel() {
  const [policy, setPolicy] = useState<DisplayPolicy | null>(null);
  const [widgets, setWidgets] = useState<LocalWidget[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([getPolicy(), listLocalWidgets()])
      .then(([p, w]) => { setPolicy(p.policy); setWidgets(w.widgets || []); })
      .catch((e) => setError((e as Error).message));
  }, []);

  if (!policy) return null;

  const toggleRotation = (widgetId: string) => {
    const exists = policy.rotation.find((r) => r.widgetId === widgetId);
    const rotation = exists
      ? policy.rotation.map((r) => (r.widgetId === widgetId ? { ...r, enabled: !r.enabled } : r))
      : [...policy.rotation, { widgetId, durationSeconds: 15, enabled: true }];
    setPolicy({ ...policy, rotation });
  };
  const setDuration = (widgetId: string, durationSeconds: number) =>
    setPolicy({ ...policy, rotation: policy.rotation.map((r) => (r.widgetId === widgetId ? { ...r, durationSeconds } : r)) });

  const save = async (apply: boolean) => {
    setBusy(true);
    try {
      await savePolicy(policy);
      if (apply) await applyPolicy();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Accordion disableGutters sx={{ bgcolor: "background.paper", border: "1px solid", borderColor: "divider", borderRadius: 2, "&:before": { display: "none" } }}>
      <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
        <Typography sx={{ fontWeight: 600 }}>Display Policy</Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Stack spacing={2}>
          {error ? <Alert severity="error">{error}</Alert> : null}
          <TextField select label="Mode" size="small" value={policy.mode} onChange={(e) => setPolicy({ ...policy, mode: e.target.value as DisplayPolicy["mode"] })}>
            <MenuItem value="single">Single widget</MenuItem>
            <MenuItem value="rotation">Rotate widgets</MenuItem>
          </TextField>

          {policy.mode === "single" ? (
            <TextField select label="Active widget" size="small" value={policy.activeWidgetId} onChange={(e) => setPolicy({ ...policy, activeWidgetId: e.target.value })}>
              {widgets.map((w) => <MenuItem key={w.manifest.id} value={w.manifest.id}>{w.manifest.name}</MenuItem>)}
            </TextField>
          ) : (
            <Stack spacing={0.5}>
              {widgets.map((w) => {
                const item = policy.rotation.find((r) => r.widgetId === w.manifest.id);
                return (
                  <Box key={w.manifest.id} sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
                    <FormControlLabel control={<Switch checked={Boolean(item?.enabled)} onChange={() => toggleRotation(w.manifest.id)} />} label={w.manifest.name} />
                    {item?.enabled ? (
                      <TextField type="number" size="small" label="sec" sx={{ width: 90 }} value={item.durationSeconds} onChange={(e) => setDuration(w.manifest.id, Number(e.target.value))} />
                    ) : null}
                  </Box>
                );
              })}
            </Stack>
          )}

          <Stack direction="row" spacing={1}>
            <Button variant="outlined" onClick={() => save(false)} disabled={busy}>Save</Button>
            <Button variant="contained" onClick={() => save(true)} disabled={busy}>Apply</Button>
            <Button color="error" onClick={async () => { setBusy(true); try { await stopPolicy(); } finally { setBusy(false); } }} disabled={busy}>Stop</Button>
          </Stack>
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
}
