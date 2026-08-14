const navItems = [...document.querySelectorAll(".nav-item")];
const sidebarToggle = document.querySelector("#sidebarToggle");
const pages = [...document.querySelectorAll("[data-page-panel]")];
const pluginGrid = document.querySelector("#pluginGrid");
const storeGrid = document.querySelector("#storeGrid");
const configPanels = [...document.querySelectorAll("[data-config-panel]")];
const spotifyPanel = document.querySelector("#spotifyPanel");
const matrixPanel = document.querySelector("#matrixPanel");
const storeSettingsPanel = document.querySelector("#storeSettingsPanel");
const clockPanel = document.querySelector("#clockPanel");
const agentPanel = document.querySelector("#agentPanel");
const weatherPanel = document.querySelector("#weatherPanel");
const textPanel = document.querySelector("#textPanel");
const imagePanel = document.querySelector("#imagePanel");
const imageFileInput = document.querySelector("#imageFileInput");
const imagePreviewImg = document.querySelector("#imagePreviewImg");
const imagePreviewEmpty = document.querySelector("#imagePreviewEmpty");
const drawPanel = document.querySelector("#drawPanel");
const drawShapeList = document.querySelector("#drawShapeList");
const addShapeButton = document.querySelector("#addShapeButton");
const imageGallery = document.querySelector("#imageGallery");
const slideshowPanel = document.querySelector("#slideshowPanel");
const slideshowGallery = document.querySelector("#slideshowGallery");
const widgetLivePreview = document.querySelector("#widgetLivePreview");
const widgetPreviewImg = document.querySelector("#widgetPreviewImg");
const bluetoothPanel = document.querySelector("#bluetoothPanel");
const bluetoothStatus = document.querySelector("#bluetoothStatus");
const bluetoothScanButton = document.querySelector("#bluetoothScanButton");
const bluetoothDeviceList = document.querySelector("#bluetoothDeviceList");
const advancedPanel = document.querySelector("#advancedPanel");
const externalWidgetPanel = document.querySelector("#externalWidgetPanel");
const externalWidgetFields = document.querySelector("#externalWidgetFields");
const pluginDialog = document.querySelector("#pluginDialog");
const closeDialogButton = document.querySelector("#closeDialogButton");
const savePluginButton = document.querySelector("#savePluginButton");
const applyPluginButton = document.querySelector("#applyPluginButton");
const policyModeSelect = document.querySelector("#policyModeSelect");
const policyActiveWidgetSelect = document.querySelector("#policyActiveWidgetSelect");
const rotationList = document.querySelector("#rotationList");
const triggerList = document.querySelector("#triggerList");
const savePolicyButton = document.querySelector("#savePolicyButton");
const applyPolicyButton = document.querySelector("#applyPolicyButton");
const addTriggerButton = document.querySelector("#addTriggerButton");
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
  text: "Custom Message",
  image: "Image",
  draw: "Draw",
  slideshow: "Slideshow",
  testPattern: "Test Pattern"
};

let currentConfig = null;
let localWidgets = [];
let storeWidgets = [];
let displayPolicy = null;
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
  return mode?.startsWith("core.") || mode?.includes(".") ? mode : `core.${mode}`;
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
      <span class="plugin-preview preview-weather weather-metric-preview" aria-hidden="true">
        <span><strong>TEMP</strong><em>72F</em></span>
        <span><strong>UV</strong><em>4</em></span>
        <span><strong>AQI</strong><em>38</em></span>
        <span><strong>WIND</strong><em>8</em></span>
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

function previewMediaMarkup({ url = "", fallbackClass = "preview-agent", alt = "Widget preview" } = {}) {
  if (url) {
    return `
      <span class="plugin-preview media-preview">
        <img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}" loading="lazy" decoding="async">
      </span>`;
  }
  return `<span class="plugin-preview ${escapeHtml(fallbackClass)}" aria-hidden="true"></span>`;
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
  if (config?.display?.mode === "widget") {
    return config?.display?.widgetId || "widget";
  }
  return config?.display?.mode || "spotify";
}

function selectedLocalWidget(plugin = selectedPlugin) {
  const widgetId = widgetIdForMode(plugin);
  return localWidgets.find((widget) => widget.manifest?.id === widgetId) || null;
}

