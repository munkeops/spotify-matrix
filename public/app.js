const navItems = [...document.querySelectorAll(".nav-item")];
const sidebarToggle = document.querySelector("#sidebarToggle");
const pages = [...document.querySelectorAll("[data-page-panel]")];
const pluginCards = [...document.querySelectorAll(".plugin-card[data-plugin]")];
const configPanels = [...document.querySelectorAll("[data-config-panel]")];
const spotifyPanel = document.querySelector("#spotifyPanel");
const matrixPanel = document.querySelector("#matrixPanel");
const clockPanel = document.querySelector("#clockPanel");
const agentPanel = document.querySelector("#agentPanel");
const advancedPanel = document.querySelector("#advancedPanel");
const pluginDialog = document.querySelector("#pluginDialog");
const closeDialogButton = document.querySelector("#closeDialogButton");
const savePluginButton = document.querySelector("#savePluginButton");
const applyPluginButton = document.querySelector("#applyPluginButton");
const pairButton = document.querySelector("#pairButton");
const directAuthButton = document.querySelector("#directAuthButton");
const pairCommand = document.querySelector("#pairCommand");
const applyButton = document.querySelector("#applyButton");
const editActivePluginButton = document.querySelector("#editActivePluginButton");
const displayPowerButton = document.querySelector("#displayPowerButton");
const statusDot = document.querySelector("#statusDot");
const statusTitle = document.querySelector("#statusTitle");
const statusText = document.querySelector("#statusText");
const tokenState = document.querySelector("#tokenState");
const dataDir = document.querySelector("#dataDir");
const processState = document.querySelector("#processState");
const activeMode = document.querySelector("#activeMode");
const matrixPreview = document.querySelector("#matrixPreview");
const dialogTitle = document.querySelector("#dialogTitle");
const clockTimezoneSelect = document.querySelector("#clockTimezoneSelect");

const fallbackAmericaTimezones = [
  "America/Adak",
  "America/Anchorage",
  "America/Anguilla",
  "America/Antigua",
  "America/Araguaina",
  "America/Argentina/Buenos_Aires",
  "America/Argentina/Catamarca",
  "America/Argentina/Cordoba",
  "America/Argentina/Jujuy",
  "America/Argentina/La_Rioja",
  "America/Argentina/Mendoza",
  "America/Argentina/Rio_Gallegos",
  "America/Argentina/Salta",
  "America/Argentina/San_Juan",
  "America/Argentina/San_Luis",
  "America/Argentina/Tucuman",
  "America/Argentina/Ushuaia",
  "America/Aruba",
  "America/Asuncion",
  "America/Atikokan",
  "America/Bahia",
  "America/Bahia_Banderas",
  "America/Barbados",
  "America/Belem",
  "America/Belize",
  "America/Blanc-Sablon",
  "America/Boa_Vista",
  "America/Bogota",
  "America/Boise",
  "America/Cambridge_Bay",
  "America/Campo_Grande",
  "America/Cancun",
  "America/Caracas",
  "America/Cayenne",
  "America/Cayman",
  "America/Chicago",
  "America/Chihuahua",
  "America/Ciudad_Juarez",
  "America/Costa_Rica",
  "America/Creston",
  "America/Cuiaba",
  "America/Curacao",
  "America/Danmarkshavn",
  "America/Dawson",
  "America/Dawson_Creek",
  "America/Denver",
  "America/Detroit",
  "America/Dominica",
  "America/Edmonton",
  "America/Eirunepe",
  "America/El_Salvador",
  "America/Fort_Nelson",
  "America/Fortaleza",
  "America/Glace_Bay",
  "America/Goose_Bay",
  "America/Grand_Turk",
  "America/Grenada",
  "America/Guadeloupe",
  "America/Guatemala",
  "America/Guayaquil",
  "America/Guyana",
  "America/Halifax",
  "America/Havana",
  "America/Hermosillo",
  "America/Indiana/Indianapolis",
  "America/Indiana/Knox",
  "America/Indiana/Marengo",
  "America/Indiana/Petersburg",
  "America/Indiana/Tell_City",
  "America/Indiana/Vevay",
  "America/Indiana/Vincennes",
  "America/Indiana/Winamac",
  "America/Inuvik",
  "America/Iqaluit",
  "America/Jamaica",
  "America/Juneau",
  "America/Kentucky/Louisville",
  "America/Kentucky/Monticello",
  "America/Kralendijk",
  "America/La_Paz",
  "America/Lima",
  "America/Los_Angeles",
  "America/Lower_Princes",
  "America/Maceio",
  "America/Managua",
  "America/Manaus",
  "America/Marigot",
  "America/Martinique",
  "America/Matamoros",
  "America/Mazatlan",
  "America/Menominee",
  "America/Merida",
  "America/Metlakatla",
  "America/Mexico_City",
  "America/Miquelon",
  "America/Moncton",
  "America/Monterrey",
  "America/Montevideo",
  "America/Montserrat",
  "America/Nassau",
  "America/New_York",
  "America/Nome",
  "America/Noronha",
  "America/North_Dakota/Beulah",
  "America/North_Dakota/Center",
  "America/North_Dakota/New_Salem",
  "America/Nuuk",
  "America/Ojinaga",
  "America/Panama",
  "America/Paramaribo",
  "America/Phoenix",
  "America/Port-au-Prince",
  "America/Port_of_Spain",
  "America/Porto_Velho",
  "America/Puerto_Rico",
  "America/Punta_Arenas",
  "America/Rankin_Inlet",
  "America/Recife",
  "America/Regina",
  "America/Resolute",
  "America/Rio_Branco",
  "America/Santarem",
  "America/Santiago",
  "America/Santo_Domingo",
  "America/Sao_Paulo",
  "America/Scoresbysund",
  "America/Sitka",
  "America/St_Barthelemy",
  "America/St_Johns",
  "America/St_Kitts",
  "America/St_Lucia",
  "America/St_Thomas",
  "America/St_Vincent",
  "America/Swift_Current",
  "America/Tegucigalpa",
  "America/Thule",
  "America/Tijuana",
  "America/Toronto",
  "America/Tortola",
  "America/Vancouver",
  "America/Whitehorse",
  "America/Winnipeg",
  "America/Yakutat"
];

