import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardActionArea, Typography, Box, CircularProgress, Alert, Chip, IconButton, Stack } from "@mui/material";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import { canPreview, gameIdOf, isGame, LocalWidget, listLocalWidgets, applyWidget, getWidgetConfig, previewWidget } from "../api";
import WidgetConfigDrawer from "../components/WidgetConfigDrawer";
import DisplayPolicyPanel from "../components/DisplayPolicyPanel";

const CATEGORY_COLOR: Record<string, string> = {
  media: "#4be0c0", time: "#8ea2ff", assistant: "#ffb86b", information: "#7ee0a0",
  custom: "#c58cff", diagnostics: "#ff8c8c", weather: "#66d0ff", games: "#ff7ab8",
};

function Placeholder({ widget }: { widget: LocalWidget }) {
  const color = CATEGORY_COLOR[widget.manifest.category] || "#4be0c0";
  return (
    <Box sx={{ width: "100%", height: "100%", display: "grid", placeItems: "center", background: `radial-gradient(circle at 50% 35%, ${color}22, #050607 75%)` }}>
      <Typography sx={{ fontSize: 34, fontWeight: 800, color }}>{widget.manifest.name.charAt(0)}</Typography>
    </Box>
  );
}

export default function Plugins() {
  const navigate = useNavigate();
  const [widgets, setWidgets] = useState<LocalWidget[]>([]);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<LocalWidget | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [applyingId, setApplyingId] = useState("");

  const loadPreviews = useCallback(async (list: LocalWidget[]) => {
    await Promise.all(
      list
        .filter((w) => canPreview(w))
        .map(async (w) => {
          try {
            const cfg = await getWidgetConfig(w.manifest.id);
            const p = await previewWidget(w.manifest.id, cfg.config);
            setPreviews((prev) => ({ ...prev, [w.manifest.id]: p.dataUrl }));
          } catch {
            /* ignore */
          }
        }),
    );
  }, []);

  const refresh = useCallback(async () => {
    try {
      const r = await listLocalWidgets();
      setWidgets(r.widgets || []);
      setError("");
      loadPreviews(r.widgets || []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [loadPreviews]);

  useEffect(() => { refresh(); }, [refresh]);

  const runNow = async (widget: LocalWidget) => {
    setApplyingId(widget.manifest.id);
    try {
      await applyWidget(widget.manifest.id, null);
      await refresh();
      if (isGame(widget)) navigate(`/play/${gameIdOf(widget)}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setApplyingId("");
    }
  };

  const openSettings = (widget: LocalWidget) => {
    if (!widget.configurable) { runNow(widget); return; }
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

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(auto-fill, minmax(150px, 1fr))" }, gap: 1.5 }}>
        {widgets.map((widget) => {
          const id = widget.manifest.id;
          return (
            <Card key={id} sx={{ position: "relative", borderColor: widget.active ? "primary.main" : "divider" }}>
              <CardActionArea onClick={() => openSettings(widget)}>
                <Box sx={{ aspectRatio: "1", bgcolor: "#050607" }}>
                  {previews[id] ? (
                    <img src={previews[id]} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", imageRendering: "pixelated", display: "block" }} />
                  ) : (
                    <Placeholder widget={widget} />
                  )}
                </Box>
                <Box sx={{ p: 1 }}>
                  <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>{widget.manifest.name}</Typography>
                  <Typography variant="caption" color="text.secondary">{widget.manifest.category}</Typography>
                </Box>
              </CardActionArea>
              {widget.active ? <Chip size="small" label="Active" color="primary" sx={{ position: "absolute", top: 6, left: 6, height: 20 }} /> : null}
              <IconButton
                size="small"
                onClick={() => runNow(widget)}
                disabled={applyingId === id}
                sx={{ position: "absolute", top: 4, right: 4, bgcolor: "rgba(0,0,0,0.55)", "&:hover": { bgcolor: "rgba(0,0,0,0.75)" } }}
              >
                <PlayArrowRoundedIcon fontSize="small" sx={{ color: "#fff" }} />
              </IconButton>
            </Card>
          );
        })}

        <Card component="a" href="/studio/" sx={{ textDecoration: "none" }}>
          <Box sx={{ aspectRatio: "1", display: "grid", placeItems: "center", background: "radial-gradient(circle at 50% 35%, #c58cff22, #050607 75%)" }}>
            <Typography sx={{ fontSize: 30, fontWeight: 800, color: "#c58cff" }}>🎨</Typography>
          </Box>
          <Box sx={{ p: 1 }}>
            <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>Meme Studio</Typography>
            <Typography variant="caption" color="text.secondary">create</Typography>
          </Box>
        </Card>
      </Box>

      <WidgetConfigDrawer widget={selected} open={drawerOpen} onClose={() => setDrawerOpen(false)} onApplied={refresh} />
    </Stack>
  );
}
