import { Box, Stack, Typography } from "@mui/material";

/**
 * The mini-joystick module, drawn.
 *
 * The diagram cannot know how a given board is laid out, so it does not
 * pretend to: press a button and it lights up here. That is what makes the
 * silkscreen letters mean something, and it is why `pressed` matters more
 * than getting the picture exactly right.
 */

export type ModuleControl = "a" | "b" | "c" | "d" | "ok";

const SIZE = 44;

function Key({
  id,
  label,
  action,
  selected,
  pressed,
  onSelect,
  round,
}: {
  id: ModuleControl;
  label: string;
  action: string;
  selected: boolean;
  pressed: boolean;
  onSelect: (id: ModuleControl) => void;
  round?: boolean;
}) {
  return (
    <Box
      role="button"
      tabIndex={0}
      aria-label={`${label}: ${action}`}
      aria-pressed={selected}
      onClick={() => onSelect(id)}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(id)}
      sx={{
        width: SIZE,
        height: SIZE,
        borderRadius: round ? "50%" : 2,
        display: "grid",
        placeItems: "center",
        cursor: "pointer",
        userSelect: "none",
        transition: "transform 120ms, box-shadow 120ms, background-color 120ms",
        // Pressed beats selected: it is live feedback from the hardware.
        bgcolor: pressed ? "primary.main" : selected ? "action.selected" : "background.default",
        color: pressed ? "primary.contrastText" : "text.primary",
        border: "2px solid",
        borderColor: selected ? "primary.main" : "divider",
        transform: pressed ? "scale(0.92)" : "none",
        boxShadow: pressed ? "0 0 0 6px rgba(75,224,192,0.18)" : "none",
        "&:hover": { borderColor: "primary.main" },
      }}
    >
      <Typography variant="subtitle2" sx={{ fontWeight: 700, lineHeight: 1 }}>
        {label}
      </Typography>
    </Box>
  );
}

export default function ModuleDiagram({
  bindings,
  labels,
  actionLabels,
  selected,
  pressed,
  onSelect,
}: {
  bindings: Record<string, string>;
  labels: Record<string, string>;
  actionLabels: Record<string, string>;
  selected: ModuleControl;
  pressed: string;
  onSelect: (id: ModuleControl) => void;
}) {
  const key = (id: ModuleControl, round?: boolean) => (
    <Key
      id={id}
      round={round}
      label={id === "ok" ? "OK" : id.toUpperCase()}
      action={actionLabels[bindings[id]] ?? "Nothing"}
      selected={selected === id}
      pressed={pressed === id}
      onSelect={onSelect}
    />
  );

  return (
    <Stack spacing={1.5} alignItems="center">
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 3,
          p: 2.5,
          borderRadius: 3,
          border: "1px solid",
          borderColor: "divider",
          bgcolor: "background.paper",
        }}
      >
        {/* The stick, with its press as the centre. */}
        <Stack alignItems="center" spacing={0.75}>
          <Box
            sx={{
              width: SIZE * 1.9,
              height: SIZE * 1.9,
              borderRadius: "50%",
              display: "grid",
              placeItems: "center",
              border: "2px dashed",
              borderColor: "divider",
            }}
          >
            {key("ok", true)}
          </Box>
          <Typography variant="caption" color="text.secondary">
            Stick
          </Typography>
        </Stack>

        {/* Four buttons. Which letter is where is the board's business, so
            press one and watch which of these lights up. */}
        <Box sx={{ display: "grid", gridTemplateColumns: "auto auto", gap: 1.25 }}>
          {key("a")}
          {key("b")}
          {key("c")}
          {key("d")}
        </Box>
      </Box>

      <Typography variant="caption" color="text.secondary" textAlign="center">
        Press a button on the module and it lights up here, so you can tell which is which.
        Tap one to change what it does.
      </Typography>

      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        {labels[selected] ?? selected.toUpperCase()} — {actionLabels[bindings[selected]] ?? "Nothing"}
      </Typography>
    </Stack>
  );
}
