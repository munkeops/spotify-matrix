import { ReactNode } from "react";
import { Stack, Typography } from "@mui/material";

/**
 * A labelled form control.
 *
 * MUI's outlined inputs notch their label into the border, which cuts the
 * frame and leaves fields at different heights depending on whether they
 * carry a label. The label sits above here, so every control in a form is
 * the same shape and the outline stays an outline.
 */
export default function Field({
  label,
  help,
  children,
}: {
  label: string;
  help?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Stack spacing={0.75}>
      <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 600, letterSpacing: 0.2 }}>
        {label}
      </Typography>
      {children}
      {help ? (
        <Typography variant="caption" color="text.secondary">
          {help}
        </Typography>
      ) : null}
    </Stack>
  );
}
