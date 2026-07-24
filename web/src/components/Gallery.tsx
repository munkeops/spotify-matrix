import { useEffect, useState, useCallback, useRef } from "react";
import { Box, Button, Typography, Stack } from "@mui/material";
import { Asset, listAssets, uploadAsset, deleteAsset } from "../api";

function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error("Could not read file"));
    reader.readAsDataURL(file);
  });
}

// selected: for single-pick pass the current name; for multi pass the ordered list.
export default function Gallery({
  mode, selected, onPick,
}: {
  mode: "single" | "multi";
  selected: string | string[];
  onPick: (name: string) => void;
}) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setAssets((await listAssets()).assets || []);
    } catch {
      setAssets([]);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const onUpload = async (file?: File) => {
    if (!file) return;
    try {
      const data = await readFile(file);
      await uploadAsset(file.name, data);
      await refresh();
    } catch {
      /* ignored */
    }
  };

  const order = (name: string) => (Array.isArray(selected) ? selected.indexOf(name) : -1);
  const isSelected = (name: string) => (Array.isArray(selected) ? selected.includes(name) : selected === name);

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
        <Typography variant="caption" color="text.secondary">
          {mode === "multi" ? "Tap to include" : "Tap to use"}
        </Typography>
        <Button size="small" onClick={() => fileRef.current?.click()}>Upload</Button>
        <input ref={fileRef} type="file" accept="image/*" hidden onChange={(e) => onUpload(e.target.files?.[0])} />
      </Stack>
      <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(64px, 1fr))", gap: 1, maxHeight: 240, overflowY: "auto" }}>
        {assets.length === 0 ? <Typography variant="body2" color="text.secondary">No images yet.</Typography> : null}
        {assets.map((asset) => (
          <Box
            key={asset.name}
            onClick={() => onPick(asset.name)}
            sx={{
              position: "relative", aspectRatio: "1", borderRadius: 1.5, overflow: "hidden", cursor: "pointer",
              border: "2px solid", borderColor: isSelected(asset.name) ? "primary.main" : "transparent",
            }}
          >
            <img src={asset.url} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", imageRendering: "pixelated", display: "block" }} />
            {mode === "multi" && order(asset.name) >= 0 ? (
              <Box sx={{ position: "absolute", top: 2, left: 2, bgcolor: "primary.main", color: "primary.contrastText", borderRadius: 1, px: 0.5, fontSize: 11, fontWeight: 700 }}>
                {order(asset.name) + 1}
              </Box>
            ) : null}
            {asset.animated ? (
              <Box sx={{ position: "absolute", bottom: 2, left: 2, bgcolor: "rgba(0,0,0,0.65)", color: "#ffd166", borderRadius: 0.5, px: 0.5, fontSize: 10, fontWeight: 700 }}>GIF</Box>
            ) : null}
            <Box
              onClick={(e) => { e.stopPropagation(); deleteAsset(asset.name).then(refresh).catch(() => undefined); }}
              sx={{ position: "absolute", top: 2, right: 2, width: 18, height: 18, display: "grid", placeItems: "center", borderRadius: "50%", bgcolor: "rgba(0,0,0,0.6)", color: "#fff", fontSize: 14, lineHeight: 1 }}
            >×</Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
}
