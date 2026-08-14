"use strict";
/* Meme Studio — self-contained canvas editor. Composes a scene (background image +
   freehand strokes + shapes + text) and exports it to a 64x64 PNG for the matrix. */

const STAGE = 384;
const stage = document.getElementById("stage");
const ctx = stage.getContext("2d");
const preview = document.getElementById("preview");
const pctx = preview.getContext("2d");

const state = {
  tool: "pen",
  color: "#ffffff",
  size: 6,
  fill: false,
  textFont: "sans-serif",
  textSize: 52,
  textBold: false,
  objects: [],
  background: { color: "#000000", img: null, fit: "cover", rotate: 0 },
  selected: -1,
};

let draft = null; // in-progress object
let drag = null; // { index, startX, startY, origin }
let rotatedBgCache = null; // { key, canvas }
const undoStack = [];

// ---------- helpers ----------
const $ = (id) => document.getElementById(id);

function toStage(event) {
  const rect = stage.getBoundingClientRect();
  return {
    x: (event.clientX - rect.left) * (STAGE / rect.width),
    y: (event.clientY - rect.top) * (STAGE / rect.height),
  };
}

function snapshot() {
  undoStack.push(JSON.stringify(state.objects));
  if (undoStack.length > 60) undoStack.shift();
}

function toast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (el.hidden = true), 2200);
}

async function api(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || payload.message || "Request failed");
  return payload;
}

// ---------- background ----------
function rotatedBackground() {
  const img = state.background.img;
  if (!img) return null;
  const rotate = ((state.background.rotate % 360) + 360) % 360;
  const key = `${img.src.length}:${img.width}x${img.height}:${rotate}`;
  if (rotatedBgCache && rotatedBgCache.key === key) return rotatedBgCache.canvas;
  let canvas;
  if (rotate === 0) {
    canvas = img;
  } else {
    canvas = document.createElement("canvas");
    const swap = rotate === 90 || rotate === 270;
    canvas.width = swap ? img.height : img.width;
    canvas.height = swap ? img.width : img.height;
    const c = canvas.getContext("2d");
    c.translate(canvas.width / 2, canvas.height / 2);
    c.rotate((rotate * Math.PI) / 180);
    c.drawImage(img, -img.width / 2, -img.height / 2);
  }
  rotatedBgCache = { key, canvas };
  return canvas;
}

function drawBackground(c, size) {
  c.fillStyle = state.background.color;
  c.fillRect(0, 0, size, size);
  const src = rotatedBackground();
  if (!src) return;
  const iw = src.width;
  const ih = src.height;
  let dw = size;
  let dh = size;
  let dx = 0;
  let dy = 0;
  if (state.background.fit !== "stretch") {
    const scale = state.background.fit === "cover" ? Math.max(size / iw, size / ih) : Math.min(size / iw, size / ih);
    dw = iw * scale;
    dh = ih * scale;
    dx = (size - dw) / 2;
    dy = (size - dh) / 2;
  }
  c.drawImage(src, dx, dy, dw, dh);
}

// ---------- objects ----------
function drawObject(c, o) {
  c.save();
  if (o.erase) c.globalCompositeOperation = "destination-out";
  c.strokeStyle = o.color;
  c.fillStyle = o.color;
  c.lineCap = "round";
  c.lineJoin = "round";
  if (o.type === "stroke") {
    c.lineWidth = o.size;
    if (o.points.length === 1) {
      c.beginPath();
      c.arc(o.points[0].x, o.points[0].y, Math.max(0.5, o.size / 2), 0, Math.PI * 2);
      c.fill();
    } else {
      c.beginPath();
      o.points.forEach((p, i) => (i ? c.lineTo(p.x, p.y) : c.moveTo(p.x, p.y)));
      c.stroke();
    }
  } else if (o.type === "rect") {
    if (o.fill) c.fillRect(o.x, o.y, o.w, o.h);
    else { c.lineWidth = o.size; c.strokeRect(o.x, o.y, o.w, o.h); }
  } else if (o.type === "circle") {
    c.beginPath();
    c.ellipse(o.x + o.w / 2, o.y + o.h / 2, Math.abs(o.w / 2), Math.abs(o.h / 2), 0, 0, Math.PI * 2);
    if (o.fill) c.fill();
    else { c.lineWidth = o.size; c.stroke(); }
  } else if (o.type === "line") {
    c.lineWidth = o.size;
    c.beginPath();
    c.moveTo(o.x, o.y);
    c.lineTo(o.x2, o.y2);
    c.stroke();
  } else if (o.type === "text") {
    c.font = `${o.bold ? "bold " : ""}${o.size}px ${o.font}`;
    c.textBaseline = "top";
    o.text.split("\n").forEach((line, i) => c.fillText(line, o.x, o.y + i * o.size * 1.12));
  }
  c.restore();
}

