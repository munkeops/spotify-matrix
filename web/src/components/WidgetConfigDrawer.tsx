import { useEffect, useRef, useState } from "react";
import {
  Drawer, Box, Stack, Typography, TextField, MenuItem, Switch, FormControlLabel,
  Button, IconButton, Divider, Alert,
} from "@mui/material";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import {
  LocalWidget, getWidgetConfig, saveWidgetConfig, applyWidget, previewWidget, PREVIEWABLE,
} from "../api";

export default function WidgetConfigDrawer({
  widget, open, onClose, onApplied,
}: {
  widget: LocalWidget | null;
  open: boolean;
  onClose: () => void;
  onApplied: () => void;
}) {
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [preview, setPreview] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  const id = widget?.manifest.id ?? "";
  const fields = widget?.manifest.config ?? [];
  const previewable = PREVIEWABLE.has(id);

  useEffect(() => {
    if (!widget || !open) return;
    setError("");
    setPreview("");
    getWidgetConfig(id)
      .then((r) => setValues(r.config || {}))
      .catch((e) => setError((e as Error).message));
  }, [id, open, widget]);

  useEffect(() => {
    if (!open || !previewable) return;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      previewWidget(id, values).then((r) => setPreview(r.dataUrl)).catch(() => undefined);
    }, 250);
    return () => window.clearTimeout(timer.current);
  }, [values, open, previewable, id]);

  const set = (key: string, value: unknown) => setValues((prev) => ({ ...prev, [key]: value }));

  const doSave = async () => {
    setBusy(true);
    try {
      await saveWidgetConfig(id, values);
      onApplied();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const doApply = async () => {
    setBusy(true);
    try {
      await applyWidget(id, values);
      onApplied();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{ sx: { width: { xs: "100%", sm: 420 }, p: 2, bgcolor: "background.default" } }}
    >
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
        <Typography variant="h6">{widget?.manifest.name ?? "Widget"}</Typography>
        <IconButton onClick={onClose}><CloseRoundedIcon /></IconButton>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{widget?.manifest.summary}</Typography>

      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}

      {previewable ? (
        <Box sx={{ display: "grid", placeItems: "center", mb: 2 }}>
          {preview ? (
            <img src={preview} width={128} height={128} style={{ imageRendering: "pixelated", borderRadius: 8, background: "#000" }} alt="preview" />
          ) : (
            <Box sx={{ width: 128, height: 128, borderRadius: 2, bgcolor: "background.paper" }} />
          )}
        </Box>
      ) : null}

      <Stack spacing={2} sx={{ flex: 1, overflowY: "auto" }}>
        {fields.length === 0 ? (
          <Typography variant="body2" color="text.secondary">This widget has no options.</Typography>
        ) : null}
        {fields.map((field) => {
          const value = values[field.key] ?? field.default ?? "";
          if (field.type === "boolean") {
            return (
              <FormControlLabel
                key={field.key}
                control={<Switch checked={Boolean(values[field.key] ?? field.default)} onChange={(e) => set(field.key, e.target.checked)} />}
                label={field.label}
              />
            );
          }
          if (field.type === "select") {
            return (
              <TextField key={field.key} select label={field.label} value={String(value)} onChange={(e) => set(field.key, e.target.value)} fullWidth size="small">
                {(field.options ?? []).map((opt) => (
                  <MenuItem key={String(opt.value)} value={String(opt.value)}>{opt.label}</MenuItem>
                ))}
              </TextField>
            );
          }
          return (
            <TextField
              key={field.key}
              label={field.label}
              type={field.type === "number" ? "number" : field.type === "secret" ? "password" : "text"}
              value={value as string | number}
              placeholder={field.placeholder}
              helperText={field.helpText}
              onChange={(e) => set(field.key, field.type === "number" ? Number(e.target.value) : e.target.value)}
              fullWidth
              size="small"
            />
          );
        })}
      </Stack>

      <Divider sx={{ my: 2 }} />
      <Stack direction="row" spacing={1}>
        <Button variant="outlined" onClick={doSave} disabled={busy} fullWidth>Save</Button>
        <Button variant="contained" onClick={doApply} disabled={busy} fullWidth>Apply</Button>
      </Stack>
    </Drawer>
  );
}
