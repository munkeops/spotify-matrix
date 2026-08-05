import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Alert, Box, Button, Card, Chip, CircularProgress, Stack, Typography } from "@mui/material";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import SportsEsportsRoundedIcon from "@mui/icons-material/SportsEsportsRounded";
import {
  LocalApp,
  StoreApp,
  applyApp,
  gameIdFromAppId,
  installApp,
  isGame,
  listLocalApps,
  listStoreApps,
  previewApp,
} from "../api";
import { SHELVES, ShelfKey, ShelfTabs, colorFor, groupByShelf } from "../shelves";

interface StoreItem {
  id: string;
  name: string;
  summary: string;
  category: string;
  author: string;
  version: string;
  installed: boolean;
  active: boolean;
  isGame: boolean;
  configurable: boolean;
  artwork: string;
}

// Local apps know what is installed and running; the catalogue knows what
// else is out there. Merge so one card can show both.
function mergeCatalogue(local: LocalApp[], store: StoreApp[]): StoreItem[] {
  const items = new Map<string, StoreItem>();
  for (const app of local) {
    items.set(app.manifest.id, {
      id: app.manifest.id,
      name: app.manifest.name,
      summary: app.manifest.summary,
      category: app.manifest.category,
      author: app.manifest.author,
      version: app.manifest.version,
      installed: true,
      active: app.active,
      isGame: isGame(app),
      configurable: app.configurable,
      artwork: "",
    });
  }
  for (const app of store) {
    const existing = items.get(app.id);
    if (existing) {
      existing.summary = existing.summary || app.summary;
      existing.artwork = existing.artwork || app.matrixPreviewUrl;
      continue;
    }
    items.set(app.id, {
      id: app.id,
      name: app.name,
      summary: app.summary,
      category: app.category,
      author: app.author,
      version: app.version,
      installed: app.installed,
      active: false,
      isGame: app.category === "games",
      configurable: false,
      artwork: app.matrixPreviewUrl,
    });
  }
  return [...items.values()].sort((a, b) => a.name.localeCompare(b.name));
}