function objectBounds(o) {
  if (o.type === "stroke") {
    const xs = o.points.map((p) => p.x);
    const ys = o.points.map((p) => p.y);
    const pad = o.size;
    return { x: Math.min(...xs) - pad, y: Math.min(...ys) - pad, w: Math.max(...xs) - Math.min(...xs) + pad * 2, h: Math.max(...ys) - Math.min(...ys) + pad * 2 };
  }
  if (o.type === "rect" || o.type === "circle") {
    return { x: Math.min(o.x, o.x + o.w), y: Math.min(o.y, o.y + o.h), w: Math.abs(o.w), h: Math.abs(o.h) };
  }
  if (o.type === "line") {
    return { x: Math.min(o.x, o.x2), y: Math.min(o.y, o.y2), w: Math.abs(o.x2 - o.x), h: Math.abs(o.y2 - o.y) };
  }
  // text
  ctx.font = `${o.bold ? "bold " : ""}${o.size}px ${o.font}`;
  const lines = o.text.split("\n");
  const width = Math.max(...lines.map((l) => ctx.measureText(l).width), 1);
  return { x: o.x, y: o.y, w: width, h: o.size * 1.12 * lines.length };
}

function hitTest(point) {
  for (let i = state.objects.length - 1; i >= 0; i -= 1) {
    const b = objectBounds(state.objects[i]);
    if (point.x >= b.x && point.x <= b.x + b.w && point.y >= b.y && point.y <= b.y + b.h) return i;
  }
  return -1;
}

function translateObject(o, dx, dy) {
  if (o.type === "stroke") o.points.forEach((p) => { p.x += dx; p.y += dy; });
  else if (o.type === "line") { o.x += dx; o.y += dy; o.x2 += dx; o.y2 += dy; }
  else { o.x += dx; o.y += dy; }
}

// ---------- compose + render ----------
function compose(size) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const c = canvas.getContext("2d");
  drawBackground(c, size);
  const layer = document.createElement("canvas");
  layer.width = size;
  layer.height = size;
  const lc = layer.getContext("2d");
  lc.scale(size / STAGE, size / STAGE);
  const all = draft ? [...state.objects, draft] : state.objects;
  all.forEach((o) => drawObject(lc, o));
  c.drawImage(layer, 0, 0);
  return canvas;
}

function render() {
  ctx.clearRect(0, 0, STAGE, STAGE);
  ctx.drawImage(compose(STAGE), 0, 0);
  if (state.selected >= 0 && state.objects[state.selected]) {
    const b = objectBounds(state.objects[state.selected]);
    ctx.save();
    ctx.strokeStyle = "#4be0c0";
    ctx.setLineDash([5, 4]);
    ctx.lineWidth = 1.5;
    ctx.strokeRect(b.x - 2, b.y - 2, b.w + 4, b.h + 4);
    ctx.restore();
  }
  pctx.clearRect(0, 0, 64, 64);
  pctx.drawImage(compose(64), 0, 0);
}

// ---------- pointer handling ----------
stage.addEventListener("pointerdown", (event) => {
  event.preventDefault();
  stage.setPointerCapture(event.pointerId);
  const p = toStage(event);

  if (state.tool === "select") {
    const index = hitTest(p);
    state.selected = index;
    if (index >= 0) {
      snapshot();
      drag = { index, startX: p.x, startY: p.y };
    }
    render();
    return;
  }

  if (state.tool === "text") {
    snapshot();
    const content = $("textInput").value || "TEXT";
    const obj = { type: "text", x: p.x, y: p.y, text: content, color: state.color, font: state.textFont, size: state.textSize, bold: state.textBold };
    state.objects.push(obj);
    state.selected = state.objects.length - 1;
    render();
    return;
  }

  snapshot();
  if (state.tool === "pen" || state.tool === "eraser") {
    draft = { type: "stroke", points: [p], color: state.color, size: state.size, erase: state.tool === "eraser" };
  } else if (state.tool === "rect" || state.tool === "circle") {
    draft = { type: state.tool, x: p.x, y: p.y, w: 0, h: 0, color: state.color, size: state.size, fill: state.fill };
  } else if (state.tool === "line") {
    draft = { type: "line", x: p.x, y: p.y, x2: p.x, y2: p.y, color: state.color, size: state.size };
  }
  render();
});

stage.addEventListener("pointermove", (event) => {
  if (!draft && !drag) return;
  event.preventDefault();
  const p = toStage(event);
  if (drag) {
    const o = state.objects[drag.index];
    translateObject(o, p.x - drag.startX, p.y - drag.startY);
    drag.startX = p.x;
    drag.startY = p.y;
  } else if (draft.type === "stroke") {
    draft.points.push(p);
  } else if (draft.type === "line") {
    draft.x2 = p.x;
    draft.y2 = p.y;
  } else {
    draft.w = p.x - draft.x;
    draft.h = p.y - draft.y;
  }
  render();
});

function endGesture() {
  if (draft) {
    if (draft.type === "stroke" || draft.type === "line" || Math.abs(draft.w) > 1 || Math.abs(draft.h) > 1) {
      state.objects.push(draft);
    } else {
      undoStack.pop(); // discard the snapshot for an empty click
    }
    draft = null;
  }
  drag = null;
  render();
}
stage.addEventListener("pointerup", endGesture);
stage.addEventListener("pointercancel", endGesture);

