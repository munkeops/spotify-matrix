import { ReactNode } from "react";
import { Card, CardContent, Stack, Typography } from "@mui/material";

/**
 * One block of settings.
 *
 * Every panel was rolling its own heading - two different variants, two
 * different colours, and its own spacing - so the page read as several
 * pages stacked. There is one shape here and everything uses it: an icon,
 * a title, whatever status belongs beside it, then the controls.
 */
export default function SettingsSection({
  title,
  icon,
  action,
  children,
}: {
  title: string;
  icon?: ReactNode;
  /** Status or a button, shown at the end of the heading row. */
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Stack direction="row" alignItems="center" spacing={1}>
            {icon}
            <Typography
              variant="overline"
              color="text.secondary"
              sx={{ flex: 1, letterSpacing: 0.8, lineHeight: 1.6 }}
            >
              {title}
            </Typography>
            {action}
          </Stack>
          {children}
        </Stack>
      </CardContent>
    </Card>
  );
}
