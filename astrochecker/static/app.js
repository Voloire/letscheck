"use strict";

const TIME_ZONE = "Europe/Rome";
const HORIZON_SECONDS = 86400;

const form = document.querySelector("#planner-form");
const fields = document.querySelector("#planner-fields");
const verifyButton = document.querySelector("#verify-connection");
const calculateButton = document.querySelector("#calculate");
const connectionStatus = document.querySelector("#connection-status");
const headerConnection = document.querySelector("#header-connection");
const unlockNote = document.querySelector("#unlock-note");
const formError = document.querySelector("#form-error");
const resultError = document.querySelector("#result-error");
const emptyResult = document.querySelector("#empty-result");
const resultContent = document.querySelector("#result-content");
const resultLive = document.querySelector("#result-live");
const staleBadge = document.querySelector("#stale-badge");

let connected = false;
let hasResult = false;
let calculationRunning = false;

function romeDateAtTenPm() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const part = (type) => parts.find((item) => item.type === type)?.value;
  return `${part("year")}-${part("month")}-${part("day")}T22:00`;
}

document.querySelector("#start").value = romeDateAtTenPm();

function setButtonLoading(button, isLoading, text) {
  button.disabled = isLoading;
  button.classList.toggle("loading", isLoading);
  const label = button.querySelector(".button-label");
  if (!label.dataset.idle) label.dataset.idle = label.textContent;
  label.textContent = isLoading ? text : label.dataset.idle;
  button.setAttribute("aria-busy", String(isLoading));
}

function setConnected(next, message) {
  connected = next;
  fields.disabled = !next || calculationRunning;
  headerConnection.classList.toggle("connected", next);
  headerConnection.classList.toggle("failed", !next && Boolean(message));
  headerConnection.querySelector("span:last-child").textContent = next ? "SkyChart connesso" : message ? "Non connesso" : "Da verificare";
  connectionStatus.className = `status-message ${next ? "success" : message ? "error" : ""}`;
  connectionStatus.textContent = message || "SkyChart non verificato.";
  unlockNote.classList.toggle("unlocked", next);
  unlockNote.textContent = next
    ? "Connessione verificata. Il pianificatore è pronto."
    : "Verifica la connessione per sbloccare il pianificatore.";
  if (next) document.querySelector("#connection-details").open = false;
}

async function readJson(response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    throw new Error("Il server ha restituito una risposta non leggibile.");
  }
}

verifyButton.addEventListener("click", async () => {
  setButtonLoading(verifyButton, true, "Verifica in corso…");
  connectionStatus.className = "status-message";
  connectionStatus.textContent = "Contatto SkyChart…";
  try {
    const response = await fetch("/api/status", { headers: { Accept: "application/json" } });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "Verifica non riuscita.");
    if (data.connected) {
      setConnected(true, data.message || `SkyChart connesso a 127.0.0.1:${data.port || 3292}.`);
    } else {
      setConnected(false, data.message || "SkyChart non raggiungibile. Controlla il server TCP/IP e riprova.");
    }
  } catch (error) {
    setConnected(false, error instanceof Error ? error.message : "Connessione non riuscita. Riprova.");
  } finally {
    setButtonLoading(verifyButton, false, "");
  }
});

function numberValue(id) {
  const value = document.querySelector(id).value.trim();
  return value === "" ? NaN : Number(value);
}

function showFormError(message, invalidInput) {
  formError.textContent = message;
  formError.hidden = false;
  if (invalidInput) {
    invalidInput.setAttribute("aria-invalid", "true");
    invalidInput.focus();
  }
}

function clearFormErrors() {
  formError.hidden = true;
  formError.textContent = "";
  form.querySelectorAll("[aria-invalid='true']").forEach((input) => input.removeAttribute("aria-invalid"));
}

