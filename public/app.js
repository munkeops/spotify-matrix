const configForm = document.querySelector("#configForm");
const displayForm = document.querySelector("#displayForm");
const matrixForm = document.querySelector("#matrixForm");
const pairButton = document.querySelector("#pairButton");
const directAuthButton = document.querySelector("#directAuthButton");
const uploadImageButton = document.querySelector("#uploadImageButton");
const pairCommand = document.querySelector("#pairCommand");
const startButton = document.querySelector("#startButton");
const stopButton = document.querySelector("#stopButton");
const statusDot = document.querySelector("#statusDot");
const statusTitle = document.querySelector("#statusTitle");
const statusText = document.querySelector("#statusText");
const runtimePill = document.querySelector("#runtimePill");
const tokenState = document.querySelector("#tokenState");
const dataDir = document.querySelector("#dataDir");
const processState = document.querySelector("#processState");

let currentConfig = null;

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

function fillForms(config) {
  currentConfig = config;
  configForm.clientId.value = config.spotify.clientId || "";
  configForm.clientSecret.value = config.spotify.clientSecret || "";
  configForm.redirectUri.value = config.spotify.redirectUri || "http://127.0.0.1:8888/callback";
  displayForm.displayMode.value = config.runtime.displayMode || (config.runtime.testPattern ? "test_pattern" : "spotify");
  displayForm.weatherLocation.value = config.weather?.location || "";
  displayForm.weatherTemperature.value = config.weather?.temperature || "";
  displayForm.weatherCondition.value = config.weather?.condition || "";
  displayForm.calendarTitle.value = config.calendar?.title || "";

  for (const [key, value] of Object.entries(config.matrix)) {
    if (matrixForm[key]) {
      if (matrixForm[key].type === "checkbox") {
        matrixForm[key].checked = Boolean(value);
      } else {
        matrixForm[key].value = value;
      }
    }
  }
  matrixForm.mockOutput.value = config.runtime.mockOutput || "";
  matrixForm.testPattern.checked = displayForm.displayMode.value === "test_pattern" || Boolean(config.runtime.testPattern);
}

function collectConfig() {
  return {
    spotify: {
      clientId: configForm.clientId.value,
      clientSecret: configForm.clientSecret.value,
      redirectUri: configForm.redirectUri.value
    },
    matrix: {
      rows: matrixForm.rows.value,
      cols: matrixForm.cols.value,
      chainLength: matrixForm.chainLength.value,
      parallel: matrixForm.parallel.value,
      brightness: matrixForm.brightness.value,
      gpioSlowdown: matrixForm.gpioSlowdown.value,
      hardwareMapping: matrixForm.hardwareMapping.value,
      pwmBits: matrixForm.pwmBits.value,
      limitRefreshRateHz: matrixForm.limitRefreshRateHz.value,
      noHardwarePulse: matrixForm.noHardwarePulse.checked,
      pollSeconds: matrixForm.pollSeconds.value,
      fps: matrixForm.fps.value,
      rpm: matrixForm.rpm.value
    },
    runtime: {
      displayMode: displayForm.displayMode.value,
      mockOutput: matrixForm.mockOutput.value,
      testPattern: displayForm.displayMode.value === "test_pattern",
      imagePath: currentConfig?.runtime?.imagePath || ""
    },
    weather: {
      location: displayForm.weatherLocation.value,
      temperature: displayForm.weatherTemperature.value,
      condition: displayForm.weatherCondition.value
    },
    calendar: {
      title: displayForm.calendarTitle.value,
      timezone: currentConfig?.calendar?.timezone || "local"
    }
  };
}

async function saveConfig(event) {
  event.preventDefault();
  const saved = await api("/api/config", {
    method: "POST",
    body: JSON.stringify(collectConfig())
  });
  fillForms(saved);
  setMessage("Configuration saved.");
  await refreshStatus();
}

async function refreshConfig() {
  fillForms(await api("/api/config"));
}

async function refreshStatus() {
  const status = await api("/api/status");
  const running = status.runtime.running;
  runtimePill.textContent = running ? "Running" : "Stopped";
  runtimePill.classList.toggle("running", running);

  statusDot.className = `status-dot ${status.configured ? "ok" : "bad"}`;
  statusTitle.textContent = status.configured ? "Ready" : "Setup needed";
  statusText.textContent = status.configured
    ? `${displayForm.displayMode.options[displayForm.displayMode.selectedIndex].text} mode is ready.`
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

configForm.addEventListener("submit", saveConfig);
displayForm.addEventListener("submit", saveConfig);
matrixForm.addEventListener("submit", saveConfig);

displayForm.displayMode.addEventListener("change", () => {
  matrixForm.testPattern.checked = displayForm.displayMode.value === "test_pattern";
});

matrixForm.testPattern.addEventListener("change", () => {
  displayForm.displayMode.value = matrixForm.testPattern.checked ? "test_pattern" : "spotify";
});

uploadImageButton.addEventListener("click", async () => {
  const file = displayForm.displayImage.files[0];
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
  displayForm.displayMode.value = "image";
  setMessage(`Image uploaded to ${payload.imagePath}. Save or start the matrix in image mode.`);
  await refreshStatus();
});

pairButton.addEventListener("click", async () => {
  const session = await api("/api/auth/session", { method: "POST", body: "{}" });
  const origin = window.location.origin;
  setMessage(session.command.replace(`http://<pi-host>:${window.location.port || 3000}`, origin));
});

directAuthButton.addEventListener("click", async () => {
  await api("/api/config", {
    method: "POST",
    body: JSON.stringify(collectConfig())
  });
  window.location.href = "/api/auth/login";
});

startButton.addEventListener("click", async () => {
  await api("/api/runtime/start", { method: "POST", body: "{}" });
  await refreshStatus();
});

stopButton.addEventListener("click", async () => {
  await api("/api/runtime/stop", { method: "POST", body: "{}" });
  await refreshStatus();
});

refreshConfig()
  .then(refreshStatus)
  .catch((error) => setMessage(error.message));

setInterval(refreshStatus, 5000);
