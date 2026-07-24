import { useEffect, useState, useCallback } from "react";
import {
  Card, CardContent, CardActions, Typography, Stack, Chip, Button, Box, CircularProgress, Alert,
} from "@mui/material";
import TuneRoundedIcon from "@mui/icons-material/TuneRounded";
import { LocalWidget, listLocalWidgets, applyWidget } from "../api";
import WidgetConfigDrawer from "../components/WidgetConfigDrawer";
import DisplayPolicyPanel from "../components/DisplayPolicyPanel";

export default function Plugins() {
  const [widgets, setWidgets] = useState<LocalWidget[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<LocalWidget | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [applyingId, setApplyingId] = useState("");

  const refresh = useCallback(async () => {
    try {
      const r = await listLocalWidgets();
      setWidgets(r.widgets || []);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const runNow = async (widget: LocalWidget) => {
    setApplyingId(widget.manifest.id);
    try {
      await applyWidget(widget.manifest.id, null);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setApplyingId("");
    }
  };

  const openSettings = (widget: LocalWidget) => {
    setSelected(widget);
    setDrawerOpen(true);
  };

  if (loading) {
    return <Box sx={{ display: "grid", placeItems: "center", py: 8 }}><CircularProgress /></Box>;
  }

  return (
    <Stack spacing={2}>
      {error ? <Alert severity="error">{error}</Alert> : null}

      <DisplayPolicyPanel />

      {widgets.map((widget) => (
        <Card key={widget.manifest.id} sx={{ borderColor: widget.active ? "primary.main" : "divider" }}>
          <CardContent sx={{ pb: 1 }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{widget.manifest.name}</Typography>
              {widget.active ? <Chip label="Active" color="primary" size="small" /> : null}
              <Chip label={widget.manifest.category} size="small" variant="outlined" />
            </Stack>
            <Typography variant="body2" color="text.secondary">{widget.manifest.summary}</Typography>
          </CardContent>
          <CardActions sx={{ px: 2, pb: 2 }}>
            <Button variant="contained" size="small" disabled={applyingId === widget.manifest.id} onClick={() => runNow(widget)}>
              {applyingId === widget.manifest.id ? "Applying…" : widget.active ? "Running" : "Run"}
            </Button>
            {widget.configurable ? (
              <Button size="small" startIcon={<TuneRoundedIcon />} onClick={() => openSettings(widget)}>Settings</Button>
            ) : null}
          </CardActions>
        </Card>
      ))}

      <Card component="a" href="/studio/" sx={{ textDecoration: "none" }}>
        <CardContent>
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>Meme Studio</Typography>
          <Typography variant="body2" color="text.secondary">Draw, add text, and store memes. Opens the editor.</Typography>
        </CardContent>
      </Card>

      <WidgetConfigDrawer
        widget={selected}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onApplied={refresh}
      />
    </Stack>
  );
}
