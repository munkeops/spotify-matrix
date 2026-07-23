import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, Typography, Stack, Chip, Switch, Box, CircularProgress, Alert, FormControlLabel } from "@mui/material";
import { apiGet, apiPost, StatusResponse } from "../api";

export default function Dashboard() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setStatus(await apiGet<StatusResponse>("/api/status"));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  const togglePower = async (on: boolean) => {
    setBusy(true);
    try {
      await apiPost(on ? "/api/runtime/apply" : "/api/runtime/stop", {});
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!status && !error) {
    return (
      <Box sx={{ display: "grid", placeItems: "center", py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  const running = status?.runtime.running ?? false;

  return (
    <Stack spacing={2}>
      {error ? <Alert severity="error">{error}</Alert> : null}

      <Card>
        <CardContent>
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Box>
              <Typography variant="overline" color="text.secondary">Display</Typography>
              <Typography variant="h6">{running ? "Running" : "Stopped"}</Typography>
            </Box>
            <FormControlLabel
              control={<Switch checked={running} disabled={busy} onChange={(e) => togglePower(e.target.checked)} />}
              label={running ? "On" : "Off"}
              labelPlacement="start"
            />
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Stack spacing={1}>
            <Typography variant="overline" color="text.secondary">Status</Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip color={status?.configured ? "success" : "warning"} label={status?.configured ? "Configured" : "Setup needed"} size="small" />
              <Chip variant="outlined" label={`Data: ${status?.dataDir ?? "—"}`} size="small" />
            </Stack>
            {status && status.missing.length > 0 ? (
              <Typography variant="body2" color="text.secondary">Missing: {status.missing.join(", ")}</Typography>
            ) : null}
          </Stack>
        </CardContent>
      </Card>
    </Stack>
  );
}
