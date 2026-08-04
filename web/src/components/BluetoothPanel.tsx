import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, Stack, Typography, Button, Chip, Box, Alert } from "@mui/material";
import BluetoothRoundedIcon from "@mui/icons-material/BluetoothRounded";
import { BtDevice, btStatus, btDevices, btScan, btConnect, btDisconnect, btRemove } from "../api";

export default function BluetoothPanel() {
  const [available, setAvailable] = useState(true);
  const [adapter, setAdapter] = useState("");
  const [powered, setPowered] = useState(false);
  const [advice, setAdvice] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [devices, setDevices] = useState<BtDevice[]>([]);
  const [scanning, setScanning] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [s, d] = await Promise.all([btStatus(), btDevices()]);
      setAvailable(s.available);
      setAdapter(s.adapter);
      setPowered(s.powered);
      setAdvice(s.advice || "");
      setBlocked(Boolean(s.blocked));
      setDevices(d.devices || []);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const scan = async () => {
    setScanning(true);
    try {
      const r = await btScan(8);
      setDevices(r.devices || []);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setScanning(false);
    }
  };

  const act = async (fn: () => Promise<unknown>, mac: string) => {
    setBusy(mac);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };

  const sorted = [...devices].sort((a, b) => Number(b.connected) - Number(a.connected) || Number(b.paired) - Number(a.paired));

  return (
    <Card>
      <CardContent>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <BluetoothRoundedIcon color="primary" />
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>Bluetooth</Typography>
          </Stack>
          <Button size="small" variant="outlined" onClick={scan} disabled={!available || scanning}>
            {scanning ? "Scanning…" : "Scan"}
          </Button>
        </Stack>

        {error ? <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert> : null}

        {advice ? (
          <Alert severity={!available || blocked ? "warning" : powered ? "info" : "warning"} sx={{ mb: 1 }}>
            {advice}
          </Alert>
        ) : null}

        {!available ? null : (
          <>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Adapter {adapter || "ready"} · power {powered ? "on" : "off"}
            </Typography>
            <Stack spacing={1}>
              {sorted.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No devices yet. Put the device in pairing mode first, then tap Scan.
                </Typography>
              ) : null}
              {sorted.map((device) => (
                <Box key={device.mac} sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1, p: 1, border: "1px solid", borderColor: device.connected ? "primary.main" : "divider", borderRadius: 2 }}>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>{device.name || device.mac}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {device.mac}{device.connected ? " · Connected" : device.paired ? " · Paired" : ""}
                    </Typography>
                  </Box>
                  <Stack direction="row" spacing={0.5}>
                    {device.connected ? (
                      <Button size="small" variant="outlined" disabled={busy === device.mac} onClick={() => act(() => btDisconnect(device.mac), device.mac)}>Disconnect</Button>
                    ) : (
                      <Button size="small" variant="contained" disabled={busy === device.mac} onClick={() => act(() => btConnect(device.mac), device.mac)}>Connect</Button>
                    )}
                    {device.paired ? (
                      <Button size="small" color="error" disabled={busy === device.mac} onClick={() => act(() => btRemove(device.mac), device.mac)}>Forget</Button>
                    ) : null}
                  </Stack>
                </Box>
              ))}
            </Stack>
          </>
        )}
      </CardContent>
    </Card>
  );
}
