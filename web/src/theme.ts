import { createTheme } from "@mui/material/styles";

// Dark, teal-accented theme matching the Assistant Matrix brand.
export const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#4be0c0", contrastText: "#06231d" },
    secondary: { main: "#8ea2ff" },
    background: { default: "#0b0d12", paper: "#151922" },
    text: { primary: "#e8ecf1", secondary: "#93a0b4" },
    divider: "rgba(255,255,255,0.08)",
  },
  shape: { borderRadius: 14 },
  typography: {
    fontFamily: 'Roboto, system-ui, -apple-system, "Segoe UI", sans-serif',
    h6: { fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 600 },
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: { backgroundImage: "none", border: "1px solid rgba(255,255,255,0.08)" },
      },
    },
    MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
  },
});