// ---------- controls ----------
$("toolbar").addEventListener("click", (event) => {
  const button = event.target.closest(".tool");
  if (!button) return;
  state.tool = button.dataset.tool;
  [...document.querySelectorAll(".tool")].forEach((t) => t.classList.toggle("active", t === button));
  if (state.tool !== "select") state.selected = -1;
  render();
});

$("color").addEventListener("input", (e) => {
  state.color = e.target.value;
  if (state.selected >= 0) { state.objects[state.selected].color = state.color; render(); }
});
$("size").addEventListener("input", (e) => (state.size = Number(e.target.value)));
$("fill").addEventListener("change", (e) => (state.fill = e.target.checked));
$("textInput").addEventListener("input", (e) => {
  if (state.selected >= 0 && state.objects[state.selected].type === "text") {
    state.objects[state.selected].text = e.target.value;
    render();
  }
});
$("textFont").addEventListener("change", (e) => (state.textFont = e.target.value));
$("textSize").addEventListener("input", (e) => (state.textSize = Number(e.target.value)));
$("textBold").addEventListener("change", (e) => (state.textBold = e.target.checked));

$("bgColor").addEventListener("input", (e) => { state.background.color = e.target.value; render(); });
$("bgFit").addEventListener("change", (e) => { state.background.fit = e.target.value; render(); });
$("bgRotate").addEventListener("input", (e) => { state.background.rotate = Number(e.target.value); render(); });
$("clearBg").addEventListener("click", () => { state.background.img = null; rotatedBgCache = null; render(); });
$("bgFile").addEventListener("change", (event) => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    const img = new Image();
    img.onload = () => { state.background.img = img; rotatedBgCache = null; render(); };
    img.src = reader.result;
  };
  reader.readAsDataURL(file);
  event.target.value = "";
});

$("undoBtn").addEventListener("click", () => {
  if (!undoStack.length) return;
  state.objects = JSON.parse(undoStack.pop());
  state.selected = -1;
  render();
});
$("clearBtn").addEventListener("click", () => {
  snapshot();
  state.objects = [];
  state.selected = -1;
  render();
});
$("downloadBtn").addEventListener("click", () => {
  const link = document.createElement("a");
  link.download = "matrix-meme.png";
  link.href = compose(512).toDataURL("image/png");
  link.click();
});
$("applyBtn").addEventListener("click", async () => {
  const button = $("applyBtn");
  button.disabled = true;
  toast("Sending to matrix…");
  try {
    const dataUrl = compose(64).toDataURL("image/png");
    const uploaded = await api("/api/assets/upload", { name: "studio.png", data: dataUrl });
    await api("/api/widgets/local/core.image/apply", { config: { assetPath: uploaded.assetPath, fit: "stretch", background: "#000000" } });
    toast("Saved & sent to matrix ✓");
    loadMemes();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
});

// ---------- my memes gallery ----------
async function loadMemes() {
  const gallery = $("memeGallery");
  try {
    const response = await fetch("/api/assets");
    const payload = await response.json();
    const assets = payload.assets || [];
    if (!assets.length) {
      gallery.innerHTML = '<p style="color:var(--muted);font-size:0.82rem;margin:0">No saved memes yet.</p>';
      return;
    }
    gallery.innerHTML = assets
      .map(
        (a) => `<div class="studio-thumb" data-name="${a.name}" title="Load to edit">
          <img src="${a.url}" alt="">
          ${a.animated ? '<span class="thumb-gif">GIF</span>' : ""}
          <button class="thumb-delete" data-del="${a.name}" aria-label="Delete">×</button>
        </div>`,
      )
      .join("");
  } catch (error) {
    gallery.innerHTML = '<p style="color:var(--muted);font-size:0.82rem;margin:0">Could not load gallery.</p>';
  }
}

$("memeGallery").addEventListener("click", async (event) => {
  const del = event.target.closest("[data-del]");
  if (del) {
    event.stopPropagation();
    try {
      await fetch(`/api/assets/${encodeURIComponent(del.dataset.del)}`, { method: "DELETE" });
      toast("Deleted");
      loadMemes();
    } catch (error) {
      toast("Delete failed", true);
    }
    return;
  }
  const thumb = event.target.closest("[data-name]");
  if (!thumb) return;
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = () => {
    snapshot();
    state.objects = [];
    state.selected = -1;
    state.background.img = img;
    state.background.fit = "cover";
    state.background.rotate = 0;
    rotatedBgCache = null;
    render();
    toast("Loaded — draw on top, then send");
  };
  img.src = `/api/assets/${encodeURIComponent(thumb.dataset.name)}?edit=1`;
});

$("newBtn").addEventListener("click", () => {
  snapshot();
  state.objects = [];
  state.selected = -1;
  state.background.img = null;
  rotatedBgCache = null;
  render();
  toast("New canvas");
});

loadMemes();
render();
