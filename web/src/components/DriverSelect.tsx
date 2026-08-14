import { useEffect, useState } from "react";
import { Alert, Box, Chip, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { MatrixDriver, MatrixDriversResponse, getMatrixDrivers } from "../api";
import Field from "./Field";
import { RADIUS } from "../theme";

/**
 * Which wiring this matrix uses.
 *
 * Picking one fills in the mapping, the slowdown and the pulse setting,
 * because those three are not independent choices - they follow from where
 * the panel's OE line lands. They stay editable underneath: a driver is a
 * starting point for a known board, not a lock.
 *
 * The definitions come from the server so this page and the runtime cannot
 * disagree about what "direct wiring" means, and the pin table is the one
 * from the library's own source.
 */
export default function DriverSelect({
  hardwareMapping,
  onApply,
}: {
  hardwareMapping: string;
  /** Called with the settings the chosen driver implies. */
  onApply: (settings: { hardwareMapping: string; gpioSlowdown: number; noHardwarePulse: boolean }) => void;
}) {
  const [data, setData] = useState<MatrixDriversResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getMatrixDrivers()
      .then(setData)
      .catch((e) => setError((e as Error).message));
  }, []);

  if (error) return <Alert severity="warning">{error}</Alert>;
  if (!data) return null;

  // Read from the settings rather than from what was last picked, so this
  // still tells the truth after someone edits the mapping by hand.
  const active =
    data.drivers.find((driver) => driver.hardwareMapping === hardwareMapping)?.id ?? "custom";
  const selected: MatrixDriver | undefined = data.drivers.find((driver) => driver.id === active);

  const apply = (id: string) => {
    const driver = data.drivers.find((d) => d.id === id);
    if (!driver) return;
    onApply({
      hardwareMapping: driver.hardwareMapping,
      gpioSlowdown: driver.gpioSlowdown,
      noHardwarePulse: driver.noHardwarePulse,
    });
  };

  return (
    <Stack spacing={1.5}>
      <Field
        label="Wiring"
        help="Sets the mapping, slowdown and pulsing below. Save to apply - the matrix restarts."
      >
        <TextField select value={active} onChange={(event) => apply(event.target.value)}>
          {data.drivers.map((driver) => (
            <MenuItem key={driver.id} value={driver.id}>
              {driver.name}
            </MenuItem>
          ))}
          {/* Only reachable by hand-editing the mapping, and not worth
              hiding: it is how you find out you are on something unusual. */}
          {active === "custom" ? <MenuItem value="custom">Custom ({hardwareMapping || "unset"})</MenuItem> : null}
        </TextField>
      </Field>

      {selected ? (
        <>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Typography variant="body2" color="text.secondary">
              {selected.summary}
            </Typography>
            <Chip
              size="small"
              variant="outlined"
              color={selected.noHardwarePulse ? "warning" : "success"}
              label={selected.noHardwarePulse ? "Software pulsing" : "Hardware pulsing"}
            />
          </Stack>

          <Box
            sx={{
              border: "1px solid",
              borderColor: "divider",
              borderRadius: `${RADIUS}px`,
              p: 1.25,
              overflowX: "auto",
            }}
          >
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
              BCM PINS
            </Typography>
            <Box
              sx={{
                mt: 0.75,
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(58px, 1fr))",
                gap: 0.75,
              }}
            >
              {data.pinOrder.map((signal) => (
                <Box key={signal} sx={{ textAlign: "center" }}>
                  <Typography variant="caption" color="text.secondary" component="div">
                    {signal}
                  </Typography>
                  <Typography variant="body2" component="div" sx={{ fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
                    {selected.pins[signal] ?? "-"}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Box>

          {selected.notes ? (
            <Typography variant="caption" color="text.secondary">
              {selected.notes}
            </Typography>
          ) : null}
        </>
      ) : (
        <Typography variant="caption" color="text.secondary">
          These settings do not match a known wiring, so nothing here will change them.
        </Typography>
      )}
    </Stack>
  );
}
