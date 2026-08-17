import { Box } from "@mui/material";
import { UserProfile } from "../api";

/**
 * A profile's face.
 *
 * Sixteen squares across, because that is what reads on a 64x64 panel from
 * the other side of a room - a photograph at that size is a smudge. The
 * same drawing is used here and on the matrix, so what you draw is what
 * appears.
 *
 * Profiles without one show their initial rather than a placeholder
 * silhouette, which at least tells two people apart.
 */

const SIZE = 16;

/** Base62 digit to palette index, matching how frames are encoded. */
function index(character: string): number {
  if (character >= "0" && character <= "9") return character.charCodeAt(0) - 48;
  if (character >= "a" && character <= "z") return character.charCodeAt(0) - 87;
  if (character >= "A" && character <= "Z") return character.charCodeAt(0) - 29;
  return -1;
}

/** A stable colour per profile, so an initial is not just grey. */
function tint(id: string): string {
  let hash = 0;
  for (const character of id) hash = (hash * 31 + character.charCodeAt(0)) % 360;
  return `hsl(${hash}, 62%, 46%)`;
}

export default function Avatar({ profile, size = 48 }: { profile: UserProfile; size?: number }) {
  const drawn = profile.avatar.length === SIZE && profile.palette.length > 0;

  if (!drawn) {
    return (
      <Box
        sx={{
          width: size,
          height: size,
          borderRadius: "22%",
          display: "grid",
          placeItems: "center",
          bgcolor: tint(profile.id),
          color: "#fff",
          fontWeight: 800,
          fontSize: size * 0.45,
          flexShrink: 0,
        }}
      >
        {(profile.name[0] || "?").toUpperCase()}
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: size,
        height: size,
        borderRadius: "22%",
        overflow: "hidden",
        display: "grid",
        gridTemplateColumns: `repeat(${SIZE}, 1fr)`,
        bgcolor: "#05070b",
        flexShrink: 0,
      }}
    >
      {profile.avatar.flatMap((row, y) =>
        Array.from(row).map((character, x) => (
          <Box
            key={`${x}-${y}`}
            sx={{ background: profile.palette[index(character)] ?? "transparent", aspectRatio: "1" }}
          />
        )),
      )}
    </Box>
  );
}