function renderExternalWidgetConfig(plugin = selectedPlugin, savedConfig = {}) {
  if (!externalWidgetFields) {
    return;
  }
  const widget = selectedLocalWidget(plugin);
  const fields = widget?.manifest?.config || [];
  if (!fields.length) {
    externalWidgetFields.innerHTML = `<p class="muted">This widget does not expose configurable fields.</p>`;
    return;
  }
  externalWidgetFields.innerHTML = fields.map((field) => {
    const key = escapeHtml(field.key);
    const label = escapeHtml(field.label || field.key);
    const value = savedConfig[field.key] ?? field.default ?? "";
    const help = field.helpText ? `<small>${escapeHtml(field.helpText)}</small>` : "";
    if (field.type === "boolean") {
      return `<label class="check-row"><input name="${key}" type="checkbox" ${value ? "checked" : ""}><span>${label}</span></label>${help}`;
    }
    if (field.type === "select") {
      const options = (field.options || []).map((option) => {
        const optionValue = option.value ?? option;
        const optionLabel = option.label ?? optionValue;
        return `<option value="${escapeHtml(optionValue)}" ${String(optionValue) === String(value) ? "selected" : ""}>${escapeHtml(optionLabel)}</option>`;
      }).join("");
      return `<label>${label}<select name="${key}">${options}</select></label>${help}`;
    }
    const inputType = field.type === "number" ? "number" : field.type === "secret" ? "password" : "text";
    const placeholder = field.placeholder ? ` placeholder="${escapeHtml(field.placeholder)}"` : "";
    return `<label>${label}<input name="${key}" type="${inputType}" value="${escapeHtml(value)}"${placeholder}></label>${help}`;
  }).join("");
}

function setPage(pageName) {
  navItems.forEach((item) => item.classList.toggle("active", item.dataset.page === pageName));
  pages.forEach((page) => page.classList.toggle("active", page.dataset.pagePanel === pageName));
}

