import { Box, Button, Chip, Stack, Typography } from "@mui/material";
import BluetoothRoundedIcon from "@mui/icons-material/BluetoothRounded";
import ComputerRoundedIcon from "@mui/icons-material/ComputerRounded";
import DevicesOtherRoundedIcon from "@mui/icons-material/DevicesOtherRounded";
import HeadphonesRoundedIcon from "@mui/icons-material/HeadphonesRounded";
import KeyboardRoundedIcon from "@mui/icons-material/KeyboardRounded";
import PhoneAndroidRoundedIcon from "@mui/icons-material/PhoneAndroidRounded";
import SpeakerRoundedIcon from "@mui/icons-material/SpeakerRounded";
import SportsEsportsRoundedIcon from "@mui/icons-material/SportsEsportsRounded";
import TvRoundedIcon from "@mui/icons-material/TvRounded";
import { BtDevice } from "../api";
import { RADIUS } from "../theme";

/**
 * One device, as a desktop would show it.
 *
 * Pairing and connecting are separate things and the buttons say so: an
 * unpaired device can only be paired, and a paired one can be connected,
 * disconnected or forgotten. A single Connect that quietly paired first
 * could not tell you which half had failed.
 */

const ICONS: Record<string, typeof BluetoothRoundedIcon> = {
  audio: SpeakerRoundedIcon,
  headphones: HeadphonesRoundedIcon,
  controller: SportsEsportsRoundedIcon,
  input: KeyboardRoundedIcon,
  phone: PhoneAndroidRoundedIcon,
  computer: ComputerRoundedIcon,
  display: TvRoundedIcon,
  other: DevicesOtherRoundedIcon,
};

export default function BluetoothDevice({
  device,
  busy,
  onPair,
  onConnect,
  onDisconnect,
  onForget,
}: {
  device: BtDevice;
  busy: boolean;
  onPair: () => void;
  onConnect: () => void;
  onDisconnect: () => void;
  onForget: () => void;
}) {
  const Icon = ICONS[device.role] ?? ICONS.other;
  const state = device.connected ? "Connected" : device.paired ? "Paired" : "";

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        p: 1.25,
        border: "1px solid",
        borderColor: device.connected ? "primary.main" : "divider",
        borderRadius: `${RADIUS}px`,
        bgcolor: device.connected ? "action.selected" : "transparent",
      }}
    >
      <Icon fontSize="small" color={device.connected ? "primary" : "disabled"} />

      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Stack direction="row" spacing={0.75} alignItems="center">
          <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>
            {device.name || device.mac}
          </Typography>
          {state ? (
            <Chip
              size="small"
              color={device.connected ? "success" : "default"}
              variant={device.connected ? "filled" : "outlined"}
              label={state}
              sx={{ height: 18 }}
            />
          ) : null}
        </Stack>
        <Typography variant="caption" color="text.secondary" noWrap component="div">
          {device.mac}
        </Typography>
      </Box>

      <Stack direction="row" spacing={0.5}>
        {!device.paired ? (
          <Button size="small" variant="contained" disabled={busy} onClick={onPair}>
            {busy ? "Pairing…" : "Pair"}
          </Button>
        ) : device.connected ? (
          <Button size="small" variant="outlined" disabled={busy} onClick={onDisconnect}>
            Disconnect
          </Button>
        ) : (
          <Button size="small" variant="contained" disabled={busy} onClick={onConnect}>
            {busy ? "Connecting…" : "Connect"}
          </Button>
        )}
        {device.paired ? (
          <Button size="small" color="error" disabled={busy} onClick={onForget}>
            Forget
          </Button>
        ) : null}
      </Stack>
    </Box>
  );
}