function validateForm() {
  clearFormErrors();
  const rules = [
    ["#object", (v) => v.trim().length > 0, "Inserisci il nome dell’oggetto."],
    ["#latitude", (v) => Number.isFinite(Number(v)) && Number(v) >= -90 && Number(v) <= 90, "La latitudine deve essere compresa tra −90° e 90°."],
    ["#longitude", (v) => Number.isFinite(Number(v)) && Number(v) >= -180 && Number(v) <= 180, "La longitudine deve essere compresa tra −180° e 180°."],
    ["#start", (v) => v !== "", "Scegli una data e un’ora locale."],
    ["#duration", (v) => Number.isFinite(Number(v)) && Number(v) > 0 && Number(v) <= 1440, "La durata deve essere maggiore di 0 e non superare 1.440 minuti."],
    ["#min-alt", (v) => Number.isFinite(Number(v)) && Number(v) >= 0 && Number(v) <= 90, "L’altezza minima deve essere compresa tra 0° e 90°."],
    ["#max-alt", (v) => Number.isFinite(Number(v)) && Number(v) >= 0 && Number(v) <= 90, "L’altezza massima deve essere compresa tra 0° e 90°."],
    ["#az-start", (v) => Number.isFinite(Number(v)) && Number(v) >= 0 && Number(v) <= 360, "L’azimut iniziale deve essere compreso tra 0° e 360°."],
    ["#az-end", (v) => Number.isFinite(Number(v)) && Number(v) >= 0 && Number(v) <= 360, "L’azimut finale deve essere compreso tra 0° e 360°."],
  ];
  for (const [selector, valid, message] of rules) {
    const input = document.querySelector(selector);
    if (!valid(input.value)) {
      showFormError(message, input);
      return false;
    }
  }
  const minAlt = numberValue("#min-alt");
  const maxAlt = numberValue("#max-alt");
  if (maxAlt <= minAlt) {
    showFormError("L’altezza massima deve essere maggiore di quella minima.", document.querySelector("#max-alt"));
    return false;
  }
  const azStart = numberValue("#az-start");
  const azEnd = numberValue("#az-end");
  const isWholeHorizon = azStart === 0 && azEnd === 360;
  if (!isWholeHorizon && azStart % 360 === azEnd % 360) {
    showFormError("Gli azimut iniziale e finale uguali sono ambigui. Usa 0° → 360° per tutto l’orizzonte.", document.querySelector("#az-end"));
    return false;
  }
  return true;
}

function currentPayload() {
  return {
    object: document.querySelector("#object").value.trim(),
    latitude: numberValue("#latitude"),
    longitude: numberValue("#longitude"),
    start: document.querySelector("#start").value,
    duration_minutes: numberValue("#duration"),
    min_alt: numberValue("#min-alt"),
    max_alt: numberValue("#max-alt"),
    az_start: numberValue("#az-start"),
    az_end: numberValue("#az-end"),
  };
}

function markStale() {
  if (!hasResult || calculationRunning) return;
  staleBadge.hidden = false;
  resultContent.classList.add("is-stale");
}

form.addEventListener("input", (event) => {
  event.target.removeAttribute("aria-invalid");
  if (!formError.hidden) {
    formError.hidden = true;
    formError.textContent = "";
  }
  markStale();
});

function formatInstant(startIso, offsetSeconds, includeWeekday = true) {
  const instant = new Date(new Date(startIso).getTime() + Number(offsetSeconds) * 1000);
  const options = {
    timeZone: TIME_ZONE,
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZoneName: "short",
  };
  if (includeWeekday) options.weekday = "short";
  return new Intl.DateTimeFormat("it-IT", options).format(instant);
}

