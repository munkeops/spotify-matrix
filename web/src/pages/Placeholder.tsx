import { Card, CardContent, Typography, Button, Stack } from "@mui/material";

export default function Placeholder({ title, note, link }: { title: string; note: string; link?: string }) {
  return (
    <Card>
      <CardContent>
        <Stack spacing={1.5}>
          <Typography variant="h6">{title}</Typography>
          <Typography variant="body2" color="text.secondary">{note}</Typography>
          {link ? (
            <Button variant="contained" href={link} sx={{ alignSelf: "flex-start" }}>
              Open
            </Button>
          ) : null}
        </Stack>
      </CardContent>
    </Card>
  );
}
