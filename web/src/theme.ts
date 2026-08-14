import { createTheme } from "@mui/material/styles";

/** One corner radius for everything: cards, fields, buttons, chips. */
export const RADIUS = 10;

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
  shape: { borderRadius: RADIUS },
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

    // Inputs carry their label above rather than notched into the outline.
    // The notch reads as part of the border, cuts the frame, and makes every
    // field a different height depending on whether it has a label at all.
    MuiTextField: { defaultProps: { size: "small", fullWidth: true } },
    MuiOutlinedInput: {
      styleOverrides: {
        // One radius for every control, matching the cards they sit in.
        root: { borderRadius: RADIUS },
        notchedOutline: { top: 0, "& legend": { display: "none" } },
      },
    },
    MuiInputLabel: { styleOverrides: { outlined: { display: "none" } } },
    MuiFormHelperText: {
      styleOverrides: { root: { marginLeft: 0, marginTop: 6, fontSize: 12 } },
    },
    MuiSelect: { styleOverrides: { select: { paddingTop: 10, paddingBottom: 10 } } },
    MuiButton: { styleOverrides: { root: { borderRadius: RADIUS } } },
    MuiChip: { styleOverrides: { root: { borderRadius: RADIUS / 2 } } },
    MuiAlert: { styleOverrides: { root: { borderRadius: RADIUS } } },
    MuiToggleButton: { styleOverrides: { root: { borderRadius: RADIUS } } },
  },
});
