import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Box, Card, CardActionArea, Chip, CircularProgress, Stack, Typography } from "@mui/material";
import { GameSummary, listGames, previewWidget } from "../api";

export default function Play() {
  const navigate = useNavigate();
  const [games, setGames] = useState<GameSummary[]>([]);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadPreviews = useCallback(async (list: GameSummary[]) => {
    await Promise.all(list.map(async (game) => {
      try {
        const preview = await previewWidget(game.widgetId, {});
        setPreviews((prev) => ({ ...prev, [game.id]: preview.dataUrl }));
      } catch { /* a missing tile just falls back to the initial */ }
    }));
  }, []);

  const refresh = useCallback(async () => {
    try {
      const response = await listGames();
      setGames(response.games || []);
      setError("");
      loadPreviews(response.games || []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [loadPreviews]);

  useEffect(() => {
    refresh();
    // The active game changes when a plugin is applied elsewhere or by joystick.
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  if (loading) {
    return <Box sx={{ display: "grid", placeItems: "center", py: 8 }}><CircularProgress /></Box>;
  }

  return (
    <Stack spacing={2}>
      {error ? <Alert severity="error">{error}</Alert> : null}
      <Box>
        <Typography variant="h6">Arcade</Typography>
        <Typography variant="body2" color="text.secondary">
          Pick a game to put it on the matrix and open its gamepad.
        </Typography>
      </Box>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(auto-fill, minmax(150px, 1fr))" }, gap: 1.5 }}>
        {games.map((game) => (
          <Card key={game.id} sx={{ position: "relative", borderColor: game.active ? "primary.main" : "divider" }}>
            <CardActionArea onClick={() => navigate(`/play/${game.id}`)}>
              <Box sx={{ aspectRatio: "1", bgcolor: "#050607", display: "grid", placeItems: "center" }}>
                {previews[game.id] ? (
                  <img src={previews[game.id]} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", imageRendering: "pixelated", display: "block" }} />
                ) : (
                  <Typography sx={{ fontSize: 34, fontWeight: 800, color: "#ff7ab8" }}>{game.name.charAt(0)}</Typography>
                )}
              </Box>
              <Box sx={{ p: 1 }}>
                <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>{game.name}</Typography>
                <Typography variant="caption" color="text.secondary" noWrap sx={{ display: "block" }}>{game.summary}</Typography>
              </Box>
            </CardActionArea>
            {game.active ? <Chip size="small" label="On screen" color="primary" sx={{ position: "absolute", top: 6, left: 6, height: 20 }} /> : null}
          </Card>
        ))}
      </Box>
    </Stack>
  );
}
