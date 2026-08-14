import SettingsSection from "./SettingsSection";
import BluetoothDevice from "./BluetoothDevice";
import { RADIUS } from "../theme";
import { useEffect, useState, useCallback } from "react";
import { Alert, Box, Button, Chip, Stack, Switch, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import BluetoothRoundedIcon from "@mui/icons-material/BluetoothRounded";
import { BtDevice, btStatus, btDevices, btScan, btConnect, btPair, btPower, btDisconnect, btRemove } from "../api";

export default function BluetoothPanel() {
  const [available, setAvailable] = useState(true);
  const [adapter, setAdapter] = useState("");
  const [powered, setPowered] = useState(false);
  const [powering, setPowering] = useState(false);
  const [advice, setAdvice] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [devices, setDevices] = useState<BtDevice[]>([]);
  const [scanning, setScanning] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [connectAdvice, setConnectAdvice] = useState("");
  // A scan turns up every nearby radio, so start on what you came for.
  const [filter, setFilter] = useState<"controller" | "audio" | "all">("all");
  const [showUnnamed, setShowUnnamed] = useState(false);

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

  const togglePower = async (on: boolean) => {
    setPowering(true);
    setError("");
    try {
      const status = await btPower(on);
      setPowered(status.powered);
      // Turning it on takes a moment to settle, and the device list is
      // meaningless until it has.
      if (status.powered) await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPowering(false);
    }
  };

  const act = async (fn: () => Promise<any>, mac: string) => {
    setBusy(mac);
    setConnectAdvice("");
    try {
      const result = await fn();
      // A failed connect explains itself rather than just going quiet.
      if (result && typeof result === "object" && "ok" in result && !result.ok) {
        setConnectAdvice(String((result as any).advice || (result as any).message || ""));
      }
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };

  const counts = {
    controller: devices.filter((d) => d.role === "controller").length,
    audio: devices.filter((d) => d.role === "audio").length,
    all: devices.length,
  };
  const sorted = devices
    .filter((d) => filter === "all" || d.role === filter)
    // Anything already set up stays visible whatever the filters say.
    .filter((d) => showUnnamed || d.named || d.paired || d.connected);

  // Paired above, everything else below: a device you have set up is not the
  // same kind of thing as one a scan happened to see.
  const paired = sorted.filter((device) => device.paired);
  const nearby = sorted.filter((device) => !device.paired);

  return (
    <SettingsSection
      title="Bluetooth"
      icon={<BluetoothRoundedIcon fontSize="small" color="primary" />}
      action={
        <Stack direction="row" spacing={1} alignItems="center">
          <Switch
            size="small"
            checked={powered}
            disabled={!available || powering}
            onChange={(e) => togglePower(e.target.checked)}
            inputProps={{ "aria-label": "Bluetooth power" }}
          />
          <Button size="small" variant="outlined" onClick={scan} disabled={!available || !powered || scanning}>
            {scanning ? "Scanning…" : "Scan"}
          </Button>
        </Stack>
      }
    >

        {error ? <Alert severity="error">{error}</Alert> : null}

        {connectAdvice ? (
          <Alert severity="warning" onClose={() => setConnectAdvice("")}>
            {connectAdvice}
          </Alert>
        ) : null}

        {advice ? (
          <Alert severity={!available || blocked ? "warning" : powered ? "info" : "warning"}>
            {advice}
          </Alert>
        ) : null}

        {!available ? null : (
          <>
            <Typography variant="body2" color="text.secondary">
              Adapter {adapter || "ready"} · power {powered ? "on" : "off"}
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1, flexWrap: "wrap" }} useFlexGap>
              <ToggleButtonGroup size="small" exclusive value={filter} onChange={(_, next) => next && setFilter(next)}>
                <ToggleButton value="controller" sx={{ textTransform: "none", py: 0.25 }}>
                  Controllers ({counts.controller})
                </ToggleButton>
                <ToggleButton value="audio" sx={{ textTransform: "none", py: 0.25 }}>
                  Audio ({counts.audio})
                </ToggleButton>
                <ToggleButton value="all" sx={{ textTransform: "none", py: 0.25 }}>
                  All ({counts.all})
                </ToggleButton>
              </ToggleButtonGroup>
              <Chip
                size="small"
                variant={showUnnamed ? "filled" : "outlined"}
                label={showUnnamed ? "Hide unnamed" : "Show unnamed"}
                onClick={() => setShowUnnamed((value) => !value)}
              />
            </Stack>

            {paired.length ? (
              <Stack spacing={1}>
                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
                  MY DEVICES
                </Typography>
                {paired.map((device) => (
                  <BluetoothDevice
                    key={device.mac}
                    device={device}
                    busy={busy === device.mac}
                    onPair={() => act(() => btPair(device.mac), device.mac)}
                    onConnect={() => act(() => btConnect(device.mac), device.mac)}
                    onDisconnect={() => act(() => btDisconnect(device.mac), device.mac)}
                    onForget={() => act(() => btRemove(device.mac), device.mac)}
                  />
                ))}
              </Stack>
            ) : null}

            <Stack spacing={1}>
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
                AVAILABLE
              </Typography>
              {nearby.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  {devices.length === 0
                    ? "Nothing found yet. Hold the device's pairing button until its light flashes quickly, then Scan."
                    : "Nothing new. A device reports its name a moment after it appears, so scan again or show unnamed."}
                </Typography>
              ) : null}
              {nearby.map((device) => (
                <BluetoothDevice
                  key={device.mac}
                  device={device}
                  busy={busy === device.mac}
                  onPair={() => act(() => btPair(device.mac), device.mac)}
                  onConnect={() => act(() => btConnect(device.mac), device.mac)}
                  onDisconnect={() => act(() => btDisconnect(device.mac), device.mac)}
                  onForget={() => act(() => btRemove(device.mac), device.mac)}
                />
              ))}
            </Stack>
          </>
        )}
    </SettingsSection>
  );
}
