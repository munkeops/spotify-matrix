import { useEffect, useRef } from "react";
import { Box, Chip, Stack, Typography } from "@mui/material";

/**
 * The matrix as these settings would leave it.
 *
 * Rotation and brightness are applied here rather than saved and looked at,
 * because both are hard to picture from a number and one of them restarts
 * the runtime to take effect. It draws a test pattern rather than mirroring
 * the panel: there is no endpoint for the live frame outside a game, and a
 * pattern with a marked corner reads rotation more clearly anyway.
 */

const PANEL = 64;

/** Colour bars, a border, a centre cross and one white corner.
 *
 * The corner is the important part: it is the only thing that tells 90 from
 * 270 at a glance.
 */
function paint(context: CanvasRenderingContext2D): void {
  const bars = ["#e05a5a", "#e0b45a", "#5ae06a", "#5ab4e0", "#8e5ae0", "#e0e0e0"];
  for (let y = 0; y < PANEL; y += 1) {
    for (let x = 0; x < PANEL; x += 1) {
      const edge = x === 0 || y === 0 || x === PANEL - 1 || y === PANEL - 1;
      const cross = x === PANEL / 2 || y === PANEL / 2;
      const corner = x < 6 && y < 6;
      context.fillStyle = corner
        ? "#ffffff"
        : edge
          ? "#3a4358"
          : cross
            ? "#26303f"
            : bars[Math.floor((y / PANEL) * bars.length)];
      context.fillRect(x, y, 1, 1);
    }
  }
}

export default function DisplayPreview({
  rotation,
  brightness,
  rows,
  cols,
}: {
  rotation: number;
  brightness: number;
  rows: number;
  cols: number;
}) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const size = 208;

  useEffect(() => {
    const context = ref.current?.getContext("2d");
    if (context) paint(context);
  }, []);

  return (
    <Stack spacing={1.25} alignItems="center">
      <Box
        sx={{
          width: size,
          height: size,
          p: 1,
          borderRadius: 3,
          bgcolor: "#05070b",
          border: "1px solid",
          borderColor: "divider",
          display: "grid",
          placeItems: "center",
          overflow: "hidden",
        }}
      >
        <Box
          component="canvas"
          ref={ref}
          width={PANEL}
          height={PANEL}
          sx={{
            width: size - 16,
            height: size - 16,
            // One canvas rather than four thousand elements, and pixelated so
            // it looks like a matrix instead of a photograph of one.
            imageRendering: "pixelated",
            transition: "transform 220ms ease, filter 220ms ease",
            transform: `rotate(${rotation}deg)`,
            // Below about a fifth the real panel is barely visible, and the
            // preview should be just as unreadable.
            filter: `brightness(${Math.max(0.05, brightness / 100)})`,
          }}
        />
      </Box>

      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" justifyContent="center" useFlexGap>
        <Chip size="small" variant="outlined" label={`${cols}x${rows}`} />
        <Chip size="small" variant="outlined" label={`${rotation}°`} />
        <Chip size="small" variant="outlined" label={`${brightness}%`} />
      </Stack>

      <Typography variant="caption" color="text.secondary" textAlign="center">
        Brightness applies as soon as you save. Rotation and the driver settings restart the
        matrix, so it will blank for a moment.
      </Typography>
    </Stack>
  );
}
