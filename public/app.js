const navItems = [...document.querySelectorAll(".nav-item")];
const sidebarToggle = document.querySelector("#sidebarToggle");
const pages = [...document.querySelectorAll("[data-page-panel]")];
const pluginGrid = document.querySelector("#pluginGrid");
const storeGrid = document.querySelector("#storeGrid");
const configPanels = [...document.querySelectorAll("[data-config-panel]")];
const spotifyPanel = document.querySelector("#spotifyPanel");
const matrixPanel = document.querySelector("#matrixPanel");
const clockPanel = document.querySelector("#clockPanel");
const agentPanel = document.querySelector("#agentPanel");
const weatherPanel = document.querySelector("#weatherPanel");
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
  weather: "Weather",
  testPattern: "Test Pattern"
};

let currentConfig = null;
let localWidgets = [];
let storeWidgets = [];
let selectedPlugin = "spotify";
let runtimeRunning = false;
let browserAmericaTimezone = "";

function pluginCards() {
  return [...document.querySelectorAll(".plugin-card[data-plugin]")];
}

function modeFromWidgetId(widgetId) {
  return widgetId?.startsWith("core.") ? widgetId.slice(5) : widgetId;
}

function widgetIdForMode(mode) {
  return mode?.startsWith("core.") ? mode : `core.${mode}`;
}

function widgetCategoryLabel(category) {
  return {
    media: "Music",
    time: "Ambient",
    assistant: "Assistant",
    information: "Info",
    diagnostics: "Diagnostic",
    custom: "Widget"
  }[category] || "Widget";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function previewMarkup(mode) {
  if (mode === "clock") {
    return `
      <span class="plugin-preview preview-clock" aria-hidden="true">
        <span class="plugin-clock-face">
          <span class="plugin-clock-tick tick-12"></span>
          <span class="plugin-clock-tick tick-3"></span>
          <span class="plugin-clock-tick tick-6"></span>
          <span class="plugin-clock-tick tick-9"></span>
          <span class="plugin-clock-hand plugin-hour-hand"></span>
          <span class="plugin-clock-hand plugin-minute-hand"></span>
          <span class="plugin-clock-pin"></span>
        </span>
      </span>`;
  }
  if (mode === "weather") {
    return `
      <span class="plugin-preview preview-weather" aria-hidden="true">
        <span class="weather-sun"></span>
        <span class="weather-face-mini">
          <span class="weather-glasses"></span>
          <span class="weather-smile-mini"></span>
        </span>
      </span>`;
  }
  return `<span class="plugin-preview preview-${mode === "testPattern" ? "test" : mode}" aria-hidden="true"></span>`;
}

function storePreviewClass(widgetId) {
  if (widgetId?.includes("calendar")) {
    return "preview-calendar";
  }
  if (widgetId?.includes("board")) {
    return "preview-board";
  }
  if (widgetId?.includes("music")) {
    return "preview-spotify";
  }
  return "preview-agent";
}

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
  pluginCards().forEach((card) => card.classList.toggle("active", card.dataset.plugin === plugin));
  configPanels.forEach((panel) => panel.classList.toggle("active", panel.dataset.configPanel === plugin));
  dialogTitle.textContent = pluginLabels[plugin] || "Plugin";
}

function syncActiveMode(mode) {
  activeMode.textContent = pluginLabels[mode] || "Spotify";
  matrixPreview.dataset.mode = mode;
  pluginCards().forEach((card) => card.classList.toggle("active", card.dataset.plugin === mode));
}

function renderLocalWidgets(widgets) {
  if (!pluginGrid || !widgets.length) {
    return;
  }
  localWidgets = widgets;
  const cards = widgets.map((widget) => {
    const manifest = widget.manifest || {};
    const mode = modeFromWidgetId(manifest.id);
    pluginLabels[mode] = manifest.name || pluginLabels[mode] || mode;
    const name = escapeHtml(manifest.name || mode);
    const summary = escapeHtml(manifest.summary || "Assistant Matrix widget.");
    const meta = escapeHtml(widgetCategoryLabel(manifest.category));
    const widgetId = escapeHtml(manifest.id || "");
    const escapedMode = escapeHtml(mode);
    return `
      <article class="plugin-card${widget.active ? " active" : ""}" data-plugin="${escapedMode}" data-widget-id="${widgetId}" role="button" tabindex="0">
        <span class="plugin-meta">${meta}</span>
        <strong>${name}</strong>
        <small>${summary}</small>
        ${previewMarkup(mode)}
        <button class="plugin-settings-button" type="button" data-plugin-settings="${escapedMode}">Settings</button>
      </article>`;
  }).join("");
  pluginGrid.innerHTML = cards;
  syncActiveMode(normalizeMode(currentConfig));
}

