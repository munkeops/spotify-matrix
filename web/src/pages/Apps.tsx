import { useEffect, useState, useCallback, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button, Card, CardActionArea, Typography, Box, CircularProgress, Alert, Chip, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, IconButton, Stack } from "@mui/material";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import SportsEsportsRoundedIcon from "@mui/icons-material/SportsEsportsRounded";
import { canPreview, gameIdOf, isGame, LocalApp, listLocalApps, applyApp, getAppConfig, previewApp, uninstallApp } from "../api";
import AppConfigDrawer from "../components/AppConfigDrawer";
import DisplayPolicyPanel from "../components/DisplayPolicyPanel";
import { SHELVES, ShelfKey, ShelfTabs, colorFor, groupByShelf } from "../shelves";

function Placeholder({ app }: { app: LocalApp }) {
  const color = colorFor(app.manifest.category);
  return (
    <Box sx={{ width: "100%", height: "100%", display: "grid", placeItems: "center", background: `radial-gradient(circle at 50% 35%, ${color}22, #050607 75%)` }}>
      <Typography sx={{ fontSize: 34, fontWeight: 800, color }}>{app.manifest.name.charAt(0)}</Typography>
    </Box>
  );
}

export default function Apps() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [apps, setApps] = useState<LocalApp[]>([]);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<LocalApp | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [applyingId, setApplyingId] = useState("");
  //: The app awaiting confirmation. Uninstalling deletes its files and its
  //: saved settings, so it asks first.
  const [removing, setRemoving] = useState<LocalApp | null>(null);
  const [removingBusy, setRemovingBusy] = useState(false);

  const requested = params.get("tab") as ShelfKey | null;
  const tab: ShelfKey = SHELVES.some((shelf) => shelf.key === requested) ? (requested as ShelfKey) : "apps";
  const setTab = (next: ShelfKey) => setParams(next === "apps" ? {} : { tab: next }, { replace: true });

  const loadPreviews = useCallback(async (list: LocalApp[]) => {
    await Promise.all(
      list
        .filter((w) => canPreview(w))
        .map(async (w) => {
          try {
            const cfg = await getAppConfig(w.manifest.id);
            const p = await previewApp(w.manifest.id, cfg.config);
            setPreviews((prev) => ({ ...prev, [w.manifest.id]: p.dataUrl }));
          } catch {
            /* ignore */
          }
        }),
    );
  }, []);

  const refresh = useCallback(async () => {
    try {
      const r = await listLocalApps();
      setApps(r.apps || []);
      setError("");
      loadPreviews(r.apps || []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [loadPreviews]);

  useEffect(() => { refresh(); }, [refresh]);

  const confirmRemove = async () => {
    if (!removing) return;
    setRemovingBusy(true);
    try {
      await uninstallApp(removing.manifest.id);
      setRemoving(null);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRemovingBusy(false);
    }
  };

  const runNow = async (app: LocalApp) => {
    setApplyingId(app.manifest.id);
    try {
      await applyApp(app.manifest.id, null);
      await refresh();
      if (isGame(app)) navigate(`/play/${gameIdOf(app)}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setApplyingId("");
    }
  };

  const openSettings = (app: LocalApp) => {
    if (!app.configurable) { runNow(app); return; }
    setSelected(app);
    setDrawerOpen(true);
  };

  // Same three shelves as the Store, so a game sits in the same place whether
  // you are browsing or managing what you already have.
  const shelves = useMemo(
    () => groupByShelf(apps.map((app) => ({ app, id: app.manifest.id, category: app.manifest.category, isGame: isGame(app) }))),
    [apps],
  );

  if (loading) {
    return <Box sx={{ display: "grid", placeItems: "center", py: 8 }}><CircularProgress /></Box>;
  }

  const shelf = shelves[tab];

  return (
    <Stack spacing={2}>
      {error ? <Alert severity="error">{error}</Alert> : null}
      <DisplayPolicyPanel />

      <Box>
        <Typography variant="h6">Installed</Typography>
        <Typography variant="body2" color="text.secondary">
          {SHELVES.find((entry) => entry.key === tab)!.blurb}
        </Typography>
      </Box>

      <ShelfTabs
        value={tab}
        onChange={setTab}
        counts={{ apps: shelves.apps.length, play: shelves.play.length, creative: shelves.creative.length }}
      />

      {shelf.length === 0 ? (
        <Alert severity="info" action={<Chip size="small" label="Store" onClick={() => navigate(`/store?tab=${tab}`)} />}>
          Nothing installed on this shelf yet.
        </Alert>
      ) : null}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(auto-fill, minmax(150px, 1fr))" }, gap: 1.5 }}>
        {shelf.map(({ app }) => {
          const id = app.manifest.id;
          const game = isGame(app);
          return (
            <Card key={id} sx={{ position: "relative", borderColor: app.active ? "primary.main" : "divider" }}>
              <CardActionArea onClick={() => openSettings(app)}>
                <Box sx={{ aspectRatio: "1", bgcolor: "#050607" }}>
                  {previews[id] ? (
                    <img src={previews[id]} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", imageRendering: "pixelated", display: "block" }} />
                  ) : (
                    <Placeholder app={app} />
                  )}
                </Box>
                <Box sx={{ p: 1 }}>
                  <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>{app.manifest.name}</Typography>
                  <Typography variant="caption" color="text.secondary">{app.manifest.category}</Typography>
                </Box>
              </CardActionArea>
              {app.active ? <Chip size="small" label="Active" color="primary" sx={{ position: "absolute", top: 6, left: 6, height: 20 }} /> : null}
              {app.builtIn ? null : (
                <IconButton
                  size="small"
                  onClick={() => setRemoving(app)}
                  aria-label={`Uninstall ${app.manifest.name}`}
                  sx={{ position: "absolute", bottom: 4, right: 4, bgcolor: "rgba(0,0,0,0.55)", "&:hover": { bgcolor: "rgba(0,0,0,0.75)", color: "error.main" } }}
                >
                  <DeleteOutlineRoundedIcon fontSize="small" sx={{ color: "#fff" }} />
                </IconButton>
              )}
              <IconButton
                size="small"
                onClick={() => runNow(app)}
                disabled={applyingId === id}
                aria-label={game ? "Play" : "Put on matrix"}
                sx={{ position: "absolute", top: 4, right: 4, bgcolor: "rgba(0,0,0,0.55)", "&:hover": { bgcolor: "rgba(0,0,0,0.75)" } }}
              >
                {game ? (
                  <SportsEsportsRoundedIcon fontSize="small" sx={{ color: "#fff" }} />
                ) : (
                  <PlayArrowRoundedIcon fontSize="small" sx={{ color: "#fff" }} />
                )}
              </IconButton>
            </Card>
          );
        })}

        {tab === "creative" ? (
          <Card component="a" href="/studio/" sx={{ textDecoration: "none" }}>
            <Box sx={{ aspectRatio: "1", display: "grid", placeItems: "center", background: "radial-gradient(circle at 50% 35%, #c58cff22, #050607 75%)" }}>
              <Typography sx={{ fontSize: 30, fontWeight: 800, color: "#c58cff" }}>🎨</Typography>
            </Box>
            <Box sx={{ p: 1 }}>
              <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>Meme Studio</Typography>
              <Typography variant="caption" color="text.secondary">create</Typography>
            </Box>
          </Card>
        ) : null}
      </Box>

      <AppConfigDrawer app={selected} open={drawerOpen} onClose={() => setDrawerOpen(false)} onApplied={refresh} />

      <Dialog open={removing !== null} onClose={() => setRemoving(null)}>
        <DialogTitle>Uninstall {removing?.manifest.name}?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Its files and anything you configured for it are deleted. It stays in the
            store, so you can install it again - but its settings will not come back.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRemoving(null)} disabled={removingBusy}>Keep</Button>
          <Button color="error" variant="contained" disabled={removingBusy} onClick={confirmRemove}>
            {removingBusy ? "Uninstalling…" : "Uninstall"}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