export default function Store() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [items, setItems] = useState<StoreItem[]>([]);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const requested = params.get("tab") as ShelfKey | null;
  const tab: ShelfKey = SHELVES.some((shelf) => shelf.key === requested) ? (requested as ShelfKey) : "apps";
  const setTab = (next: ShelfKey) => setParams(next === "apps" ? {} : { tab: next }, { replace: true });

  const loadPreviews = useCallback(async (list: StoreItem[]) => {
    await Promise.all(list.map(async (item) => {
      if (!item.installed) {
        if (item.artwork) setPreviews((prev) => ({ ...prev, [item.id]: item.artwork }));
        return;
      }
      try {
        const preview = await previewApp(item.id, {});
        setPreviews((prev) => ({ ...prev, [item.id]: preview.dataUrl }));
      } catch {
        if (item.artwork) setPreviews((prev) => ({ ...prev, [item.id]: item.artwork }));
      }
    }));
  }, []);

  const refresh = useCallback(async () => {
    try {
      // The catalogue is optional: a missing store index must not hide what is
      // already installed.
      const [local, store] = await Promise.all([
        listLocalApps(),
        listStoreApps().catch(() => ({ apps: [] as StoreApp[] })),
      ]);
      const merged = mergeCatalogue(local.apps || [], store.apps || []);
      setItems(merged);
      setError("");
      loadPreviews(merged);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [loadPreviews]);

  useEffect(() => { refresh(); }, [refresh]);

  const install = async (id: string) => {
    setBusy(id);
    try {
      await installApp(id);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };

  const run = async (item: StoreItem) => {
    setBusy(item.id);
    try {
      await applyApp(item.id, null);
      if (item.isGame) {
        navigate(`/play/${gameIdFromAppId(item.id)}`);
        return;
      }
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };

  const shelves = useMemo(() => groupByShelf(items), [items]);

  if (loading) {
    return <Box sx={{ display: "grid", placeItems: "center", py: 8 }}><CircularProgress /></Box>;
  }

  const current = SHELVES.find((shelf) => shelf.key === tab)!;
  const shelf = shelves[tab];

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="h6">App Store</Typography>
        <Typography variant="body2" color="text.secondary">{current.blurb}</Typography>
      </Box>

      <ShelfTabs
        value={tab}
        onChange={setTab}
        counts={{ apps: shelves.apps.length, play: shelves.play.length, creative: shelves.creative.length }}
      />

      {error ? <Alert severity="error">{error}</Alert> : null}
      {shelf.length === 0 ? (
        <Alert severity="info">
          Nothing here yet. {tab === "play" ? "Game apps appear once installed." : "Check the store URL in Settings."}
        </Alert>
      ) : null}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 2 }}>
        {shelf.map((item) => {
          const color = colorFor(item.category);
          return (
            <Card
              key={item.id}
              sx={{
                display: "flex", flexDirection: "column", overflow: "hidden",
                borderColor: item.active ? "primary.main" : "divider",
                transition: "transform .15s ease, box-shadow .15s ease",
                "&:hover": { transform: "translateY(-2px)", boxShadow: 6 },
              }}
            >
              <Box sx={{ position: "relative", aspectRatio: "16 / 9", display: "grid", placeItems: "center", background: `radial-gradient(circle at 50% 30%, ${color}22, #050607 78%)` }}>
                {previews[item.id] ? (
                  <img src={previews[item.id]} alt="" style={{ height: "78%", aspectRatio: "1", objectFit: "cover", imageRendering: "pixelated", borderRadius: 8 }} />
                ) : (
                  <Typography sx={{ fontSize: 40, fontWeight: 800, color }}>{item.name.charAt(0)}</Typography>
                )}
                {item.active ? (
                  <Chip size="small" label="On screen" color="primary" sx={{ position: "absolute", top: 8, left: 8, height: 20 }} />
                ) : null}
              </Box>
              <Box sx={{ p: 1.5, flex: 1, display: "flex", flexDirection: "column", gap: 0.5 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, flex: 1 }} noWrap>{item.name}</Typography>
                  <Chip size="small" label={item.category} sx={{ bgcolor: `${color}22`, color, fontWeight: 600 }} />
                </Stack>
                <Typography variant="body2" color="text.secondary" sx={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", minHeight: 40 }}>
                  {item.summary}
                </Typography>
                <Typography variant="caption" color="text.secondary">{item.author} · v{item.version}</Typography>
                <Box sx={{ mt: 1 }}>
                  {!item.installed ? (
                    <Button fullWidth variant="contained" startIcon={<DownloadRoundedIcon />} disabled={busy === item.id} onClick={() => install(item.id)}>
                      {busy === item.id ? "Installing…" : "Install"}
                    </Button>
                  ) : item.isGame ? (
                    <Button fullWidth variant="contained" startIcon={<SportsEsportsRoundedIcon />} disabled={busy === item.id} onClick={() => run(item)}>
                      {busy === item.id ? "Starting…" : "Play"}
                    </Button>
                  ) : (
                    <Button
                      fullWidth
                      variant={item.active ? "outlined" : "contained"}
                      color={item.active ? "success" : "primary"}
                      startIcon={item.active ? <CheckCircleRoundedIcon /> : <PlayArrowRoundedIcon />}
                      disabled={busy === item.id}
                      onClick={() => run(item)}
                    >
                      {item.active ? "On screen" : busy === item.id ? "Starting…" : "Put on matrix"}
                    </Button>
                  )}
                </Box>
              </Box>
            </Card>
          );
        })}

        {tab === "creative" ? (
          <Card component="a" href="/studio/" sx={{ textDecoration: "none", display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <Box sx={{ aspectRatio: "16 / 9", display: "grid", placeItems: "center", background: "radial-gradient(circle at 50% 30%, #c58cff22, #050607 78%)" }}>
              <Typography sx={{ fontSize: 40 }}>🎨</Typography>
            </Box>
            <Box sx={{ p: 1.5 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Meme Studio</Typography>
              <Typography variant="body2" color="text.secondary">Draw and compose images for the panel.</Typography>
            </Box>
          </Card>
        ) : null}
      </Box>
    </Stack>
  );
}
