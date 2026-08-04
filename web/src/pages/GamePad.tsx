import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Alert, Box, Button, Card, CardContent, Chip, CircularProgress, IconButton, Stack, Typography } from "@mui/material";
import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import ArrowUpwardRoundedIcon from "@mui/icons-material/ArrowUpwardRounded";
import ArrowDownwardRoundedIcon from "@mui/icons-material/ArrowDownwardRounded";
import RotateLeftRoundedIcon from "@mui/icons-material/RotateLeftRounded";
import RotateRightRoundedIcon from "@mui/icons-material/RotateRightRounded";
import VerticalAlignBottomRoundedIcon from "@mui/icons-material/VerticalAlignBottomRounded";
import SwapHorizRoundedIcon from "@mui/icons-material/SwapHorizRounded";
import PauseRoundedIcon from "@mui/icons-material/PauseRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import RestartAltRoundedIcon from "@mui/icons-material/RestartAltRounded";
import BoltRoundedIcon from "@mui/icons-material/BoltRounded";
import ChevronLeftRoundedIcon from "@mui/icons-material/ChevronLeftRounded";
import { GameFrame, GameScores, GameSummary, applyWidget, getGameScores, getGameState, listGames, sendGameInput } from "../api";
import PanelMirror from "../components/PanelMirror";

const POLL_MS = 200;
const REPEAT_DELAY_MS = 220;
const REPEAT_EVERY_MS = 90;
const REPEATABLE = new Set(["left", "right", "up", "down", "softDrop", "p2Up", "p2Down"]);

// Whichever of these a game declares becomes its big primary button.
const PRIMARY = ["flap", "fire", "drop", "hardDrop"];
const PRIMARY_LABEL: Record<string, string> = { flap: "Flap", fire: "Fire", drop: "Drop", hardDrop: "Hard drop" };

const KEYS: Record<string, string> = {
  ArrowLeft: "left", ArrowRight: "right", ArrowUp: "up", ArrowDown: "down",
  " ": "primary", Enter: "primary",
  x: "rotateCw", z: "rotateCcw", c: "hold",
  w: "p2Up", s: "p2Down",
  p: "togglePause", r: "restart",
};