async function refreshLocalWidgets() {
  try {
    const response = await api("/api/widgets/local");
    renderLocalWidgets(response.widgets || []);
  } catch (error) {
    console.warn("Unable to load local widget registry", error);
  }
}

function renderStoreWidgets(widgets) {
  if (!storeGrid) {
    return;
  }
  storeWidgets = widgets;
  if (!widgets.length) {
    storeGrid.innerHTML = `
      <article class="plugin-card planned" aria-disabled="true">
        <span class="plugin-meta">Empty</span>
        <strong>No widgets found</strong>
        <small>The configured widget store did not return any catalog entries.</small>
        <span class="plugin-preview preview-board" aria-hidden="true"></span>
      </article>`;
    return;
  }
  storeGrid.innerHTML = widgets.map((widget) => {
    const id = escapeHtml(widget.id || "");
    const name = escapeHtml(widget.name || widget.id || "Widget");
    const summary = escapeHtml(widget.summary || "Assistant Matrix store widget.");
    const meta = escapeHtml(widgetCategoryLabel(widget.category));
    const version = escapeHtml(widget.version || "");
    const author = escapeHtml(widget.author || "Assistant Matrix");
    const previewClass = escapeHtml(storePreviewClass(widget.id));
    const installed = Boolean(widget.installed);
    return `
      <article class="plugin-card store-card${installed ? " installed" : ""}" data-store-widget-id="${id}">
        <span class="plugin-meta">${installed ? "Installed" : meta}</span>
        <strong>${name}</strong>
        <small>${summary}</small>
        <span class="plugin-preview ${previewClass}" aria-hidden="true"></span>
        <small>v${version} - ${author}</small>
        <button class="plugin-settings-button" type="button" data-store-install="${id}" ${installed ? "disabled" : ""}>${installed ? "Installed" : "Install"}</button>
      </article>`;
  }).join("");
}

async function refreshStoreWidgets() {
  try {
    const response = await api("/api/widgets/store");
    renderStoreWidgets(response.widgets || []);
  } catch (error) {
    console.warn("Unable to load widget store", error);
    renderStoreWidgets([]);
  }
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
  fillPanel(weatherPanel, {
    weatherLabel: config.weather?.label || "Local weather",
    weatherPostalCode: config.weather?.postalCode || "",
    weatherCountryCode: config.weather?.countryCode || "US",
    weatherLatitude: config.weather?.latitude ?? "",
    weatherLongitude: config.weather?.longitude ?? "",
    weatherTemperatureUnit: config.weather?.temperatureUnit || "fahrenheit",
    weatherFaceAccessory: config.weather?.faceAccessory || "auto",
    weatherRefreshMinutes: config.weather?.refreshMinutes || 15
  });
  fillPanel(advancedPanel, {
    mockOutput: config.runtime?.mockOutput || "",
    testPattern: Boolean(config.runtime?.testPattern)
  });

  syncActiveMode(mode);
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
      rpm: fieldValue(matrixPanel, "rpm"),
      rotation: Number(fieldValue(matrixPanel, "rotation", "0"))
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
    },
    weather: {
      label: fieldValue(weatherPanel, "weatherLabel", "Local weather") || "Local weather",
      postalCode: fieldValue(weatherPanel, "weatherPostalCode", ""),
      countryCode: fieldValue(weatherPanel, "weatherCountryCode", "US"),
      latitude: fieldValue(weatherPanel, "weatherLatitude") === "" ? null : Number(fieldValue(weatherPanel, "weatherLatitude")),
      longitude: fieldValue(weatherPanel, "weatherLongitude") === "" ? null : Number(fieldValue(weatherPanel, "weatherLongitude")),
      temperatureUnit: fieldValue(weatherPanel, "weatherTemperatureUnit", "fahrenheit"),
      faceAccessory: fieldValue(weatherPanel, "weatherFaceAccessory", "auto"),
      refreshMinutes: Number(fieldValue(weatherPanel, "weatherRefreshMinutes", "15") || 15)
    }
  };
}

