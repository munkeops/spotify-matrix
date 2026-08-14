import {
  AppBar, Box, BottomNavigation, BottomNavigationAction, Paper, Toolbar, Typography, Container,
  Drawer, List, ListItemButton, ListItemIcon, ListItemText, useMediaQuery, useTheme,
} from "@mui/material";
import HomeRoundedIcon from "@mui/icons-material/HomeRounded";
import ExtensionRoundedIcon from "@mui/icons-material/ExtensionRounded";
import StorefrontRoundedIcon from "@mui/icons-material/StorefrontRounded";
import SettingsRoundedIcon from "@mui/icons-material/SettingsRounded";
import { Routes, Route, useNavigate, useLocation, Navigate } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Apps from "./pages/Apps";
import Store from "./pages/Store";
import Settings from "./pages/Settings";
import GamePad from "./pages/GamePad";

const NAV = [
  { label: "Home", value: "/", icon: <HomeRoundedIcon /> },
  { label: "Apps", value: "/apps", icon: <ExtensionRoundedIcon /> },
  { label: "App Store", value: "/store", icon: <StorefrontRoundedIcon /> },
  { label: "Settings", value: "/settings", icon: <SettingsRoundedIcon /> },
];

const DRAWER_WIDTH = 224;

function Brand() {
  return (
    <Toolbar sx={{ gap: 1.5 }}>
      <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: "primary.main" }} />
      <Typography variant="h6" color="text.primary">Assistant Matrix</Typography>
    </Toolbar>
  );
}

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const desktop = useMediaQuery(theme.breakpoints.up("md"));
  const current = NAV.some((n) => n.value === location.pathname)
    ? location.pathname
    : location.pathname.startsWith("/play")
      ? "/store"
      : "/";

  const content = (
    <Container maxWidth={desktop ? "md" : "sm"} sx={{ flex: 1, py: 2, pb: desktop ? 4 : 12 }}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/apps" element={<Apps />} />
        {/* Apps were called plugins; old links and bookmarks still work. */}
        <Route path="/plugins" element={<Navigate to="/apps" replace />} />
        <Route path="/widgets" element={<Navigate to="/apps" replace />} />
        {/* Browsing games lives in the Store now; this keeps old links working. */}
        <Route path="/play" element={<Navigate to="/store?tab=play" replace />} />
        <Route path="/play/:gameId" element={<GamePad />} />
        <Route path="/store" element={<Store />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Container>
  );

  if (desktop) {
    return (
      <Box sx={{ display: "flex", minHeight: "100dvh", bgcolor: "background.default" }}>
        <Drawer
          variant="permanent"
          sx={{ width: DRAWER_WIDTH, flexShrink: 0, "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box", bgcolor: "background.paper", borderRight: "1px solid", borderColor: "divider" } }}
        >
          <Brand />
          <List sx={{ px: 1 }}>
            {NAV.map((item) => (
              <ListItemButton key={item.value} selected={current === item.value} onClick={() => navigate(item.value)} sx={{ borderRadius: 2, mb: 0.5 }}>
                <ListItemIcon sx={{ minWidth: 40, color: current === item.value ? "primary.main" : "text.secondary" }}>{item.icon}</ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            ))}
          </List>
        </Drawer>
        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>{content}</Box>
      </Box>
    );
  }

  return (
    <Box sx={{ minHeight: "100dvh", display: "flex", flexDirection: "column", bgcolor: "background.default" }}>
      <AppBar position="sticky" elevation={0} sx={{ bgcolor: "background.paper", borderBottom: "1px solid", borderColor: "divider" }}>
        <Brand />
      </AppBar>
      {content}
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
