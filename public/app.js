const modeTabs = Array.from(document.querySelectorAll(".mode-tab"));
const modePanels = Array.from(document.querySelectorAll(".mode-panel"));
const modeTitle = document.querySelector("#modeTitle");
const modeSubtitle = document.querySelector("#modeSubtitle");
const saveButton = document.querySelector("#saveButton");
const saveStartButton = document.querySelector("#saveStartButton");
const stopButton = document.querySelector("#stopButton");
const pairButton = document.querySelector("#pairButton");
const directAuthButton = document.querySelector("#directAuthButton");
const uploadImageButton = document.querySelector("#uploadImageButton");
const pairCommand = document.querySelector("#pairCommand");
const statusDot = document.querySelector("#statusDot");
const statusTitle = document.querySelector("#statusTitle");
const statusText = document.querySelector("#statusText");
const runtimePill = document.querySelector("#runtimePill");
const tokenState = document.querySelector("#tokenState");
const dataDir = document.querySelector("#dataDir");
const processState = document.querySelector("#processState");
const previewTitle = document.querySelector("#previewTitle");
const previewDetail = document.querySelector("#previewDetail");
const matrixPreview = document.querySelector("#matrixPreview");
const imageStatus = document.querySelector("#imageStatus");

const modeMeta = {
  spotify: ["Spotify", "Album art record display"],
  image: ["Image", "Static uploaded file"],
  calendar: ["Calendar", "Local date and time"],
  weather: ["Weather", "Manual weather display"],
  test_pattern: ["Test", "Moving panel color check"]
};

const fields = {
  clientId: document.querySelector("#clientId"),
  clientSecret: document.querySelector("#clientSecret"),
  redirectUri: document.querySelector("#redirectUri"),
  displayImage: document.querySelector("#displayImage"),
  weatherLocation: document.querySelector("#weatherLocation"),
  weatherTemperature: document.querySelector("#weatherTemperature"),
  weatherCondition: document.querySelector("#weatherCondition"),
  calendarTitle: document.querySelector("#calendarTitle"),
  rows: document.querySelector("#rows"),
  cols: document.querySelector("#cols"),
  chainLength: document.querySelector("#chainLength"),
  parallel: document.querySelector("#parallel"),
  brightness: document.querySelector("#brightness"),
  gpioSlowdown: document.querySelector("#gpioSlowdown"),
  hardwareMapping: document.querySelector("#hardwareMapping"),
  pwmBits: document.querySelector("#pwmBits"),
  limitRefreshRateHz: document.querySelector("#limitRefreshRateHz"),
  pollSeconds: document.querySelector("#pollSeconds"),
  fps: document.querySelector("#fps"),
  rpm: document.querySelector("#rpm"),
  mockOutput: document.querySelector("#mockOutput"),
  noHardwarePulse: document.querySelector("#noHardwarePulse")
};

let currentConfig = null;
let activeMode = "spotify";

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

function setMessage(message) {
  pairCommand.textContent = message;
}

function selectMode(mode) {
  activeMode = mode;
  const [title, subtitle] = modeMeta[mode];
  modeTitle.textContent = title;
  modeSubtitle.textContent = subtitle;
  modeTabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.mode === mode));
  modePanels.forEach((panel) => panel.classList.toggle("active", panel.dataset.panel === mode));
  matrixPreview.dataset.mode = mode;
  updatePreview();
}

function fillFields(config) {
  currentConfig = config;
  fields.clientId.value = config.spotify.clientId || "";
  fields.clientSecret.value = config.spotify.clientSecret || "";
  fields.redirectUri.value = config.spotify.redirectUri || "http://127.0.0.1:8888/callback";

  for (const [key, value] of Object.entries(config.matrix)) {
    if (fields[key]) {
      if (fields[key].type === "checkbox") {
        fields[key].checked = Boolean(value);
      } else {
        fields[key].value = value;
      }
    }
  }

  fields.mockOutput.value = config.runtime.mockOutput || "";
  fields.weatherLocation.value = config.weather?.location || "";
  fields.weatherTemperature.value = config.weather?.temperature || "";
  fields.weatherCondition.value = config.weather?.condition || "";
  fields.calendarTitle.value = config.calendar?.title || "";
  imageStatus.textContent = config.runtime.imagePath ? `Saved: ${config.runtime.imagePath}` : "No image uploaded.";

  selectMode(config.runtime.testPattern ? "test_pattern" : config.runtime.displayMode || "spotify");
}