export default function GamePad() {
  const { gameId = "tetris" } = useParams();
  const navigate = useNavigate();
  const [game, setGame] = useState<GameSummary | null>(null);
  const [frame, setFrame] = useState<GameFrame | null>(null);
  const [live, setLive] = useState(false);
  const [active, setActive] = useState(false);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [scores, setScores] = useState<GameScores | null>(null);
  const timers = useRef<{ delay?: number; interval?: number }>({});

  useEffect(() => {
    let cancelled = false;
    listGames()
      .then((r) => { if (!cancelled) setGame(r.games.find((g) => g.id === gameId) ?? null); })
      .catch((e) => { if (!cancelled) setError((e as Error).message); });
    return () => { cancelled = true; };
  }, [gameId]);

  const refresh = useCallback(async () => {
    try {
      const response = await getGameState(gameId);
      setFrame(response.state);
      setLive(response.live);
      setActive(response.active);
      setRunning(response.running);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  useEffect(() => {
    setLoading(true);
    refresh();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  // Reload the saved best when a round ends, so a new record shows up.
  const status = frame?.status ?? "playing";
  useEffect(() => {
    let cancelled = false;
    getGameScores(gameId)
      .then((r) => { if (!cancelled) setScores(r); })
      .catch(() => { /* a game with no scores yet is fine */ });
    return () => { cancelled = true; };
  }, [gameId, status]);

  const actions = useMemo(() => new Set(game?.actions ?? []), [game]);
  const primary = useMemo(() => PRIMARY.find((action) => actions.has(action)) ?? "", [actions]);

  const send = useCallback(async (action: string) => {
    if (!action) return;
    try {
      await sendGameInput(gameId, action);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [gameId]);

  const stopRepeat = useCallback(() => {
    window.clearTimeout(timers.current.delay);
    window.clearInterval(timers.current.interval);
    timers.current = {};
  }, []);

  useEffect(() => stopRepeat, [stopRepeat]);

  const press = useCallback((action: string) => {
    stopRepeat();
    send(action);
    if (!REPEATABLE.has(action)) return;
    // Press and hold repeats the way a real gamepad does.
    timers.current.delay = window.setTimeout(() => {
      timers.current.interval = window.setInterval(() => send(action), REPEAT_EVERY_MS);
    }, REPEAT_DELAY_MS);
  }, [send, stopRepeat]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const mapped = KEYS[event.key] ?? KEYS[event.key.toLowerCase()];
      if (!mapped) return;
      const action = mapped === "primary" ? primary : mapped;
      if (!action || (!actions.has(action) && !["togglePause", "restart"].includes(action))) return;
      event.preventDefault();
      if (event.repeat && !REPEATABLE.has(action)) return;
      send(action);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [send, actions, primary]);

  const startGame = async () => {
    if (!game) return;
    setStarting(true);
    try {
      await applyWidget(game.widgetId, null);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  };

  const pad = (action: string, icon: React.ReactNode, label: string, grow = false) => (
    <Button
      key={action}
      variant="outlined"
      aria-label={label}
      onPointerDown={(event) => { event.preventDefault(); press(action); }}
      onPointerUp={stopRepeat}
      onPointerLeave={stopRepeat}
      onPointerCancel={stopRepeat}
      onContextMenu={(event) => event.preventDefault()}
      sx={{ minWidth: 0, flex: grow ? 1 : "0 0 auto", width: grow ? "auto" : 64, height: 56, borderRadius: 2, touchAction: "none", userSelect: "none" }}
    >
      {icon}
    </Button>
  );

  const controls = () => {
    const layout = game?.layout ?? "dpad";
    const primaryButton = primary
      ? pad(primary, <Stack direction="row" spacing={0.5} alignItems="center"><BoltRoundedIcon />{PRIMARY_LABEL[primary]}</Stack>, PRIMARY_LABEL[primary], true)
      : null;

    if (layout === "tetris") {
      return (
        <>
          <Stack direction="row" spacing={1} justifyContent="center">
            {pad("rotateCcw", <RotateLeftRoundedIcon />, "Rotate counter clockwise")}
            {pad("rotateCw", <RotateRightRoundedIcon />, "Rotate clockwise")}
            {pad("hold", <SwapHorizRoundedIcon />, "Hold piece")}
          </Stack>
          <Stack direction="row" spacing={1} justifyContent="center">
            {pad("left", <ArrowBackRoundedIcon />, "Move left")}
            {pad("softDrop", <ArrowDownwardRoundedIcon />, "Soft drop")}
            {pad("right", <ArrowForwardRoundedIcon />, "Move right")}
          </Stack>
          <Stack direction="row" spacing={1}>
            {pad("hardDrop", <VerticalAlignBottomRoundedIcon />, "Hard drop", true)}
          </Stack>
        </>
      );
    }

    if (layout === "dpad") {
      return (
        <>
          <Stack direction="row" justifyContent="center">{pad("up", <ArrowUpwardRoundedIcon />, "Up")}</Stack>
          <Stack direction="row" spacing={1} justifyContent="center">
            {pad("left", <ArrowBackRoundedIcon />, "Left")}
            {pad("down", <ArrowDownwardRoundedIcon />, "Down")}
            {pad("right", <ArrowForwardRoundedIcon />, "Right")}
          </Stack>
          {primaryButton ? <Stack direction="row" spacing={1}>{primaryButton}</Stack> : null}
        </>
      );
    }

    if (layout === "vertical") {
      return (
        <>
          <Stack direction="row" spacing={4} justifyContent="center">
            <Stack spacing={1} alignItems="center">
              <Typography variant="caption" color="text.secondary">You</Typography>
              {pad("up", <ArrowUpwardRoundedIcon />, "Up")}
              {pad("down", <ArrowDownwardRoundedIcon />, "Down")}
            </Stack>
            {actions.has("p2Up") ? (
              <Stack spacing={1} alignItems="center">
                <Typography variant="caption" color="text.secondary">P2</Typography>
                {pad("p2Up", <ArrowUpwardRoundedIcon />, "Player two up")}
                {pad("p2Down", <ArrowDownwardRoundedIcon />, "Player two down")}
              </Stack>
            ) : null}
          </Stack>
        </>
      );
    }

    if (layout === "tap") {
      return <Stack direction="row" spacing={1}>{primaryButton}</Stack>;
    }

    return (
      <>
        <Stack direction="row" spacing={1} justifyContent="center">
          {pad("left", <ArrowBackRoundedIcon />, "Left")}
          {pad("right", <ArrowForwardRoundedIcon />, "Right")}
        </Stack>
        {primaryButton ? <Stack direction="row" spacing={1}>{primaryButton}</Stack> : null}
      </>
    );
  };

  if (loading && !game) {
    return <Box sx={{ display: "grid", placeItems: "center", py: 8 }}><CircularProgress /></Box>;
  }

  if (!game) {
    return <Alert severity="error" action={<Button size="small" onClick={() => navigate("/store?tab=play")}>Back</Button>}>Unknown game “{gameId}”.</Alert>;
  }


  return (
    <Stack spacing={2}>
      {error ? <Alert severity="error">{error}</Alert> : null}

      <Stack direction="row" alignItems="center" spacing={1}>
        <IconButton size="small" onClick={() => navigate("/store?tab=play")} aria-label="Back to games"><ChevronLeftRoundedIcon /></IconButton>
        <Typography variant="h6" sx={{ flex: 1 }} noWrap>{game.name}</Typography>
        <Chip size="small" color={live ? "success" : "default"} label={live ? "Live" : "Idle"} />
      </Stack>

      {!active ? (
        <Alert severity="info" action={<Button size="small" onClick={startGame} disabled={starting}>Start</Button>}>
          {game.name} is not on the matrix right now.
        </Alert>
      ) : !live ? (
        <Alert severity="warning" action={<Button size="small" onClick={startGame} disabled={starting}>Restart</Button>}>
          {running ? "Waiting for the runtime to publish a frame…" : "The matrix runtime is stopped."}
        </Alert>
      ) : null}

      <Card>
        <CardContent>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "flex-start" }}>
            <Box sx={{ width: { xs: "100%", sm: 240 }, flex: "0 0 auto" }}>
              <PanelMirror frame={live ? frame : null} dim={!live} />
            </Box>
            <Stack spacing={1.5} sx={{ flex: 1, minWidth: 0, width: "100%" }}>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {status === "gameOver" ? <Chip size="small" color="error" label="Game over" /> : null}
                {status === "won" ? <Chip size="small" color="success" label="You win" /> : null}
                {status === "paused" ? <Chip size="small" color="warning" label="Paused" /> : null}
              </Stack>
              <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(80px, 1fr))", gap: 1 }}>
                {Object.entries(frame?.hud ?? {}).map(([label, value]) => (
                  <Box key={label}>
                    <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>{label}</Typography>
                    <Typography variant="h6" sx={{ lineHeight: 1.2 }} noWrap>{String(value)}</Typography>
                  </Box>
                ))}
              </Box>
              <Typography variant="body2" color="text.secondary">{game.summary}</Typography>
              {scores && scores.plays > 0 ? (
                <Typography variant="caption" color="text.secondary">
                  {scores.best > 0 ? `Best ${scores.best} · ` : ""}{scores.plays} play{scores.plays === 1 ? "" : "s"}
                </Typography>
              ) : null}
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Stack spacing={1.5}>
            {controls()}
            <Stack direction="row" spacing={1}>
              <Button fullWidth variant="text" startIcon={status === "paused" ? <PlayArrowRoundedIcon /> : <PauseRoundedIcon />} onClick={() => send("togglePause")}>
                {status === "paused" ? "Resume" : "Pause"}
              </Button>
              <Button fullWidth variant="text" startIcon={<RestartAltRoundedIcon />} onClick={() => send("restart")}>
                Restart
              </Button>
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ textAlign: "center" }}>
              Keyboard: arrows move, space is the action button, P pauses, R restarts
              {actions.has("rotateCw") ? ", X and Z rotate, C holds" : ""}
              {actions.has("p2Up") ? ", W and S drive player two" : ""}.
            </Typography>
          </Stack>
        </CardContent>
      </Card>
    </Stack>
  );
}