const pluginLabels = {
  spotify: "Spotify",
  clock: "Clock",
  agent: "Agent Face",
  testPattern: "Test Pattern"
};

let currentConfig = null;
let selectedPlugin = "spotify";
let runtimeRunning = false;
let browserAmericaTimezone = "";

function populateTimezones() {
  if (!clockTimezoneSelect) {
    return;
  }
  const localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  const browserZones = typeof Intl.supportedValuesOf === "function"
    ? Intl.supportedValuesOf("timeZone").filter((zone) => zone.startsWith("America/"))
    : [];
  const zones = [...new Set(browserZones.length ? browserZones : fallbackAmericaTimezones)].sort();
  browserAmericaTimezone = localTimezone.startsWith("America/") ? localTimezone : "America/Chicago";
  for (const zone of zones) {
    const option = document.createElement("option");
    option.value = zone;
    option.textContent = zone.replace("America/", "").replaceAll("_", " ");
    clockTimezoneSelect.appendChild(option);
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || payload.detail || payload.message || "Request failed");
  }
  return payload;
}

function fields(container, name) {
  if (!container) {
    return [];
  }
  const element = container.elements?.[name];
  if (element) {
    if (element instanceof RadioNodeList) {
      return [...element];
    }
    return [element];
  }
  return [...container.querySelectorAll(`[name="${name}"]`)];
}

function field(container, name) {
  return fields(container, name)[0];
}

function fieldValue(container, name, fallback = "") {
  const controls = fields(container, name);
  if (!controls.length) {
    return fallback;
  }
  const checked = controls.find((control) => control.type === "radio" && control.checked);
  return (checked || controls[0]).value ?? fallback;
}

function fieldChecked(container, name) {
  return Boolean(field(container, name)?.checked);
}

function setMessage(message) {
  if (pairCommand) {
    pairCommand.textContent = message;
  }
  if (statusText) {
    statusText.textContent = message;
  }
}

function normalizeMode(config) {
  if (config?.runtime?.testPattern) {
    return "testPattern";
  }
  return config?.display?.mode || "spotify";
}

