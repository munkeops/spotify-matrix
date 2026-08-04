import { useEffect, useState, useCallback } from "react";
import { Card, CardActionArea, Typography, Stack, Chip, Button, Box, CircularProgress, Alert } from "@mui/material";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import { StoreWidget, listStoreWidgets, installWidget, previewWidget, PREVIEWABLE } from "../api";

const CATEGORY_COLOR: Record<string, string> = {
  media: "#4be0c0", time: "#8ea2ff", assistant: "#ffb86b", information: "#7ee0a0",
  custom: "#c58cff", diagnostics: "#ff8c8c", weather: "#66d0ff", games: "#ff7ab8",
};

export default function Store() {
  const [widgets, setWidgets] = useState<StoreWidget[]>([]);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const loadPreviews = useCallback(async (list: StoreWidget[]) => {
    await Promise.all(list.map(async (w) => {
      if (PREVIEWABLE.has(w.id) || w.runtime === "builtin") {
        try {
          const p = await previewWidget(w.id, {});
          setPreviews((prev) => ({ ...prev, [w.id]: p.dataUrl }));
        } catch { /* not renderable here */ }
      } else if (w.matrixPreviewUrl) {
        setPreviews((prev) => ({ ...prev, [w.id]: w.matrixPreviewUrl }));
      }
    }));
  }, []);

  const refresh = useCallback(async () => {
    try {
      const r = await listStoreWidgets();
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

  const install = async (id: string) => {
    setBusy(id);
    try {
      await installWidget(id);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };

  if (loading) {
    return <Box sx={{ display: "grid", placeItems: "center", py: 8 }}><CircularProgress /></Box>;
  }

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="h6">Plugin Store</Typography>
        <Typography variant="body2" color="text.secondary">Install plugins onto your matrix. Built-ins and community plugins live here.</Typography>
      </Box>
      {error ? <Alert severity="error">{error}</Alert> : null}
      {widgets.length === 0 ? (
        <Alert severity="info">No plugins in the store index. Check the store URL in Settings.</Alert>
      ) : null}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 2 }}>
        {widgets.map((w) => {
          const color = CATEGORY_COLOR[w.category] || "#4be0c0";
          return (
            <Card key={w.id} sx={{ display: "flex", flexDirection: "column", overflow: "hidden", transition: "transform .15s ease, box-shadow .15s ease", "&:hover": { transform: "translateY(-2px)", boxShadow: 6 } }}>
              <Box sx={{ aspectRatio: "16 / 9", display: "grid", placeItems: "center", background: `radial-gradient(circle at 50% 30%, ${color}22, #050607 78%)` }}>
                {previews[w.id] ? (
                  <img src={previews[w.id]} alt="" style={{ height: "78%", aspectRatio: "1", objectFit: "cover", imageRendering: "pixelated", borderRadius: 8 }} />
                ) : (
                  <Typography sx={{ fontSize: 40, fontWeight: 800, color }}>{w.name.charAt(0)}</Typography>
                )}
              </Box>
              <Box sx={{ p: 1.5, flex: 1, display: "flex", flexDirection: "column", gap: 0.5 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, flex: 1 }} noWrap>{w.name}</Typography>
                  <Chip size="small" label={w.category} sx={{ bgcolor: `${color}22`, color, fontWeight: 600 }} />
                </Stack>
                <Typography variant="body2" color="text.secondary" sx={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", minHeight: 40 }}>
                  {w.summary}
                </Typography>
                <Typography variant="caption" color="text.secondary">{w.author} · v{w.version}</Typography>
                <Box sx={{ mt: 1 }}>
                  {w.installed ? (
                    <Button fullWidth variant="outlined" color="success" startIcon={<CheckCircleRoundedIcon />} disabled>Installed</Button>
                  ) : (
                    <Button fullWidth variant="contained" startIcon={<DownloadRoundedIcon />} disabled={busy === w.id} onClick={() => install(w.id)}>
                      {busy === w.id ? "Installing…" : "Install"}
                    </Button>
                  )}
                </Box>
              </Box>
            </Card>
          );
        })}
      </Box>
    </Stack>
  );
}
