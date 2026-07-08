const configForm = document.querySelector("#configForm");
const matrixForm = document.querySelector("#matrixForm");
const pairButton = document.querySelector("#pairButton");
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
  matrixForm.testPattern.checked = Boolean(config.runtime.testPattern);
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
      mockOutput: matrixForm.mockOutput.value,
      testPattern: matrixForm.testPattern.checked
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
    ? "Spotify credentials and token are ready."
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
matrixForm.addEventListener("submit", saveConfig);

pairButton.addEventListener("click", async () => {
  const session = await api("/api/auth/session", { method: "POST", body: "{}" });
  const origin = window.location.origin;
  setMessage(session.command.replace(`http://<pi-host>:${window.location.port || 3000}`, origin));
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
