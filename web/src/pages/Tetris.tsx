import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Stack, Typography } from "@mui/material";
import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import ArrowDownwardRoundedIcon from "@mui/icons-material/ArrowDownwardRounded";
import RotateLeftRoundedIcon from "@mui/icons-material/RotateLeftRounded";
import RotateRightRoundedIcon from "@mui/icons-material/RotateRightRounded";
import VerticalAlignBottomRoundedIcon from "@mui/icons-material/VerticalAlignBottomRounded";
import PauseRoundedIcon from "@mui/icons-material/PauseRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import RestartAltRoundedIcon from "@mui/icons-material/RestartAltRounded";
import SwapHorizRoundedIcon from "@mui/icons-material/SwapHorizRounded";
import { TetrisAction, TetrisState, applyWidget, getTetrisState, sendTetrisInput } from "../api";

const COLS = 10;
const ROWS = 20;
const POLL_MS = 200;
const REPEAT_DELAY_MS = 220;
const REPEAT_EVERY_MS = 90;

const PIECE_COLOR: Record<string, string> = {
  I: "#00d6e4", O: "#f0ce2e", T: "#b054e8", S: "#48d660", Z: "#ee4a54", J: "#4a76f0", L: "#f4942c",
};

// Shapes mirror the runtime so next/hold tiles match what the matrix draws.
const PIECE_CELLS: Record<string, number[][]> = {
  I: [[0, 0], [1, 0], [2, 0], [3, 0]],
  O: [[0, 0], [1, 0], [0, 1], [1, 1]],
  T: [[1, 0], [0, 1], [1, 1], [2, 1]],
  S: [[1, 0], [2, 0], [0, 1], [1, 1]],
  Z: [[0, 0], [1, 0], [1, 1], [2, 1]],
  J: [[0, 0], [0, 1], [1, 1], [2, 1]],
  L: [[2, 0], [0, 1], [1, 1], [2, 1]],
};

const KEY_ACTIONS: Record<string, TetrisAction> = {
  ArrowLeft: "left",
  ArrowRight: "right",
  ArrowDown: "softDrop",
  ArrowUp: "rotateCw",
  " ": "hardDrop",
  x: "rotateCw",
  z: "rotateCcw",
  c: "hold",
  Shift: "hold",
  p: "togglePause",
  r: "restart",
};

type Cell = { color: string; ghost: boolean } | null;

function buildGrid(state: TetrisState | null): Cell[][] {
  const grid: Cell[][] = Array.from({ length: ROWS }, () => Array.from({ length: COLS }, () => null as Cell));
  if (!state) return grid;
  state.board.forEach((row, y) => {
    for (let x = 0; x < Math.min(COLS, row.length); x += 1) {
      const cell = row[x];
      if (cell !== ".") grid[y][x] = { color: PIECE_COLOR[cell] || "#8ea2ff", ghost: false };
    }
  });
  const activeColor = PIECE_COLOR[state.activeType] || "#8ea2ff";
  state.ghost.forEach(([x, y]) => {
    if (y >= 0 && y < ROWS && x >= 0 && x < COLS && !grid[y][x]) grid[y][x] = { color: activeColor, ghost: true };
  });
  state.active.forEach(([x, y]) => {
    if (y >= 0 && y < ROWS && x >= 0 && x < COLS) grid[y][x] = { color: activeColor, ghost: false };
  });
  return grid;
}