function setPage(pageName) {
  navItems.forEach((item) => item.classList.toggle("active", item.dataset.page === pageName));
  pages.forEach((page) => page.classList.toggle("active", page.dataset.pagePanel === pageName));
}

function setSelectedPlugin(plugin) {
  selectedPlugin = plugin;
  pluginCards.forEach((card) => card.classList.toggle("active", card.dataset.plugin === plugin));
  configPanels.forEach((panel) => panel.classList.toggle("active", panel.dataset.configPanel === plugin));
  dialogTitle.textContent = pluginLabels[plugin] || "Plugin";
}

function fillPanel(form, values) {
  for (const [key, value] of Object.entries(values || {})) {
    const control = field(form, key);
    if (!control) {
      continue;
    }
    const controls = fields(form, key);
    if (controls.length > 1 && controls.every((candidate) => candidate.type === "radio")) {
      controls.forEach((candidate) => {
        candidate.checked = candidate.value === value;
      });
    } else if (control.type === "checkbox") {
      control.checked = Boolean(value);
    } else {
      control.value = value ?? "";
    }
  }
}

function fillForms(config) {
  currentConfig = config;
  const mode = normalizeMode(config);
  selectedPlugin = mode;

  fillPanel(spotifyPanel, {
    clientId: config.spotify.clientId || "",
    clientSecret: config.spotify.clientSecret || "",
    redirectUri: config.spotify.redirectUri || "http://127.0.0.1:8888/callback"
  });
  fillPanel(matrixPanel, config.matrix);
  fillPanel(clockPanel, {
    clockFace: config.clock?.face || "analog",
    clockTimezone: config.clock?.timezone || browserAmericaTimezone,
    clock24Hour: Boolean(config.clock?.use24Hour),
    clockShowSeconds: Boolean(config.clock?.showSeconds)
  });
  fillPanel(agentPanel, {
    agentFaceStyle: config.agent?.faceStyle || "classic",
    agentAnimationSpeed: config.agent?.animationSpeed || "normal"
  });
  fillPanel(advancedPanel, {
    mockOutput: config.runtime?.mockOutput || "",
    testPattern: Boolean(config.runtime?.testPattern)
  });

  activeMode.textContent = pluginLabels[mode] || "Spotify";
  matrixPreview.dataset.mode = mode;
  setSelectedPlugin(mode);
}

function collectConfig(modeOverride = null) {
  const mode = modeOverride || selectedPlugin || normalizeMode(currentConfig);
  return {
    spotify: {
      clientId: fieldValue(spotifyPanel, "clientId"),
      clientSecret: fieldValue(spotifyPanel, "clientSecret"),
      redirectUri: fieldValue(spotifyPanel, "redirectUri")
    },
    matrix: {
      rows: fieldValue(matrixPanel, "rows"),
      cols: fieldValue(matrixPanel, "cols"),
      chainLength: fieldValue(matrixPanel, "chainLength"),
      parallel: fieldValue(matrixPanel, "parallel"),
      brightness: fieldValue(matrixPanel, "brightness"),
      gpioSlowdown: fieldValue(matrixPanel, "gpioSlowdown"),
      hardwareMapping: fieldValue(matrixPanel, "hardwareMapping"),
      pwmBits: fieldValue(matrixPanel, "pwmBits"),
      limitRefreshRateHz: fieldValue(matrixPanel, "limitRefreshRateHz"),
      noHardwarePulse: fieldChecked(matrixPanel, "noHardwarePulse"),
      pollSeconds: fieldValue(matrixPanel, "pollSeconds"),
      fps: fieldValue(matrixPanel, "fps"),
      rpm: fieldValue(matrixPanel, "rpm")
    },
    runtime: {
      mockOutput: fieldValue(advancedPanel, "mockOutput"),
      testPattern: mode === "testPattern"
    },
    display: { mode },
    clock: {
      face: fieldValue(clockPanel, "clockFace", "analog") || "analog",
      use24Hour: fieldChecked(clockPanel, "clock24Hour"),
      showSeconds: fieldChecked(clockPanel, "clockShowSeconds"),
      timezone: fieldValue(clockPanel, "clockTimezone") || browserAmericaTimezone
    },
    agent: {
      faceStyle: fieldValue(agentPanel, "agentFaceStyle", "classic"),
      animationSpeed: fieldValue(agentPanel, "agentAnimationSpeed", "normal")
    }
  };
}

