import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, Typography, Stack, Chip, Switch, Box, CircularProgress, Alert, FormControlLabel } from "@mui/material";
import { apiGet, apiPost, StatusResponse, listLocalWidgets, getWidgetConfig, previewWidget, LocalWidget, PREVIEWABLE } from "../api";

const CATEGORY_COLOR: Record<string, string> = {
  media: "#4be0c0", time: "#8ea2ff", assistant: "#ffb86b", information: "#7ee0a0",
  custom: "#c58cff", diagnostics: "#ff8c8c", weather: "#66d0ff",
};

export default function Dashboard() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [active, setActive] = useState<LocalWidget | null>(null);
  const [preview, setPreview] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [st, widgets] = await Promise.all([apiGet<StatusResponse>("/api/status"), listLocalWidgets()]);
      setStatus(st);
      const activeWidget = (widgets.widgets || []).find((w) => w.active) || null;
      setActive(activeWidget);
      setError("");
      if (activeWidget && PREVIEWABLE.has(activeWidget.manifest.id)) {
        try {
          const cfg = await getWidgetConfig(activeWidget.manifest.id);
          const p = await previewWidget(activeWidget.manifest.id, cfg.config);
          setPreview(p.dataUrl);
        } catch { setPreview(""); }
      } else {
        setPreview("");
      }
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
    return <Box sx={{ display: "grid", placeItems: "center", py: 8 }}><CircularProgress /></Box>;
  }

  const running = status?.runtime.running ?? false;
  const activeColor = active ? CATEGORY_COLOR[active.manifest.category] || "#4be0c0" : "#4be0c0";

  return (
    <Stack spacing={2}>
      {error ? <Alert severity="error">{error}</Alert> : null}

      <Card>
        <CardContent>
          <Typography variant="overline" color="text.secondary">On screen now</Typography>
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mt: 1 }}>
            <Box sx={{ width: 96, height: 96, borderRadius: 2, overflow: "hidden", flexShrink: 0, bgcolor: "#050607", display: "grid", placeItems: "center", border: "1px solid", borderColor: "divider" }}>
              {preview ? (
                <img src={preview} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", imageRendering: "pixelated" }} />
              ) : (
                <Typography sx={{ fontSize: 34, fontWeight: 800, color: activeColor }}>
                  {active ? active.manifest.name.charAt(0) : "—"}
                </Typography>
              )}
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="h6" noWrap>{active ? active.manifest.name : "Nothing selected"}</Typography>
              <Stack direction="row" spacing={1} sx={{ mt: 0.5 }} flexWrap="wrap" useFlexGap>
                <Chip size="small" color={running ? "success" : "default"} label={running ? "Running" : "Stopped"} />
                {active ? <Chip size="small" variant="outlined" label={active.manifest.category} /> : null}
              </Stack>
            </Box>
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Box>
              <Typography variant="overline" color="text.secondary">Display power</Typography>
              <Typography variant="h6">{running ? "On" : "Off"}</Typography>
            </Box>
            <FormControlLabel
              control={<Switch checked={running} disabled={busy} onChange={(e) => togglePower(e.target.checked)} />}
              label=""
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
