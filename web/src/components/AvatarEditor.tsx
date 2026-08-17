import { useState } from "react";
import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from "@mui/material";
import { UserProfile } from "../api";
import { RADIUS } from "../theme";

/**
 * Draw a face, sixteen pixels across.
 *
 * A fixed palette rather than a colour picker: sixteen swatches you can
 * hit with a thumb beat a gradient nobody can aim at, and the result has
 * to survive being shown on LEDs, where subtle shades are not subtle so
 * much as invisible.
 *
 * Drag to draw. The right mouse button and the eraser both clear back to
 * transparent, which the panel shows as black.
 */

const SIZE = 16;

//: Chosen to stay distinct on a panel: strong hues, no near-blacks that
//: would disappear into the background, no pastels that wash out.
const PALETTE = [
  "#ffffff", "#c9d2e0", "#7f8ca3", "#3c4658",
  "#ff4d4d", "#ff8a3d", "#ffd23d", "#9ee34f",
  "#3ddc84", "#3ddbd0", "#43b2ff", "#3d6bff",
  "#9b5cff", "#e75cff", "#ff5ca8", "#8b5a2b",
];

const BLANK = Array.from({ length: SIZE }, () => ".".repeat(SIZE));

/** Palette index to base62 digit, matching the frame encoding. */
function digit(value: number): string {
  if (value < 10) return String(value);
  if (value < 36) return String.fromCharCode(87 + value);
  return String.fromCharCode(29 + value);
}

export default function AvatarEditor({
  profile,
  open,
  onClose,
  onSave,
}: {
  profile: UserProfile;
  open: boolean;
  onClose: () => void;
  onSave: (avatar: string[], palette: string[]) => void;
}) {
  const [rows, setRows] = useState<string[]>(
    profile.avatar.length === SIZE ? profile.avatar : BLANK,
  );
  const [colour, setColour] = useState(4);
  const [painting, setPainting] = useState(false);

  const paint = (x: number, y: number, erase: boolean) => {
    setRows((previous) =>
      previous.map((row, index) =>
        index !== y ? row : row.slice(0, x) + (erase ? "." : digit(colour)) + row.slice(x + 1),
      ),
    );
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{profile.name}'s face</DialogTitle>
      <DialogContent>
        <Stack spacing={2} alignItems="center">
          <Box
            onMouseLeave={() => setPainting(false)}
            onContextMenu={(event) => event.preventDefault()}
            sx={{
              display: "grid",
              gridTemplateColumns: `repeat(${SIZE}, 1fr)`,
              width: "100%",
              maxWidth: 288,
              aspectRatio: "1",
              bgcolor: "#05070b",
              borderRadius: `${RADIUS}px`,
              overflow: "hidden",
              border: "1px solid",
              borderColor: "divider",
              cursor: "crosshair",
              touchAction: "none",
            }}
          >
            {rows.flatMap((row, y) =>
              Array.from(row).map((character, x) => {
                const value = character === "." ? "" : PALETTE[parseInt(character, 36)] ?? "";
                return (
                  <Box
                    key={`${x}-${y}`}
                    onPointerDown={(event) => {
                      setPainting(true);
                      paint(x, y, event.button === 2);
                    }}
                    onPointerEnter={(event) => {
                      if (painting) paint(x, y, event.buttons === 2);
                    }}
                    onPointerUp={() => setPainting(false)}
                    sx={{
                      background: value || "transparent",
                      aspectRatio: "1",
                      boxShadow: "inset 0 0 0 0.5px rgba(255,255,255,0.06)",
                    }}
                  />
                );
              }),
            )}
          </Box>

          <Box sx={{ display: "grid", gridTemplateColumns: "repeat(8, 1fr)", gap: 0.75, width: "100%", maxWidth: 288 }}>
            {PALETTE.map((swatch, value) => (
              <Box
                key={swatch}
                onClick={() => setColour(value)}
                sx={{
                  background: swatch,
                  aspectRatio: "1",
                  borderRadius: 1,
                  cursor: "pointer",
                  outline: value === colour ? "2px solid" : "none",
                  outlineColor: "primary.main",
                  outlineOffset: 2,
                }}
              />
            ))}
          </Box>

          <Typography variant="caption" color="text.secondary" textAlign="center">
            Drag to draw. Right-click erases. Sixteen pixels across is what reads on the
            panel from across a room.
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setRows(BLANK)}>Clear</Button>
        <Box sx={{ flex: 1 }} />
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={() => onSave(rows, PALETTE)}>
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}