function collectWidgetConfig(plugin = selectedPlugin) {
  if (plugin === "spotify") {
    return {
      clientId: fieldValue(spotifyPanel, "clientId"),
      clientSecret: fieldValue(spotifyPanel, "clientSecret"),
      redirectUri: fieldValue(spotifyPanel, "redirectUri")
    };
  }
  if (plugin === "clock") {
    return {
      face: fieldValue(clockPanel, "clockFace", "analog") || "analog",
      use24Hour: fieldChecked(clockPanel, "clock24Hour"),
      showSeconds: fieldChecked(clockPanel, "clockShowSeconds"),
      timezone: fieldValue(clockPanel, "clockTimezone") || browserAmericaTimezone
    };
  }
  if (plugin === "agent") {
    return {
      faceStyle: fieldValue(agentPanel, "agentFaceStyle", "classic"),
      animationSpeed: fieldValue(agentPanel, "agentAnimationSpeed", "normal")
    };
  }
  if (plugin === "weather") {
    return {
      label: fieldValue(weatherPanel, "weatherLabel", "Local weather") || "Local weather",
      postalCode: fieldValue(weatherPanel, "weatherPostalCode", ""),
      countryCode: fieldValue(weatherPanel, "weatherCountryCode", "US"),
      latitude: fieldValue(weatherPanel, "weatherLatitude") === "" ? null : Number(fieldValue(weatherPanel, "weatherLatitude")),
      longitude: fieldValue(weatherPanel, "weatherLongitude") === "" ? null : Number(fieldValue(weatherPanel, "weatherLongitude")),
      temperatureUnit: fieldValue(weatherPanel, "weatherTemperatureUnit", "fahrenheit"),
      faceAccessory: fieldValue(weatherPanel, "weatherFaceAccessory", "auto"),
      refreshMinutes: Number(fieldValue(weatherPanel, "weatherRefreshMinutes", "15") || 15)
    };
  }
  if (plugin === "testPattern") {
    return {
      testPattern: true
    };
  }
  return {};
}

async function saveConfig(modeOverride = null) {
  const saved = await api("/api/config", {
    method: "POST",
    body: JSON.stringify(collectConfig(modeOverride))
  });
  fillForms(saved);
  return saved;
}

async function saveWidgetConfig(plugin = selectedPlugin) {
  const widgetId = widgetIdForMode(plugin);
  const response = await api(`/api/widgets/local/${encodeURIComponent(widgetId)}/config`, {
    method: "POST",
    body: JSON.stringify({ config: collectWidgetConfig(plugin) })
  });
  await refreshConfig();
  await refreshLocalWidgets();
  return response;
}

async function applyPlugin(plugin = selectedPlugin) {
  applyButton.disabled = true;
  applyPluginButton.disabled = true;
  applyButton.textContent = "Applying...";
  try {
    const widgetId = widgetIdForMode(plugin);
    await api(`/api/widgets/local/${encodeURIComponent(widgetId)}/apply`, {
      method: "POST",
      body: JSON.stringify({ config: collectWidgetConfig(plugin) })
    });
    await refreshConfig();
    await refreshLocalWidgets();
    syncActiveMode(plugin);
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

pluginGrid?.addEventListener("click", (event) => {
  const settingsButton = event.target.closest("[data-plugin-settings]");
  if (settingsButton) {
    event.stopPropagation();
    const plugin = settingsButton.dataset.pluginSettings;
    setSelectedPlugin(plugin);
    pluginDialog.showModal();
    return;
  }
  const card = event.target.closest(".plugin-card[data-plugin]");
  if (card) {
    applyPlugin(card.dataset.plugin);
  }
});

pluginGrid?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") {
    return;
  }
  const card = event.target.closest(".plugin-card[data-plugin]");
  if (!card) {
    return;
  }
  event.preventDefault();
  applyPlugin(card.dataset.plugin);
});

storeGrid?.addEventListener("click", async (event) => {
  const installButton = event.target.closest("[data-store-install]");
  if (!installButton || installButton.disabled) {
    return;
  }
  installButton.disabled = true;
  installButton.textContent = "Installing...";
  try {
    await api("/api/widgets/install", {
      method: "POST",
      body: JSON.stringify({ widgetId: installButton.dataset.storeInstall })
    });
    await refreshLocalWidgets();
    await refreshStoreWidgets();
    setMessage("Widget installed locally.");
  } catch (error) {
    installButton.disabled = false;
    installButton.textContent = "Install";
    setMessage(error.message);
  }
});

closeDialogButton?.addEventListener("click", () => pluginDialog.close());
savePluginButton?.addEventListener("click", async () => {
  await saveWidgetConfig(selectedPlugin);
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
  displayPowerButton.disabled = true;
  try {
    const path = runtimeRunning ? "/api/runtime/stop" : "/api/runtime/apply";
    await api(path, { method: "POST", body: "{}" });
    await refreshStatus();
  } catch (error) {
    setMessage(error.message);
    await refreshStatus().catch(() => undefined);
  } finally {
    displayPowerButton.disabled = false;
  }
});

fields(clockPanel, "clockFace").forEach((control) => {
  control.addEventListener("change", () => {
    if (control.checked) {
      selectedPlugin = "clock";
    }
  });
});

populateTimezones();

refreshConfig()
  .then(refreshLocalWidgets)
  .then(refreshStoreWidgets)
  .then(refreshStatus)
  .catch((error) => setMessage(error.message));

setInterval(refreshStatus, 5000);
