import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardActions, Typography, Stack, Chip, Button, Box, CircularProgress, Alert } from "@mui/material";
import { StoreWidget, listStoreWidgets, installWidget } from "../api";

export default function Store() {
  const [widgets, setWidgets] = useState<StoreWidget[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const refresh = useCallback(async () => {
    try {
      const r = await listStoreWidgets();
      setWidgets(r.widgets || []);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const install = async (id: string) => {
    setBusy(id);
    try {
      await installWidget(id);
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
      {error ? <Alert severity="error">{error}</Alert> : null}
      {widgets.length === 0 ? (
        <Typography variant="body2" color="text.secondary">No widgets in the configured store index.</Typography>
      ) : null}
      {widgets.map((widget) => (
        <Card key={widget.id}>
          <CardContent sx={{ pb: 1 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{widget.name}</Typography>
              <Chip label={widget.category} size="small" variant="outlined" />
              <Chip label={`v${widget.version}`} size="small" variant="outlined" />
            </Stack>
            <Typography variant="body2" color="text.secondary">{widget.summary}</Typography>
          </CardContent>
          <CardActions sx={{ px: 2, pb: 2 }}>
            <Button variant="contained" size="small" disabled={busy === widget.id} onClick={() => install(widget.id)}>
              {busy === widget.id ? "Installing…" : "Install"}
            </Button>
          </CardActions>
        </Card>
      ))}
    </Stack>
  );
}
