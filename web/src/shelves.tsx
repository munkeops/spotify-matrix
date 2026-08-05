import { Chip, Stack, Tab, Tabs } from "@mui/material";

// The Store and the Apps page use the same three shelves so a game is in
// the same place whether you are browsing or managing what you already have.
export const SHELVES = [
  { key: "apps", label: "Apps", blurb: "Music, time, weather and the assistant face." },
  { key: "play", label: "Play", blurb: "Games for the panel. Install one, then grab the gamepad." },
  { key: "creative", label: "Creative", blurb: "Make something of your own for the matrix." },
] as const;

export type ShelfKey = (typeof SHELVES)[number]["key"];

const CREATIVE_CATEGORIES = new Set(["custom"]);

// A few built-ins are filed under a category that does not match the shelf a
// person would look on. Slideshow is tagged "media" but it shows your own
// pictures, so it belongs beside Draw and Image.
const CREATIVE_IDS = new Set(["core.slideshow"]);

export function shelfOf(item: { id?: string; category: string; isGame?: boolean }): ShelfKey {
  if (item.isGame || item.category === "games") return "play";
  if (CREATIVE_IDS.has(item.id ?? "") || CREATIVE_CATEGORIES.has(item.category)) return "creative";
  return "apps";
}

export const CATEGORY_COLOR: Record<string, string> = {
  media: "#4be0c0", time: "#8ea2ff", assistant: "#ffb86b", information: "#7ee0a0",
  custom: "#c58cff", diagnostics: "#ff8c8c", weather: "#66d0ff", games: "#ff7ab8",
};

export const colorFor = (category: string) => CATEGORY_COLOR[category] || "#4be0c0";

export function groupByShelf<T extends { id?: string; category: string; isGame?: boolean }>(items: T[]): Record<ShelfKey, T[]> {
  const grouped: Record<ShelfKey, T[]> = { apps: [], play: [], creative: [] };
  for (const item of items) grouped[shelfOf(item)].push(item);
  return grouped;
}

export function ShelfTabs({
  value,
  onChange,
  counts,
}: {
  value: ShelfKey;
  onChange: (next: ShelfKey) => void;
  counts: Record<ShelfKey, number>;
}) {
  return (
    <Tabs
      value={value}
      onChange={(_, next) => onChange(next as ShelfKey)}
      variant="fullWidth"
      sx={{ borderBottom: 1, borderColor: "divider", minHeight: 44 }}
    >
      {SHELVES.map((shelf) => (
        <Tab
          key={shelf.key}
          value={shelf.key}
          label={
            <Stack direction="row" spacing={0.75} alignItems="center">
              <span>{shelf.label}</span>
              <Chip size="small" label={counts[shelf.key]} sx={{ height: 18, fontSize: 11 }} />
            </Stack>
          }
          sx={{ minHeight: 44, textTransform: "none" }}
        />
      ))}
    </Tabs>
  );
}