function collectConfig(mode = activeMode) {
  return {
    spotify: {
      clientId: fields.clientId.value,
      clientSecret: fields.clientSecret.value,
      redirectUri: fields.redirectUri.value
    },
    matrix: {
      rows: fields.rows.value,
      cols: fields.cols.value,
      chainLength: fields.chainLength.value,
      parallel: fields.parallel.value,
      brightness: fields.brightness.value,
      gpioSlowdown: fields.gpioSlowdown.value,
      hardwareMapping: fields.hardwareMapping.value,
      pwmBits: fields.pwmBits.value,
      limitRefreshRateHz: fields.limitRefreshRateHz.value,
      noHardwarePulse: fields.noHardwarePulse.checked,
      pollSeconds: fields.pollSeconds.value,
      fps: fields.fps.value,
      rpm: fields.rpm.value
    },
    runtime: {
      displayMode: mode,
      mockOutput: fields.mockOutput.value,
      testPattern: mode === "test_pattern",
      imagePath: currentConfig?.runtime?.imagePath || ""
    },
    weather: {
      location: fields.weatherLocation.value,
      temperature: fields.weatherTemperature.value,
      condition: fields.weatherCondition.value
    },
    calendar: {
      title: fields.calendarTitle.value,
      timezone: currentConfig?.calendar?.timezone || "local"
    }
  };
}

async function saveConfig(mode = activeMode) {
  const saved = await api("/api/config", {
    method: "POST",
    body: JSON.stringify(collectConfig(mode))
  });
  fillFields(saved);
  setMessage(`${modeMeta[mode][0]} mode saved.`);
  await refreshStatus();
  return saved;
}

async function refreshConfig() {
  fillFields(await api("/api/config"));
}

function updatePreview() {
  const [title] = modeMeta[activeMode];
  previewTitle.textContent = title;
  if (activeMode === "spotify") {
    previewDetail.textContent = fields.clientId.value ? "Credentials saved locally" : "Add Spotify credentials";
  } else if (activeMode === "image") {
    previewDetail.textContent = currentConfig?.runtime?.imagePath ? "Uploaded image ready" : "Upload an image";
  } else if (activeMode === "calendar") {
    previewDetail.textContent = fields.calendarTitle.value || new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } else if (activeMode === "weather") {
    previewDetail.textContent = [fields.weatherTemperature.value, fields.weatherCondition.value].filter(Boolean).join(" / ") || "Set weather text";
  } else {
    previewDetail.textContent = "Color bars";
  }
}

async function refreshStatus() {
  const status = await api("/api/status");
  const running = status.runtime.running;
  runtimePill.textContent = running ? "Running" : "Stopped";
  runtimePill.classList.toggle("running", running);

  statusDot.className = `status-dot ${status.configured ? "ok" : "bad"}`;
  statusTitle.textContent = status.configured ? "Ready" : "Setup needed";
  statusText.textContent = status.configured
    ? `${modeMeta[activeMode][0]} mode is ready.`
    : `Missing: ${status.missing.join(", ")}`;

  tokenState.textContent = status.token.present
    ? `Saved${status.token.hasRefreshToken ? " with refresh token" : ""}`
    : "Not paired";
  dataDir.textContent = status.dataDir;
  processState.textContent = running
    ? `PID ${status.runtime.pid}`
    : status.runtime.lastExit
      ? `Stopped at ${status.runtime.lastExit.at}`
      : "Stopped";
}

modeTabs.forEach((tab) => {
  tab.addEventListener("click", () => selectMode(tab.dataset.mode));
});

Object.values(fields).forEach((field) => {
  if (field && field.tagName !== "INPUT") return;
  field?.addEventListener("input", updatePreview);
});

saveButton.addEventListener("click", async () => {
  await saveConfig(activeMode);
});

saveStartButton.addEventListener("click", async () => {
  await saveConfig(activeMode);
  await api("/api/runtime/start", { method: "POST", body: "{}" });
  await refreshStatus();
});

stopButton.addEventListener("click", async () => {
  await api("/api/runtime/stop", { method: "POST", body: "{}" });
  await refreshStatus();
});

uploadImageButton.addEventListener("click", async () => {
  const file = fields.displayImage.files[0];
  if (!file) {
    setMessage("Choose an image file first.");
    return;
  }
  const response = await fetch("/api/display/image", {
    method: "POST",
    headers: { "Content-Type": file.type || "application/octet-stream" },
    body: file
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || payload.detail || payload.message || "Image upload failed");
  }
  await refreshConfig();
  selectMode("image");
  setMessage(`Image uploaded to ${payload.imagePath}.`);
  await refreshStatus();
});

pairButton.addEventListener("click", async () => {
  await saveConfig("spotify");
  const session = await api("/api/auth/session", { method: "POST", body: "{}" });
  const origin = window.location.origin;
  setMessage(session.command.replace(`http://<pi-host>:${window.location.port || 3000}`, origin));
});

directAuthButton.addEventListener("click", async () => {
  await saveConfig("spotify");
  window.location.href = "/api/auth/login";
});

refreshConfig()
  .then(refreshStatus)
  .catch((error) => setMessage(error.message));

setInterval(refreshStatus, 5000);
setInterval(updatePreview, 30000);