function PieceTile({ piece, label, dim }: { piece: string; label: string; dim?: boolean }) {
  const cells = PIECE_CELLS[piece] || [];
  const width = cells.length ? Math.max(...cells.map((c) => c[0])) + 1 : 1;
  const height = cells.length ? Math.max(...cells.map((c) => c[1])) + 1 : 1;
  return (
    <Box sx={{ textAlign: "center" }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>{label}</Typography>
      <Box sx={{ width: 52, height: 40, display: "grid", placeItems: "center", bgcolor: "#05070b", borderRadius: 1, border: "1px solid", borderColor: "divider", opacity: dim ? 0.4 : 1 }}>
        <Box sx={{ display: "grid", gridTemplateColumns: `repeat(${width}, 8px)`, gridTemplateRows: `repeat(${height}, 8px)`, gap: "1px" }}>
          {Array.from({ length: width * height }, (_, index) => {
            const x = index % width;
            const y = Math.floor(index / width);
            const filled = cells.some((cell) => cell[0] === x && cell[1] === y);
            return <Box key={index} sx={{ borderRadius: "1px", bgcolor: filled ? PIECE_COLOR[piece] : "transparent" }} />;
          })}
        </Box>
      </Box>
    </Box>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>{label}</Typography>
      <Typography variant="h6" sx={{ lineHeight: 1.2 }}>{value}</Typography>
    </Box>
  );
}

export default function Tetris() {
  const [state, setState] = useState<TetrisState | null>(null);
  const [live, setLive] = useState(false);
  const [active, setActive] = useState(false);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const repeatTimers = useRef<{ delay?: number; interval?: number }>({});

  const refresh = useCallback(async () => {
    try {
      const response = await getTetrisState();
      setState(response.state);
      setLive(response.live);
      setActive(response.active);
      setRunning(response.running);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  const send = useCallback(async (action: TetrisAction) => {
    try {
      await sendTetrisInput(action);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  const stopRepeat = useCallback(() => {
    window.clearTimeout(repeatTimers.current.delay);
    window.clearInterval(repeatTimers.current.interval);
    repeatTimers.current = {};
  }, []);

  // Press-and-hold repeats moves the way a real gamepad does.
  const startRepeat = useCallback((action: TetrisAction) => {
    stopRepeat();
    send(action);
    repeatTimers.current.delay = window.setTimeout(() => {
      repeatTimers.current.interval = window.setInterval(() => send(action), REPEAT_EVERY_MS);
    }, REPEAT_DELAY_MS);
  }, [send, stopRepeat]);

  useEffect(() => stopRepeat, [stopRepeat]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const action = KEY_ACTIONS[event.key] || KEY_ACTIONS[event.key.toLowerCase()];
      if (!action) return;
      event.preventDefault();
      if (event.repeat && !["left", "right", "softDrop"].includes(action)) return;
      send(action);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [send]);

  const startGame = async () => {
    setStarting(true);
    try {
      await applyWidget("core.tetris", null);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  };

  const grid = useMemo(() => buildGrid(live ? state : null), [state, live]);

  const padButton = (action: TetrisAction, icon: React.ReactNode, options: { repeat?: boolean; label: string; grow?: boolean }) => (
    <Button
      variant="outlined"
      aria-label={options.label}
      onPointerDown={(event) => {
        event.preventDefault();
        if (options.repeat) startRepeat(action);
        else send(action);
      }}
      onPointerUp={stopRepeat}
      onPointerLeave={stopRepeat}
      onPointerCancel={stopRepeat}
      onContextMenu={(event) => event.preventDefault()}
      sx={{
        minWidth: 0,
        flex: options.grow ? 1 : "0 0 auto",
        width: options.grow ? "auto" : 64,
        height: 56,
        borderRadius: 2,
        touchAction: "none",
        userSelect: "none",
      }}
    >
      {icon}
    </Button>
  );

  if (loading) {
    return <Box sx={{ display: "grid", placeItems: "center", py: 8 }}><CircularProgress /></Box>;
  }

  return (
    <Stack spacing={2}>
      {error ? <Alert severity="error">{error}</Alert> : null}

      {!active ? (
        <Alert
          severity="info"
          action={<Button size="small" onClick={startGame} disabled={starting}>Start</Button>}
        >
          Tetris is not on the matrix right now.
        </Alert>
      ) : !live ? (
        <Alert severity="warning" action={<Button size="small" onClick={startGame} disabled={starting}>Restart</Button>}>
          {running ? "Waiting for the matrix runtime to publish the board…" : "The matrix runtime is stopped."}
        </Alert>
      ) : null}

      <Card>
        <CardContent>
          <Stack direction="row" spacing={2}>
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: `repeat(${COLS}, 1fr)`,
                gridTemplateRows: `repeat(${ROWS}, 1fr)`,
                gap: "1px",
                bgcolor: "#0a0d14",
                p: "3px",
                borderRadius: 1,
                border: "1px solid",
                borderColor: "divider",
                width: { xs: 150, sm: 190 },
                aspectRatio: "1 / 2",
                flex: "0 0 auto",
              }}
            >
              {grid.flatMap((row, y) =>
                row.map((cell, x) => (
                  <Box
                    key={`${x}-${y}`}
                    sx={{
                      borderRadius: "1px",
                      bgcolor: cell ? cell.color : "#12161f",
                      opacity: cell?.ghost ? 0.28 : 1,
                    }}
                  />
                )),
              )}
            </Box>

            <Stack spacing={1.5} sx={{ flex: 1, minWidth: 0 }}>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Chip size="small" color={live ? "success" : "default"} label={live ? "Live" : "Idle"} />
                {state?.gameOver ? <Chip size="small" color="error" label="Game over" /> : null}
                {state?.paused ? <Chip size="small" color="warning" label="Paused" /> : null}
              </Stack>
              <Stat label="Score" value={state?.score ?? 0} />
              <Stack direction="row" spacing={3}>
                <Stat label="Lines" value={state?.lines ?? 0} />
                <Stat label="Level" value={state?.level ?? 1} />
              </Stack>
              <Stack direction="row" spacing={1}>
                <PieceTile piece={state?.next || ""} label="Next" />
                <PieceTile piece={state?.hold || ""} label="Hold" dim={state?.holdLocked} />
              </Stack>
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Stack spacing={1.5}>
            <Stack direction="row" spacing={1} justifyContent="center">
              {padButton("rotateCcw", <RotateLeftRoundedIcon />, { label: "Rotate counter clockwise" })}
              {padButton("rotateCw", <RotateRightRoundedIcon />, { label: "Rotate clockwise" })}
              {padButton("hold", <SwapHorizRoundedIcon />, { label: "Hold piece" })}
            </Stack>
            <Stack direction="row" spacing={1} justifyContent="center">
              {padButton("left", <ArrowBackRoundedIcon />, { label: "Move left", repeat: true })}
              {padButton("softDrop", <ArrowDownwardRoundedIcon />, { label: "Soft drop", repeat: true })}
              {padButton("right", <ArrowForwardRoundedIcon />, { label: "Move right", repeat: true })}
            </Stack>
            <Stack direction="row" spacing={1}>
              {padButton("hardDrop", <VerticalAlignBottomRoundedIcon />, { label: "Hard drop", grow: true })}
            </Stack>
            <Stack direction="row" spacing={1}>
              <Button
                fullWidth
                variant="text"
                startIcon={state?.paused ? <PlayArrowRoundedIcon /> : <PauseRoundedIcon />}
                onClick={() => send("togglePause")}
              >
                {state?.paused ? "Resume" : "Pause"}
              </Button>
              <Button fullWidth variant="text" startIcon={<RestartAltRoundedIcon />} onClick={() => send("restart")}>
                Restart
              </Button>
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ textAlign: "center" }}>
              Keyboard: arrows move, up or X rotates, Z rotates back, space hard drops, C holds, P pauses, R restarts.
            </Typography>
          </Stack>
        </CardContent>
      </Card>
    </Stack>
  );
}
