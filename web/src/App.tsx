import { AppBar, Box, BottomNavigation, BottomNavigationAction, Paper, Toolbar, Typography, Container } from "@mui/material";
import HomeRoundedIcon from "@mui/icons-material/HomeRounded";
import ExtensionRoundedIcon from "@mui/icons-material/ExtensionRounded";
import BrushRoundedIcon from "@mui/icons-material/BrushRounded";
import SettingsRoundedIcon from "@mui/icons-material/SettingsRounded";
import { Routes, Route, useNavigate, useLocation, Navigate } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Plugins from "./pages/Plugins";
import Placeholder from "./pages/Placeholder";

const NAV = [
  { label: "Home", value: "/", icon: <HomeRoundedIcon /> },
  { label: "Plugins", value: "/plugins", icon: <ExtensionRoundedIcon /> },
  { label: "Studio", value: "/studio", icon: <BrushRoundedIcon /> },
  { label: "Settings", value: "/settings", icon: <SettingsRoundedIcon /> },
];

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const current = NAV.some((n) => n.value === location.pathname) ? location.pathname : "/";

  return (
    <Box sx={{ minHeight: "100dvh", display: "flex", flexDirection: "column", bgcolor: "background.default" }}>
      <AppBar position="sticky" elevation={0} sx={{ bgcolor: "background.paper", borderBottom: "1px solid", borderColor: "divider" }}>
        <Toolbar>
          <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: "primary.main", mr: 1.5 }} />
          <Typography variant="h6" color="text.primary">Assistant Matrix</Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="sm" sx={{ flex: 1, py: 2, pb: 12 }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/plugins" element={<Plugins />} />
          <Route path="/studio" element={<Placeholder title="Meme Studio" note="Opens the canvas editor." link="/studio/" />} />
          <Route path="/settings" element={<Placeholder title="Settings" note="Matrix, store, and Bluetooth coming here." />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Container>

      <Paper elevation={3} sx={{ position: "fixed", bottom: 0, left: 0, right: 0, borderTop: "1px solid", borderColor: "divider" }}>
        <BottomNavigation value={current} onChange={(_, value) => navigate(value)} showLabels>
          {NAV.map((item) => (
            <BottomNavigationAction key={item.value} label={item.label} value={item.value} icon={item.icon} />
          ))}
        </BottomNavigation>
      </Paper>
    </Box>
  );
}