async function saveConfig(modeOverride = null) {
  const saved = await api("/api/config", {
    method: "POST",
    body: JSON.stringify(collectConfig(modeOverride))
  });
  fillForms(saved);
  return saved;
}

async function applyPlugin(plugin = selectedPlugin) {
  applyButton.disabled = true;
  applyPluginButton.disabled = true;
  applyButton.textContent = "Applying...";
  try {
    await saveConfig(plugin);
    await api("/api/runtime/apply", { method: "POST", body: "{}" });
    if (pluginDialog.open) {
      pluginDialog.close();
    }
    await refreshStatus();
  } catch (error) {
    setMessage(error.message);
  } finally {
    applyButton.disabled = false;
    applyPluginButton.disabled = false;
    applyButton.textContent = "Apply";
  }
}

async function refreshConfig() {
  fillForms(await api("/api/config"));
}

async function refreshStatus() {
  const status = await api("/api/status");
  const mode = normalizeMode(currentConfig);
  const running = status.runtime.running;
  runtimeRunning = running;

  statusDot.className = `status-dot ${status.configured ? "ok" : "bad"}`;
  statusTitle.textContent = running ? `${pluginLabels[mode]} running` : status.configured ? `${pluginLabels[mode]} ready` : "Setup needed";
  statusText.textContent = status.configured ? "Ready to apply plugins." : `Missing: ${status.missing.join(", ")}`;
  if (tokenState) {
    tokenState.textContent = status.token.present ? `Saved${status.token.hasRefreshToken ? " with refresh token" : ""}` : "Not paired";
  }
  if (dataDir) {
    dataDir.textContent = status.dataDir;
  }
  processState.textContent = running
    ? `Running on the LED matrix`
    : status.runtime.lastExit
      ? `Stopped at ${status.runtime.lastExit.at}`
      : "Stopped";
  displayPowerButton.classList.toggle("is-on", running);
  displayPowerButton.setAttribute("aria-pressed", String(running));
}

navItems.forEach((item) => item.addEventListener("click", () => setPage(item.dataset.page)));

sidebarToggle?.addEventListener("click", () => {
  const collapsed = document.body.classList.toggle("sidebar-collapsed");
  sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
  sidebarToggle.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
});

pluginCards.forEach((card) => {
  card.addEventListener("click", () => {
    const plugin = card.dataset.plugin;
    setSelectedPlugin(plugin);
    pluginDialog.showModal();
  });
});

closeDialogButton?.addEventListener("click", () => pluginDialog.close());
savePluginButton?.addEventListener("click", async () => {
  await saveConfig(selectedPlugin);
  pluginDialog.close();
  await refreshStatus();
});
applyPluginButton?.addEventListener("click", () => applyPlugin(selectedPlugin));
applyButton?.addEventListener("click", () => applyPlugin(normalizeMode(currentConfig)));
editActivePluginButton?.addEventListener("click", () => {
  setSelectedPlugin(normalizeMode(currentConfig));
  pluginDialog.showModal();
});

spotifyPanel?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await saveConfig();
  setMessage("Spotify settings saved.");
  await refreshStatus();
});

matrixPanel?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await saveConfig();
  setMessage("Matrix settings saved.");
  await refreshStatus();
});

pairButton?.addEventListener("click", async () => {
  await saveConfig();
  const session = await api("/api/auth/session", { method: "POST", body: "{}" });
  const origin = window.location.origin;
  setMessage(session.command.replace(`http://<pi-host>:${window.location.port || 3000}`, origin));
});

directAuthButton?.addEventListener("click", async () => {
  await saveConfig();
  window.location.href = "/api/auth/login";
});

displayPowerButton?.addEventListener("click", async () => {
  const path = runtimeRunning ? "/api/runtime/stop" : "/api/runtime/start";
  await api(path, { method: "POST", body: "{}" });
  await refreshStatus();
});

populateTimezones();

refreshConfig()
  .then(refreshStatus)
  .catch((error) => setMessage(error.message));

setInterval(refreshStatus, 5000);