function formatClock(startIso, offsetSeconds) {
  const instant = new Date(new Date(startIso).getTime() + Number(offsetSeconds) * 1000);
  return new Intl.DateTimeFormat("it-IT", {
    timeZone: TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(instant);
}

function formatDuration(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  if (value < 60) return `${Number.isInteger(value) ? value : value.toFixed(1)} s`;
  const whole = Math.floor(value);
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const remainder = whole % 60;
  const parts = [];
  if (hours) parts.push(`${hours} h`);
  if (minutes) parts.push(`${minutes} min`);
  if (remainder) parts.push(`${remainder} s`);
  return parts.join(" ") || "0 s";
}

function statusLabel(status) {
  return {
    full: "Visibile per tutta la durata",
    partial: "Visibile solo in parte",
    none: "Non visibile nel periodo richiesto",
  }[status] || "Risultato non riconosciuto";
}

function renderTimeline(data) {
  const intervals = document.querySelector("#timeline-intervals");
  intervals.replaceChildren();
  const horizon = Number(data.horizon_seconds) || HORIZON_SECONDS;
  for (const item of data.intervals || []) {
    const segment = document.createElement("span");
    segment.className = "timeline-segment";
    segment.style.left = `${Math.max(0, Math.min(100, Number(item.start) / horizon * 100))}%`;
    segment.style.width = `${Math.max(0, Math.min(100, (Number(item.end) - Number(item.start)) / horizon * 100))}%`;
    segment.title = `${formatInstant(data.start, item.start)} – ${formatInstant(data.start, item.end)}`;
    intervals.append(segment);
  }
  const requested = document.querySelector("#timeline-request");
  requested.style.width = `${Math.min(100, Number(data.duration_seconds) / horizon * 100)}%`;
  requested.title = "Periodo richiesto";
  const axis = document.querySelector("#timeline-axis");
  axis.replaceChildren();
  [0, .25, .5, .75, 1].forEach((part) => {
    const label = document.createElement("span");
    label.textContent = formatClock(data.start, horizon * part);
    axis.append(label);
  });
  document.querySelector("#timeline-date").textContent = `${formatInstant(data.start, 0, false)} → ${formatInstant(data.start, horizon, false)}`;
  document.querySelector("#timeline").setAttribute(
    "aria-label",
    `${(data.intervals || []).length} intervalli visibili nelle 24 ore. Periodo richiesto: ${formatDuration(data.duration_seconds)}.`
  );
}

function svgElement(name, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function renderTrajectory(data, payload) {
  const host = document.querySelector("#trajectory");
  host.replaceChildren();
  const samples = Array.isArray(data.samples) ? data.samples : [];
  if (!samples.length) {
    const note = document.createElement("p");
    note.className = "empty-intervals";
    note.textContent = "Traiettoria non disponibile.";
    host.append(note);
    return;
  }
  const width = 700;
  const height = 142;
  const left = 30;
  const right = 8;
  const top = 6;
  const bottom = 19;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const minimumSampleAltitude = Math.min(...samples.map((sample) => Number(sample.alt)).filter(Number.isFinite));
  const axisBottom = Math.min(0, Math.floor(minimumSampleAltitude / 30) * 30);
  const axisSpan = 90 - axisBottom;
  const x = (offset) => left + Math.max(0, Math.min(1, offset / (Number(data.horizon_seconds) || HORIZON_SECONDS))) * plotWidth;
  const y = (alt) => top + (90 - Math.max(axisBottom, Math.min(90, alt))) / axisSpan * plotHeight;
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, class: "trajectory-svg", role: "img", "aria-labelledby": "trajectory-svg-title trajectory-svg-desc" });
  const title = svgElement("title", { id: "trajectory-svg-title" });
  title.textContent = "Traiettoria dell’altezza nelle 24 ore";
  const desc = svgElement("desc", { id: "trajectory-svg-desc" });
  desc.textContent = `Altezza geometrica dell’oggetto e fascia visibile tra ${payload.min_alt} e ${payload.max_alt} gradi.`;
  svg.append(title, desc);
  svg.append(svgElement("rect", { x: left, y: y(payload.max_alt), width: plotWidth, height: Math.max(1, y(payload.min_alt) - y(payload.max_alt)), class: "trajectory-band" }));
  for (let altitude = axisBottom; altitude <= 90; altitude += 30) {
    svg.append(svgElement("line", { x1: left, y1: y(altitude), x2: width - right, y2: y(altitude), class: "trajectory-grid" }));
    const label = svgElement("text", { x: 0, y: y(altitude) + 3, class: "trajectory-axis-label" });
    label.textContent = `${altitude}°`;
    svg.append(label);
  }
  const points = samples.map((sample) => `${x(Number(sample.offset)).toFixed(2)},${y(Number(sample.alt)).toFixed(2)}`).join(" ");
  svg.append(svgElement("polyline", { points, class: "trajectory-line" }));
  host.append(svg);
}

function renderIntervals(data) {
  const list = document.querySelector("#interval-list");
  list.replaceChildren();
  const items = data.intervals || [];
  document.querySelector("#interval-count").textContent = `${items.length} ${items.length === 1 ? "intervallo" : "intervalli"}`;
  if (!items.length) {
    const empty = document.createElement("li");
    empty.className = "empty-intervals";
    empty.textContent = "Nessun intervallo rispetta insieme balcone e buio astronomico.";
    list.append(empty);
    return;
  }
  items.forEach((item, index) => {
    const row = document.createElement("li");
    const number = document.createElement("span");
    number.className = "interval-index";
    number.textContent = String(index + 1).padStart(2, "0");
    const time = document.createElement("span");
    time.className = "interval-time";
    time.textContent = `${formatInstant(data.start, item.start)} – ${formatInstant(data.start, item.end)}`;
    const duration = document.createElement("span");
    duration.className = "interval-duration";
    duration.textContent = formatDuration(Number(item.end) - Number(item.start));
    row.append(number, time, duration);
    list.append(row);
  });
}

function azimuthVisible(azimuth, start, end) {
  if (start === 0 && end === 360) return true;
  const az = ((azimuth % 360) + 360) % 360;
  const from = start % 360;
  const to = end % 360;
  return from < to ? az >= from && az <= to : az >= from || az <= to;
}

function renderReasons(data, payload) {
  const host = document.querySelector("#reason-list");
  host.replaceChildren();
  const requested = (data.samples || []).filter((sample) => Number(sample.offset) <= Number(data.duration_seconds));
  const sampledReasons = [
    ["Sotto l’altezza minima", requested.some((sample) => Number(sample.alt) < payload.min_alt)],
    ["Sopra l’altezza massima", requested.some((sample) => Number(sample.alt) > payload.max_alt)],
    ["Fuori dal settore di azimut", requested.some((sample) => !azimuthVisible(Number(sample.az), payload.az_start, payload.az_end))],
    ["Sole sopra −18°", requested.some((sample) => Number(sample.sun_alt) > -18)],
  ];
  const statusReason = {
    full: "Tutti i criteri rispettati nel periodo richiesto",
    partial: "Il periodo richiesto è visibile solo in parte",
    none: "Il periodo richiesto non contiene una finestra continua completa",
  }[data.status] || "Risultato non riconosciuto";
  const reasons = [[statusReason, true], ...sampledReasons.map(([label, active]) => [`Campioni ogni 5 minuti: ${label}`, active])];
  reasons.forEach(([label, active]) => {
    if (!active) return;
    const chip = document.createElement("span");
    chip.className = "reason-chip active";
    chip.textContent = label;
    host.append(chip);
  });
}

function renderNotes(data) {
  const list = document.querySelector("#method-notes");
  list.replaceChildren();
  (data.notes || []).forEach((note) => {
    const item = document.createElement("li");
    item.textContent = String(note);
    list.append(item);
  });
}

function renderResult(data, payload) {
  emptyResult.hidden = true;
  resultError.hidden = true;
  resultContent.hidden = false;
  resultContent.classList.remove("is-stale");
  staleBadge.hidden = true;
  hasResult = true;

  const summary = document.querySelector("#result-summary");
  summary.className = `result-summary ${data.status}`;
  document.querySelector("#result-object").textContent = data.object?.name || payload.object;
  const label = statusLabel(data.status);
  document.querySelector("#result-status").textContent = label;
  document.querySelector("#result-period").textContent = `${formatInstant(data.start, 0)} – ${formatInstant(data.start, data.duration_seconds)}`;
  document.querySelector("#visible-duration").textContent = `${formatDuration(data.requested_visible_seconds)} su ${formatDuration(data.duration_seconds)}`;
  document.querySelector("#longest-duration").textContent = formatDuration(data.longest_visible_seconds);

  const windowCard = document.querySelector("#first-window-card");
  const windowTitle = document.querySelector("#first-window-title");
  const windowTime = document.querySelector("#first-window-time");
  const windowNote = document.querySelector("#first-window-note");
  if (data.first_window) {
    windowCard.classList.remove("no-window");
    windowTitle.textContent = "Prima finestra completa";
    windowTime.textContent = `${formatInstant(data.start, data.first_window.start)} – ${formatInstant(data.start, data.first_window.end)}`;
    windowNote.textContent = Number(data.first_window.start) === 0
      ? "Coincide con l’inizio richiesto. Gli estremi includono i secondi calcolati."
      : "Prima partenza utile nelle 24 ore analizzate; gli estremi includono i secondi calcolati.";
  } else {
    windowCard.classList.add("no-window");
    windowTitle.textContent = "Nessuna soluzione nelle 24 ore analizzate";
    windowTime.textContent = "Non esiste un singolo intervallo continuo della durata richiesta.";
    windowNote.textContent = "Intervalli più brevi possono comunque comparire qui sotto.";
  }

  renderTimeline(data);
  renderTrajectory(data, payload);
  renderIntervals(data);
  renderReasons(data, payload);
  renderNotes(data);
  resultLive.textContent = `${data.object?.name || payload.object}: ${label}.`;
}

function showResultError(message) {
  resultError.textContent = message;
  resultError.hidden = false;
  if (hasResult) markStale();
  else emptyResult.hidden = false;
  resultLive.textContent = message;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!connected) {
    setConnected(false, "Verifica di nuovo la connessione a SkyChart prima del calcolo.");
    verifyButton.focus();
    return;
  }
  if (!validateForm()) return;

  const payload = currentPayload();
  calculationRunning = true;
  fields.disabled = true;
  setButtonLoading(calculateButton, true, "Calcolo in corso…");
  resultError.hidden = true;
  resultLive.textContent = "Calcolo in corso. SkyChart sta preparando le prossime 24 ore.";

  try {
    const response = await fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await readJson(response);
    if (!response.ok) {
      const error = new Error(data.error || "Calcolo non riuscito.");
      error.code = data.code;
      throw error;
    }
    renderResult(data, payload);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Calcolo non riuscito. Riprova.";
    showResultError(message);
    if (error.code === "connection") {
      setConnected(false, "Connessione a SkyChart interrotta. Verificala e riprova.");
    }
  } finally {
    calculationRunning = false;
    fields.disabled = !connected;
    setButtonLoading(calculateButton, false, "");
  }
});
