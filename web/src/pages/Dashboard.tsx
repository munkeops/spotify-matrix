import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, Typography, Stack, Chip, Switch, Box, CircularProgress, Alert, IconButton } from "@mui/material";
import PowerSettingsNewRoundedIcon from "@mui/icons-material/PowerSettingsNewRounded";
import { apiGet, apiPost, StatusResponse, listLocalWidgets, getWidgetConfig, previewWidget, applyWidget, LocalWidget, PREVIEWABLE } from "../api";

const CATEGORY_COLOR: Record<string, string> = {
  media: "#4be0c0", time: "#8ea2ff", assistant: "#ffb86b", information: "#7ee0a0",
  custom: "#c58cff", diagnostics: "#ff8c8c", weather: "#66d0ff",
};
const color = (w?: LocalWidget | null) => (w ? CATEGORY_COLOR[w.manifest.category] || "#4be0c0" : "#4be0c0");

export default function Dashboard() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [widgets, setWidgets] = useState<LocalWidget[]>([]);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [switching, setSwitching] = useState("");

  const loadPreviews = useCallback(async (list: LocalWidget[]) => {
    await Promise.all(list.filter((w) => PREVIEWABLE.has(w.manifest.id)).map(async (w) => {
      try {
        const cfg = await getWidgetConfig(w.manifest.id);
        const p = await previewWidget(w.manifest.id, cfg.config);
        setPreviews((prev) => ({ ...prev, [w.manifest.id]: p.dataUrl }));
      } catch { /* ignore */ }
    }));
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [st, w] = await Promise.all([apiGet<StatusResponse>("/api/status"), listLocalWidgets()]);
      setStatus(st);
      setWidgets(w.widgets || []);
      setError("");
      loadPreviews(w.widgets || []);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [loadPreviews]);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  const togglePower = async (on: boolean) => {
    setBusy(true);
    try { await apiPost(on ? "/api/runtime/apply" : "/api/runtime/stop", {}); await refresh(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const runWidget = async (w: LocalWidget) => {
    setSwitching(w.manifest.id);
    try { await applyWidget(w.manifest.id, null); await refresh(); }
    catch (e) { setError((e as Error).message); }
    finally { setSwitching(""); }
  };

  if (!status && !error) {
    return <Box sx={{ display: "grid", placeItems: "center", py: 8 }}><CircularProgress /></Box>;
  }

  const running = status?.runtime.running ?? false;
  const active = widgets.find((w) => w.active) || null;
  const accent = color(active);

  return (
    <Stack spacing={2}>
      {error ? <Alert severity="error">{error}</Alert> : null}

      {/* Hero: the matrix screen */}
      <Card>
        <CardContent>
          <Stack alignItems="center" spacing={2}>
            <Box sx={{ p: 2, borderRadius: 4, bgcolor: "#04060a", border: "1px solid", borderColor: "divider", boxShadow: running ? `0 0 48px ${accent}44` : "none", transition: "box-shadow .4s ease" }}>
              <Box sx={{ width: { xs: 220, sm: 280 }, height: { xs: 220, sm: 280 }, borderRadius: 2, overflow: "hidden", bgcolor: "#000", display: "grid", placeItems: "center" }}>
                {active && previews[active.manifest.id] ? (
                  <img src={previews[active.manifest.id]} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", imageRendering: "pixelated", opacity: running ? 1 : 0.5 }} />
                ) : (
                  <Typography sx={{ fontSize: 64, fontWeight: 800, color: accent, opacity: running ? 1 : 0.4 }}>
                    {active ? active.manifest.name.charAt(0) : "—"}
                  </Typography>
                )}
              </Box>
            </Box>

            <Stack direction="row" alignItems="center" spacing={2} sx={{ width: "100%", justifyContent: "space-between" }}>
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="overline" color="text.secondary">On screen now</Typography>
                <Typography variant="h6" noWrap>{active ? active.manifest.name : "Nothing selected"}</Typography>
                <Chip size="small" color={running ? "success" : "default"} label={running ? "Running" : "Stopped"} sx={{ mt: 0.5 }} />
              </Box>
              <IconButton
                onClick={() => togglePower(!running)}
                disabled={busy}
                sx={{ bgcolor: running ? accent : "action.selected", color: running ? "#04060a" : "text.secondary", width: 56, height: 56, "&:hover": { bgcolor: running ? accent : "action.selected", filter: "brightness(1.1)" } }}
              >
                <PowerSettingsNewRoundedIcon />
              </IconButton>
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      {/* Quick switch */}
      {widgets.length > 0 ? (
        <Card>
          <CardContent>
            <Typography variant="overline" color="text.secondary">Quick switch</Typography>
            <Box sx={{ display: "flex", gap: 1.5, overflowX: "auto", pb: 1, mt: 1 }}>
              {widgets.map((w) => {
                const c = color(w);
                return (
                  <Box key={w.manifest.id} onClick={() => runWidget(w)} sx={{ flex: "0 0 auto", width: 84, cursor: "pointer", opacity: switching === w.manifest.id ? 0.5 : 1 }}>
                    <Box sx={{ width: 84, height: 84, borderRadius: 2, overflow: "hidden", bgcolor: "#050607", border: "2px solid", borderColor: w.active ? "primary.main" : "transparent", display: "grid", placeItems: "center" }}>
                      {previews[w.manifest.id] ? (
                        <img src={previews[w.manifest.id]} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", imageRendering: "pixelated" }} />
                      ) : (
                        <Typography sx={{ fontSize: 26, fontWeight: 800, color: c }}>{w.manifest.name.charAt(0)}</Typography>
                      )}
                    </Box>
                    <Typography variant="caption" noWrap sx={{ display: "block", textAlign: "center", mt: 0.5 }}>{w.manifest.name}</Typography>
                  </Box>
                );
              })}
            </Box>
          </CardContent>
        </Card>
      ) : (
        <Alert severity="info">No plugins installed yet — head to the Store to add some.</Alert>
      )}

      {/* Status */}
      <Card>
        <CardContent>
          <Stack spacing={1}>
            <Typography variant="overline" color="text.secondary">Status</Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip color={status?.configured ? "success" : "warning"} label={status?.configured ? "Configured" : "Setup needed"} size="small" />
              <Chip variant="outlined" label={`${widgets.length} plugin${widgets.length === 1 ? "" : "s"}`} size="small" />
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