function setSelectedPlugin(plugin) {
  selectedPlugin = plugin;
  pluginCards().forEach((card) => card.classList.toggle("active", card.dataset.plugin === plugin));
  const panelName = plugin?.includes(".") && !plugin?.startsWith("core.") ? "external" : plugin;
  configPanels.forEach((panel) => panel.classList.toggle("active", panel.dataset.configPanel === panelName));
  dialogTitle.textContent = pluginLabels[plugin] || "Plugin";
  if (panelName === "external") {
    renderExternalWidgetConfig(plugin);
  }
  updateWidgetPreview();
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
    const previewUrl = manifest.preview?.cardGif || manifest.preview?.matrixPreview || "";
    const preview = manifest.id?.startsWith("core.") ? previewMarkup(mode) : previewMediaMarkup({ url: previewUrl, fallbackClass: storePreviewClass(manifest.id), alt: `${manifest.name || "Widget"} preview` });
    return `
      <article class="plugin-card${widget.active ? " active" : ""}" data-plugin="${escapedMode}" data-widget-id="${widgetId}" role="button" tabindex="0">
        <span class="plugin-meta">${meta}</span>
        <strong>${name}</strong>
        <small>${summary}</small>
        ${preview}
        <button class="plugin-settings-button" type="button" data-plugin-settings="${escapedMode}">Settings</button>
        ${widget.builtIn ? "" : `<button class="plugin-settings-button danger" type="button" data-widget-uninstall="${widgetId}">Uninstall</button>`}
      </article>`;
  }).join("");
  const studioCard = `
      <a class="plugin-card studio-card" href="/studio/">
        <span class="plugin-meta">Create</span>
        <strong>Meme Studio</strong>
        <small>Draw, add text, and store memes. Tap to open the editor.</small>
        <span class="plugin-preview preview-text" aria-hidden="true"></span>
      </a>`;
  pluginGrid.innerHTML = cards + studioCard;
  syncActiveMode(normalizeMode(currentConfig));
  if (displayPolicy) {
    renderDisplayPolicy(displayPolicy);
  }
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
    const previewUrl = widget.previewGifUrl || widget.matrixPreviewUrl || "";
    const installed = Boolean(widget.installed);
    return `
      <article class="plugin-card store-card${installed ? " installed" : ""}" data-store-widget-id="${id}">
        <span class="plugin-meta">${installed ? "Installed" : meta}</span>
        <strong>${name}</strong>
        <small>${summary}</small>
        ${previewMediaMarkup({ url: previewUrl, fallbackClass: storePreviewClass(widget.id), alt: `${widget.name || "Widget"} preview` })}
        <small>v${version} - ${author}</small>
        <button class="plugin-settings-button" type="button" data-store-install="${id}">${installed ? "Update" : "Install"}</button>
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

function renderDisplayPolicy(policy) {
  if (!policyModeSelect || !policyActiveWidgetSelect || !rotationList || !triggerList) {
    return;
  }
  displayPolicy = policy;
  policyModeSelect.value = policy.mode || "single";
  policyActiveWidgetSelect.innerHTML = localWidgets.map((widget) => {
    const id = escapeHtml(widget.manifest.id);
    const name = escapeHtml(widget.manifest.name);
    return `<option value="${id}">${name}</option>`;
  }).join("");
  policyActiveWidgetSelect.value = policy.activeWidgetId || "core.spotify";

  const rotationById = new Map((policy.rotation || []).map((item) => [item.widgetId, item]));
  rotationList.innerHTML = localWidgets.map((widget) => {
    const id = widget.manifest.id;
    const item = rotationById.get(id);
    const enabled = item?.enabled ?? false;
    const duration = item?.durationSeconds ?? 60;
    return `
      <div class="rotation-row" data-rotation-widget-id="${escapeHtml(id)}">
        <label class="check-row">
          <input type="checkbox" name="rotationEnabled" ${enabled ? "checked" : ""}>
          <span>${escapeHtml(widget.manifest.name)}</span>
        </label>
        <label>
          Seconds
          <input name="rotationDuration" type="number" min="5" max="86400" step="5" value="${escapeHtml(duration)}">
        </label>
      </div>`;
  }).join("");

  const widgetOptions = localWidgets.map((widget) => {
    const id = escapeHtml(widget.manifest.id);
    const name = escapeHtml(widget.manifest.name);
    return { id, name };
  });
  triggerList.innerHTML = (policy.triggers || []).map((rule, index) => triggerRowMarkup(rule, index, widgetOptions)).join("") || `<p class="muted">No trigger rules configured.</p>`;
}

function triggerRowMarkup(rule, index, widgetOptions = null) {
  const optionsSource = widgetOptions || localWidgets.map((widget) => ({
    id: escapeHtml(widget.manifest.id),
    name: escapeHtml(widget.manifest.name)
  }));
  const selectedWidget = rule.widgetId || "core.spotify";
  const options = optionsSource.map((option) => `<option value="${option.id}" ${option.id === selectedWidget ? "selected" : ""}>${option.name}</option>`).join("");
  return `
    <div class="trigger-row" data-trigger-index="${index}">
      <label class="check-row">
        <input type="checkbox" name="triggerEnabled" ${rule.enabled ? "checked" : ""}>
        <span>Enabled</span>
      </label>
      <label>
        Event
        <input name="triggerEvent" value="${escapeHtml(rule.event || "")}" placeholder="spotify.playback_started">
      </label>
      <label>
        Widget
        <select name="triggerWidgetId">${options}</select>
      </label>
      <label>
        Priority
        <input name="triggerPriority" type="number" step="1" value="${escapeHtml(rule.priority ?? 0)}">
      </label>
      <label>
        Hold seconds
        <input name="triggerMinDuration" type="number" min="0" max="86400" step="5" value="${escapeHtml(rule.minDurationSeconds ?? 15)}">
      </label>
      <button type="button" class="icon-danger" data-remove-trigger aria-label="Remove trigger">Remove</button>
    </div>`;
}

function addTriggerRule() {
  if (!triggerList) {
    return;
  }
  const existingRows = [...triggerList.querySelectorAll(".trigger-row")];
  if (!existingRows.length) {
    triggerList.innerHTML = "";
  }
  const index = existingRows.length;
  triggerList.insertAdjacentHTML("beforeend", triggerRowMarkup({
    event: "spotify.playback_started",
    widgetId: "core.spotify",
    enabled: true,
    priority: 50,
    minDurationSeconds: 15
  }, index));
}

function collectDisplayPolicy() {
  const rotation = [...document.querySelectorAll(".rotation-row")].map((row) => ({
    widgetId: row.dataset.rotationWidgetId,
    enabled: Boolean(row.querySelector("[name='rotationEnabled']")?.checked),
    durationSeconds: Number(row.querySelector("[name='rotationDuration']")?.value || 60)
  }));
  const triggers = [...document.querySelectorAll(".trigger-row")].map((row) => ({
    event: row.querySelector("[name='triggerEvent']")?.value || "",
    widgetId: row.querySelector("[name='triggerWidgetId']")?.value || "core.spotify",
    enabled: Boolean(row.querySelector("[name='triggerEnabled']")?.checked),
    priority: Number(row.querySelector("[name='triggerPriority']")?.value || 0),
    minDurationSeconds: Number(row.querySelector("[name='triggerMinDuration']")?.value || 0)
  })).filter((rule) => rule.event);
  return {
    mode: policyModeSelect?.value || "single",
    activeWidgetId: policyActiveWidgetSelect?.value || "core.spotify",
    rotation,
    triggers
  };
}

async function refreshDisplayPolicy() {
  try {
    const response = await api("/api/display/policy");
    renderDisplayPolicy(response.policy);
  } catch (error) {
    console.warn("Unable to load display policy", error);
  }
}

async function saveDisplayPolicy() {
  const response = await api("/api/display/policy", {
    method: "POST",
    body: JSON.stringify({ policy: collectDisplayPolicy() })
  });
  renderDisplayPolicy(response.policy);
  setMessage("Display policy saved.");
}

async function applyDisplayPolicy() {
  await saveDisplayPolicy();
  const response = await api("/api/display/policy/apply", { method: "POST", body: "{}" });
  if (response.state?.schedulerRunning) {
    setMessage("Display rotation started.");
  } else {
    setMessage("Display policy applied.");
  }
  await refreshConfig();
  await refreshLocalWidgets();
  await refreshStatus();
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

function setImagePreview(url) {
  if (!imagePreviewImg || !imagePreviewEmpty) {
    return;
  }
  if (url) {
    imagePreviewImg.src = url;
    imagePreviewImg.hidden = false;
    imagePreviewEmpty.hidden = true;
  } else {
    imagePreviewImg.removeAttribute("src");
    imagePreviewImg.hidden = true;
    imagePreviewEmpty.hidden = false;
  }
}

const PREVIEW_WIDGETS = new Set(["text", "image", "draw", "slideshow"]);
let previewTimer = null;

async function updateWidgetPreview() {
  if (!widgetLivePreview || !widgetPreviewImg) {
    return;
  }
  if (!PREVIEW_WIDGETS.has(selectedPlugin)) {
    widgetLivePreview.hidden = true;
    return;
  }
  widgetLivePreview.hidden = false;
  const plugin = selectedPlugin;
  try {
    const response = await api("/api/widgets/preview", {
      method: "POST",
      body: JSON.stringify({ widgetId: widgetIdForMode(plugin), config: collectWidgetConfig(plugin) })
    });
    if (selectedPlugin === plugin) {
      widgetPreviewImg.src = response.dataUrl;
    }
  } catch (error) {
    setMessage(error.message);
  }
}

function scheduleWidgetPreview() {
  if (!PREVIEW_WIDGETS.has(selectedPlugin)) {
    return;
  }
  if (previewTimer) {
    clearTimeout(previewTimer);
  }
  previewTimer = setTimeout(updateWidgetPreview, 250);
}

let galleryAssets = [];
let slideshowItems = [];

function galleryThumb(asset, badge) {
  const name = escapeHtml(asset.name);
  const badgeMarkup = badge ? `<span class="thumb-badge">${escapeHtml(badge)}</span>` : "";
  const gif = asset.animated ? `<span class="thumb-gif">GIF</span>` : "";
  return `
    <div class="asset-thumb" data-asset="${name}">
      <img src="${escapeHtml(asset.url)}" alt="${name}" loading="lazy">
      ${badgeMarkup}${gif}
      <button type="button" class="thumb-delete" data-delete-asset="${name}" aria-label="Delete">×</button>
    </div>`;
}

function renderImageGallery() {
  if (!imageGallery) {
    return;
  }
  if (!galleryAssets.length) {
    imageGallery.innerHTML = `<p class="muted">No saved images yet. Upload one or make a meme in the Studio.</p>`;
    return;
  }
  const current = fieldValue(imagePanel, "assetPath", "");
  imageGallery.innerHTML = galleryAssets.map((asset) => galleryThumb(asset).replace("asset-thumb", asset.name === current ? "asset-thumb selected" : "asset-thumb")).join("");
}

function renderSlideshowGallery() {
  if (!slideshowGallery) {
    return;
  }
  if (!galleryAssets.length) {
    slideshowGallery.innerHTML = `<p class="muted">No saved images yet. Upload some or make memes in the Studio.</p>`;
    return;
  }
  slideshowGallery.innerHTML = galleryAssets.map((asset) => {
    const order = slideshowItems.indexOf(asset.name);
    const html = galleryThumb(asset, order >= 0 ? String(order + 1) : "");
    return order >= 0 ? html.replace("asset-thumb", "asset-thumb selected") : html;
  }).join("");
}

async function loadGallery() {
  try {
    const response = await api("/api/assets");
    galleryAssets = response.assets || [];
  } catch (error) {
    galleryAssets = [];
  }
  renderImageGallery();
  renderSlideshowGallery();
}

async function deleteAsset(name) {
  try {
    await api(`/api/assets/${encodeURIComponent(name)}`, { method: "DELETE" });
    slideshowItems = slideshowItems.filter((item) => item !== name);
    await loadGallery();
    scheduleWidgetPreview();
  } catch (error) {
    setMessage(error.message);
  }
}

imageGallery?.addEventListener("click", (event) => {
  const del = event.target.closest("[data-delete-asset]");
  if (del) {
    deleteAsset(del.dataset.deleteAsset);
    return;
  }
  const thumb = event.target.closest("[data-asset]");
  if (!thumb) {
    return;
  }
  const assetInput = field(imagePanel, "assetPath");
  if (assetInput) {
    assetInput.value = thumb.dataset.asset;
  }
  setImagePreview(`/api/assets/${encodeURIComponent(thumb.dataset.asset)}`);
  renderImageGallery();
  scheduleWidgetPreview();
});

slideshowGallery?.addEventListener("click", (event) => {
  const del = event.target.closest("[data-delete-asset]");
  if (del) {
    deleteAsset(del.dataset.deleteAsset);
    return;
  }
  const thumb = event.target.closest("[data-asset]");
  if (!thumb) {
    return;
  }
  const name = thumb.dataset.asset;
  const index = slideshowItems.indexOf(name);
  if (index >= 0) {
    slideshowItems.splice(index, 1);
  } else {
    slideshowItems.push(name);
  }
  renderSlideshowGallery();
  scheduleWidgetPreview();
});

let drawShapes = [];

const SHAPE_TYPES = ["rect", "circle", "line", "text", "pixel"];
const SHAPE_FIELDS = {
  rect: ["x", "y", "w", "h"],
  circle: ["x", "y", "radius"],
  line: ["x", "y", "x2", "y2"],
  text: ["x", "y", "text", "fontFamily", "size"],
  pixel: ["x", "y"]
};
const SHAPE_FIELD_META = {
  x: { label: "X", type: "number" },
  y: { label: "Y", type: "number" },
  w: { label: "W", type: "number" },
  h: { label: "H", type: "number" },
  radius: { label: "R", type: "number" },
  x2: { label: "X2", type: "number" },
  y2: { label: "Y2", type: "number" },
  text: { label: "Text", type: "text" },
  fontFamily: { label: "Font", type: "select", options: ["pixel", "sans", "mono", "devanagari"] },
  size: { label: "Size", type: "select", options: ["small", "medium", "large"] }
};
const NUMERIC_SHAPE_FIELDS = new Set(["x", "y", "w", "h", "radius", "x2", "y2"]);

function shapeDefaults(type = "rect") {
  return { type, color: "#ffffff", x: 8, y: 8, w: 16, h: 12, radius: 8, x2: 24, y2: 24, text: "HI", size: "small", fill: true, fontFamily: "pixel", bold: false, italic: false };
}

function renderDrawShapes() {
  if (!drawShapeList) {
    return;
  }
  if (!drawShapes.length) {
    drawShapeList.innerHTML = `<p class="muted">No shapes yet. Add a rectangle, circle, line, text, or pixel.</p>`;
    return;
  }
  drawShapeList.innerHTML = drawShapes.map((shape, index) => {
    const typeOptions = SHAPE_TYPES.map((type) => `<option value="${type}" ${shape.type === type ? "selected" : ""}>${type}</option>`).join("");
    const inputs = (SHAPE_FIELDS[shape.type] || SHAPE_FIELDS.rect).map((key) => {
      const meta = SHAPE_FIELD_META[key];
      if (meta.type === "select") {
        const options = meta.options.map((option) => `<option value="${option}" ${shape[key] === option ? "selected" : ""}>${option}</option>`).join("");
        return `<label class="shape-field">${meta.label}<select data-shape-field="${key}">${options}</select></label>`;
      }
      return `<label class="shape-field">${meta.label}<input data-shape-field="${key}" type="${meta.type}" value="${escapeHtml(shape[key])}"></label>`;
    }).join("");
    let toggles = "";
    if (shape.type === "rect" || shape.type === "circle") {
      toggles = `<label class="shape-field check"><input data-shape-field="fill" type="checkbox" ${shape.fill ? "checked" : ""}><span>Fill</span></label>`;
    } else if (shape.type === "text") {
      toggles = `
        <label class="shape-field check"><input data-shape-field="bold" type="checkbox" ${shape.bold ? "checked" : ""}><span>B</span></label>
        <label class="shape-field check"><input data-shape-field="italic" type="checkbox" ${shape.italic ? "checked" : ""}><span>I</span></label>`;
    }
    return `
      <div class="draw-shape-row" data-shape-index="${index}">
        <select data-shape-field="type" class="shape-type">${typeOptions}</select>
        ${inputs}
        <label class="shape-field color"><input data-shape-field="color" type="color" value="${escapeHtml(shape.color)}"></label>
        ${toggles}
        <button type="button" class="icon-button danger" data-shape-remove="${index}" aria-label="Remove shape">x</button>
      </div>`;
  }).join("");
}

function collectDrawShapes() {
  return drawShapes.map((shape) => {
    const cleaned = { type: shape.type, color: shape.color || "#ffffff" };
    for (const key of SHAPE_FIELDS[shape.type] || SHAPE_FIELDS.rect) {
      cleaned[key] = NUMERIC_SHAPE_FIELDS.has(key) ? Number(shape[key]) || 0 : shape[key];
    }
    if (shape.type === "rect" || shape.type === "circle") {
      cleaned.fill = Boolean(shape.fill);
    }
    if (shape.type === "text") {
      cleaned.bold = Boolean(shape.bold);
      cleaned.italic = Boolean(shape.italic);
    }
    return cleaned;
  });
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
  fillPanel(storeSettingsPanel, {
    storeIndexUrl: config.store?.indexUrl || "configs/widget_store_index.json"
  });
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
    weatherRefreshMinutes: config.weather?.refreshMinutes || 15,
    weatherMetricsSeconds: config.weather?.metricsSeconds || 45,
    weatherSceneSeconds: config.weather?.sceneSeconds || 20
  });
  fillPanel(textPanel, {
    text: config.text?.text ?? "HELLO",
    color: config.text?.color || "#ffffff",
    background: config.text?.background || "#000000",
    fontFamily: config.text?.fontFamily || "pixel",
    fontSize: config.text?.fontSize || "medium",
    align: config.text?.align || "center",
    bold: Boolean(config.text?.bold),
    italic: Boolean(config.text?.italic),
    wrap: Boolean(config.text?.wrap),
    fit: Boolean(config.text?.fit),
    scroll: Boolean(config.text?.scroll),
    scrollSpeed: config.text?.scrollSpeed || "normal"
  });
  const imageAsset = config.image?.assetPath || "";
  fillPanel(imagePanel, {
    assetPath: imageAsset,
    fit: config.image?.fit || "contain",
    rotate: String(config.image?.rotate ?? 0),
    background: config.image?.background || "#000000"
  });
  setImagePreview(imageAsset ? `/api/assets/${encodeURIComponent(imageAsset)}` : "");
  fillPanel(drawPanel, { background: config.draw?.background || "#000000" });
  drawShapes = (config.draw?.shapes || []).map((shape) => ({ ...shapeDefaults(shape.type || "rect"), ...shape }));
  renderDrawShapes();
  fillPanel(slideshowPanel, {
    intervalSeconds: config.slideshow?.intervalSeconds ?? 8,
    fit: config.slideshow?.fit || "cover",
    background: config.slideshow?.background || "#000000"
  });
  slideshowItems = [...(config.slideshow?.items || [])];
  renderImageGallery();
  renderSlideshowGallery();
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
    store: {
      indexUrl: fieldValue(storeSettingsPanel, "storeIndexUrl", "configs/widget_store_index.json") || "configs/widget_store_index.json"
    },
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
      refreshMinutes: Number(fieldValue(weatherPanel, "weatherRefreshMinutes", "15") || 15),
      metricsSeconds: Number(fieldValue(weatherPanel, "weatherMetricsSeconds", "45") || 45),
      sceneSeconds: Number(fieldValue(weatherPanel, "weatherSceneSeconds", "20") || 20)
    },
    text: collectWidgetConfig("text"),
    image: collectWidgetConfig("image"),
    draw: collectWidgetConfig("draw"),
    slideshow: collectWidgetConfig("slideshow")
  };
}

function collectWidgetConfig(plugin = selectedPlugin) {
  if (plugin === "text") {
    return {
      text: fieldValue(textPanel, "text", ""),
      color: fieldValue(textPanel, "color", "#ffffff") || "#ffffff",
      background: fieldValue(textPanel, "background", "#000000") || "#000000",
      fontFamily: fieldValue(textPanel, "fontFamily", "pixel"),
      fontSize: fieldValue(textPanel, "fontSize", "medium"),
      align: fieldValue(textPanel, "align", "center"),
      bold: fieldChecked(textPanel, "bold"),
      italic: fieldChecked(textPanel, "italic"),
      wrap: fieldChecked(textPanel, "wrap"),
      fit: fieldChecked(textPanel, "fit"),
      scroll: fieldChecked(textPanel, "scroll"),
      scrollSpeed: fieldValue(textPanel, "scrollSpeed", "normal")
    };
  }
  if (plugin === "image") {
    return {
      assetPath: fieldValue(imagePanel, "assetPath", ""),
      fit: fieldValue(imagePanel, "fit", "contain"),
      rotate: Number(fieldValue(imagePanel, "rotate", "0")) || 0,
      background: fieldValue(imagePanel, "background", "#000000") || "#000000"
    };
  }
  if (plugin === "draw") {
    return {
      background: fieldValue(drawPanel, "background", "#000000") || "#000000",
      shapes: collectDrawShapes()
    };
  }
  if (plugin === "slideshow") {
    return {
      items: [...slideshowItems],
      intervalSeconds: Number(fieldValue(slideshowPanel, "intervalSeconds", "8")) || 8,
      fit: fieldValue(slideshowPanel, "fit", "cover"),
      background: fieldValue(slideshowPanel, "background", "#000000") || "#000000"
    };
  }
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
      refreshMinutes: Number(fieldValue(weatherPanel, "weatherRefreshMinutes", "15") || 15),
      metricsSeconds: Number(fieldValue(weatherPanel, "weatherMetricsSeconds", "45") || 45),
      sceneSeconds: Number(fieldValue(weatherPanel, "weatherSceneSeconds", "20") || 20)
    };
  }
  if (plugin === "testPattern") {
    return {
      testPattern: true
    };
  }
  if (plugin?.includes(".") && !plugin?.startsWith("core.")) {
    const widget = selectedLocalWidget(plugin);
    const values = {};
    for (const fieldDef of widget?.manifest?.config || []) {
      const control = field(externalWidgetPanel, fieldDef.key);
      if (!control) {
        continue;
      }
      if (control.type === "checkbox") {
        values[fieldDef.key] = control.checked;
      } else if (control.type === "number") {
        values[fieldDef.key] = control.value === "" ? null : Number(control.value);
      } else {
        values[fieldDef.key] = control.value;
      }
    }
    return values;
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

async function openPluginSettings(plugin) {
  setSelectedPlugin(plugin);
  if (plugin === "image" || plugin === "slideshow") {
    loadGallery();
  }
  if (plugin?.includes(".") && !plugin?.startsWith("core.")) {
    try {
      const response = await api(`/api/widgets/local/${encodeURIComponent(widgetIdForMode(plugin))}/config`);
      renderExternalWidgetConfig(plugin, response.config || {});
    } catch (error) {
      renderExternalWidgetConfig(plugin);
      setMessage(error.message);
    }
  }
  pluginDialog.showModal();
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

function renderBluetooth(status, devices) {
  if (!bluetoothStatus || !bluetoothDeviceList) {
    return;
  }
  if (!status.available) {
    bluetoothStatus.textContent = "Bluetooth is not available on this device.";
    bluetoothDeviceList.innerHTML = "";
    if (bluetoothScanButton) bluetoothScanButton.disabled = true;
    return;
  }
  bluetoothStatus.textContent = `Adapter ${status.adapter || "ready"} · power ${status.powered ? "on" : "off"}`;
  const sorted = [...devices].sort((a, b) => Number(b.connected) - Number(a.connected) || Number(b.paired) - Number(a.paired));
  if (!sorted.length) {
    bluetoothDeviceList.innerHTML = `<p class="muted">No devices yet. Put your speaker in pairing mode and tap Scan.</p>`;
    return;
  }
  bluetoothDeviceList.innerHTML = sorted.map((device) => {
    const label = escapeHtml(device.name || device.mac);
    const mac = escapeHtml(device.mac);
    const state = device.connected ? "Connected" : device.paired ? "Paired" : "";
    const primary = device.connected
      ? `<button type="button" class="secondary" data-bt-disconnect="${mac}">Disconnect</button>`
      : `<button type="button" data-bt-connect="${mac}">Connect</button>`;
    const forget = device.paired ? `<button type="button" class="secondary danger" data-bt-remove="${mac}">Forget</button>` : "";
    return `
      <div class="bt-device${device.connected ? " connected" : ""}">
        <div class="bt-device-info">
          <strong>${label}</strong>
          <small>${mac}${state ? ` · ${state}` : ""}</small>
        </div>
        <div class="bt-device-actions">${primary}${forget}</div>
      </div>`;
  }).join("");
}

async function refreshBluetooth() {
  if (!bluetoothPanel) {
    return;
  }
  try {
    const [status, devices] = await Promise.all([api("/api/bluetooth/status"), api("/api/bluetooth/devices")]);
    renderBluetooth(status, devices.devices || []);
  } catch (error) {
    if (bluetoothStatus) bluetoothStatus.textContent = "Bluetooth status unavailable.";
  }
}

bluetoothScanButton?.addEventListener("click", async () => {
  bluetoothScanButton.disabled = true;
  bluetoothScanButton.textContent = "Scanning…";
  try {
    const response = await api("/api/bluetooth/scan", { method: "POST", body: JSON.stringify({ seconds: 8 }) });
    const status = await api("/api/bluetooth/status");
    renderBluetooth(status, response.devices || []);
  } catch (error) {
    setMessage(error.message);
  } finally {
    bluetoothScanButton.disabled = false;
    bluetoothScanButton.textContent = "Scan";
  }
});

bluetoothDeviceList?.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-bt-connect], [data-bt-disconnect], [data-bt-remove]");
  if (!button) {
    return;
  }
  const connect = button.dataset.btConnect;
  const disconnect = button.dataset.btDisconnect;
  const remove = button.dataset.btRemove;
  const original = button.textContent;
  button.disabled = true;
  button.textContent = connect ? "Connecting…" : disconnect ? "Disconnecting…" : "Forgetting…";
  try {
    if (connect) await api("/api/bluetooth/connect", { method: "POST", body: JSON.stringify({ mac: connect }) });
    else if (disconnect) await api("/api/bluetooth/disconnect", { method: "POST", body: JSON.stringify({ mac: disconnect }) });
    else if (remove) await api("/api/bluetooth/remove", { method: "POST", body: JSON.stringify({ mac: remove }) });
    await refreshBluetooth();
  } catch (error) {
    setMessage(error.message);
    button.disabled = false;
    button.textContent = original;
  }
});

navItems.forEach((item) => item.addEventListener("click", () => item.dataset.page && setPage(item.dataset.page)));

sidebarToggle?.addEventListener("click", () => {
  const collapsed = document.body.classList.toggle("sidebar-collapsed");
  sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
  sidebarToggle.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
});

pluginGrid?.addEventListener("click", (event) => {
  const uninstallButton = event.target.closest("[data-widget-uninstall]");
  if (uninstallButton) {
    event.stopPropagation();
    uninstallButton.disabled = true;
    uninstallButton.textContent = "Removing...";
    api(`/api/widgets/local/${encodeURIComponent(uninstallButton.dataset.widgetUninstall)}`, { method: "DELETE" })
      .then(async () => {
        setMessage("Widget uninstalled.");
        await refreshConfig();
        await refreshLocalWidgets();
        await refreshStoreWidgets();
        await refreshDisplayPolicy();
        await refreshStatus();
      })
      .catch((error) => {
        uninstallButton.disabled = false;
        uninstallButton.textContent = "Uninstall";
        setMessage(error.message);
      });
    return;
  }
  const settingsButton = event.target.closest("[data-plugin-settings]");
  if (settingsButton) {
    event.stopPropagation();
    const plugin = settingsButton.dataset.pluginSettings;
    openPluginSettings(plugin);
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
  if (!installButton) {
    return;
  }
  installButton.disabled = true;
  const wasInstalled = installButton.textContent === "Update";
  installButton.textContent = wasInstalled ? "Updating..." : "Installing...";
  try {
    await api("/api/widgets/install", {
      method: "POST",
      body: JSON.stringify({ widgetId: installButton.dataset.storeInstall })
    });
    await refreshLocalWidgets();
    await refreshStoreWidgets();
    setMessage(wasInstalled ? "Widget updated locally." : "Widget installed locally.");
  } catch (error) {
    installButton.disabled = false;
    installButton.textContent = wasInstalled ? "Update" : "Install";
    setMessage(error.message);
  }
});

savePolicyButton?.addEventListener("click", async () => {
  savePolicyButton.disabled = true;
  try {
    await saveDisplayPolicy();
  } catch (error) {
    setMessage(error.message);
  } finally {
    savePolicyButton.disabled = false;
  }
});

applyPolicyButton?.addEventListener("click", async () => {
  applyPolicyButton.disabled = true;
  try {
    await applyDisplayPolicy();
  } catch (error) {
    setMessage(error.message);
  } finally {
    applyPolicyButton.disabled = false;
  }
});

addTriggerButton?.addEventListener("click", () => addTriggerRule());

triggerList?.addEventListener("click", (event) => {
  const removeButton = event.target.closest("[data-remove-trigger]");
  if (!removeButton) {
    return;
  }
  removeButton.closest(".trigger-row")?.remove();
  if (!triggerList.querySelector(".trigger-row")) {
    triggerList.innerHTML = `<p class="muted">No trigger rules configured.</p>`;
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
  openPluginSettings(normalizeMode(currentConfig));
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

storeSettingsPanel?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await saveConfig();
  await refreshStoreWidgets();
  setMessage("Widget store settings saved.");
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

imageFileInput?.addEventListener("change", async () => {
  const file = imageFileInput.files?.[0];
  if (!file) {
    return;
  }
  try {
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error("Could not read the selected file."));
      reader.readAsDataURL(file);
    });
    setMessage("Uploading image...");
    const response = await api("/api/assets/upload", { method: "POST", body: JSON.stringify({ name: file.name, data: dataUrl }) });
    const assetInput = field(imagePanel, "assetPath");
    if (assetInput) {
      assetInput.value = response.assetPath;
    }
    setImagePreview(response.url);
    setMessage("Image uploaded. Apply to show it on the matrix.");
    loadGallery();
    scheduleWidgetPreview();
  } catch (error) {
    setMessage(error.message);
  } finally {
    imageFileInput.value = "";
  }
});

textPanel?.addEventListener("input", scheduleWidgetPreview);
imagePanel?.addEventListener("input", scheduleWidgetPreview);
drawPanel?.addEventListener("input", scheduleWidgetPreview);
slideshowPanel?.addEventListener("input", scheduleWidgetPreview);

addShapeButton?.addEventListener("click", () => {
  drawShapes.push(shapeDefaults("rect"));
  renderDrawShapes();
  scheduleWidgetPreview();
});

function onShapeFieldChange(event) {
  const control = event.target.closest("[data-shape-field]");
  if (!control) {
    return;
  }
  const row = control.closest("[data-shape-index]");
  const index = Number(row?.dataset.shapeIndex);
  if (!Number.isInteger(index) || !drawShapes[index]) {
    return;
  }
  const key = control.dataset.shapeField;
  if (key === "type") {
    const current = drawShapes[index];
    drawShapes[index] = { ...shapeDefaults(control.value), color: current.color, x: current.x, y: current.y };
    renderDrawShapes();
    scheduleWidgetPreview();
    return;
  }
  drawShapes[index][key] = control.type === "checkbox" ? control.checked : control.value;
  scheduleWidgetPreview();
}

drawShapeList?.addEventListener("input", onShapeFieldChange);
drawShapeList?.addEventListener("change", onShapeFieldChange);

drawShapeList?.addEventListener("click", (event) => {
  const removeButton = event.target.closest("[data-shape-remove]");
  if (!removeButton) {
    return;
  }
  drawShapes.splice(Number(removeButton.dataset.shapeRemove), 1);
  renderDrawShapes();
  scheduleWidgetPreview();
});

populateTimezones();

refreshConfig()
  .then(refreshLocalWidgets)
  .then(refreshDisplayPolicy)
  .then(refreshStoreWidgets)
  .then(refreshStatus)
  .then(loadGallery)
  .then(refreshBluetooth)
  .catch((error) => setMessage(error.message));

setInterval(refreshStatus, 5000);
