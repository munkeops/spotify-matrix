import { useEffect, useRef } from "react";
import { Box } from "@mui/material";
import { GameFrame } from "../api";

// Games publish a palette plus one index character per pixel, so one canvas
// mirrors any game exactly as it appears on the panel.
const ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";

function rgb(value: string): [number, number, number] {
  const text = value.replace("#", "");
  if (text.length !== 6) return [0, 0, 0];
  return [parseInt(text.slice(0, 2), 16), parseInt(text.slice(2, 4), 16), parseInt(text.slice(4, 6), 16)];
}

export default function PanelMirror({ frame, dim, size = 64 }: { frame: GameFrame | null; dim?: boolean; size?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;

    const rows = frame?.pixels ?? [];
    const height = rows.length || size;
    const width = rows[0]?.length || size;
    canvas.width = width;
    canvas.height = height;

    const image = context.createImageData(width, height);
    const palette = (frame?.palette ?? []).map(rgb);
    for (let y = 0; y < height; y += 1) {
      const row = rows[y] ?? "";
      for (let x = 0; x < width; x += 1) {
        const index = ALPHABET.indexOf(row[x] ?? "0");
        const [r, g, b] = palette[index >= 0 ? index : 0] ?? [0, 0, 0];
        const offset = (y * width + x) * 4;
        image.data[offset] = r;
        image.data[offset + 1] = g;
        image.data[offset + 2] = b;
        image.data[offset + 3] = 255;
      }
    }
    context.putImageData(image, 0, 0);
  }, [frame, size]);

  return (
    <Box
      sx={{
        p: 1,
        borderRadius: 2,
        bgcolor: "#04060a",
        border: "1px solid",
        borderColor: "divider",
        lineHeight: 0,
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          width: "100%",
          height: "auto",
          aspectRatio: "1 / 1",
          imageRendering: "pixelated",
          borderRadius: 4,
          opacity: dim ? 0.4 : 1,
          transition: "opacity .3s ease",
          display: "block",
        }}
      />
    </Box>
  );
}
