"use strict";

const DEFAULT_TIME_ZONE = "Europe/Rome";
const HORIZON_SECONDS = 86400;
const SEARCH_DELAY_MS = 250;

const form = document.querySelector("#planner-form");
const fields = document.querySelector("#planner-fields");
const verifyButton = document.querySelector("#verify-connection");
const calculateButton = document.querySelector("#calculate");
const saveSiteButton = document.querySelector("#save-site");
const detectLocationButton = document.querySelector("#detect-location");
const connectionStatus = document.querySelector("#connection-status");
const headerConnection = document.querySelector("#header-connection");
const unlockNote = document.querySelector("#unlock-note");
const formError = document.querySelector("#form-error");
const resultError = document.querySelector("#result-error");
const emptyResult = document.querySelector("#empty-result");
const resultContent = document.querySelector("#result-content");
const resultLive = document.querySelector("#result-live");
const staleBadge = document.querySelector("#stale-badge");
const objectInput = document.querySelector("#object");
const objectResults = document.querySelector("#object-results");
const objectSearchStatus = document.querySelector("#object-search-status");
const siteStatus = document.querySelector("#site-status");
const timezoneInput = document.querySelector("#timezone");
const startInput = document.querySelector("#start");

let catalogReady = false;
let siteLoaded = false;
let hasResult = false;
let calculationRunning = false;
let selectedObject = null;
let objectOptions = [];
let activeObjectIndex = -1;
let searchTimer = null;
let searchGeneration = 0;
let proposedLocation = null;

function localDateAtTenPm(timeZone = DEFAULT_TIME_ZONE) {
  let formatter;
  try {
    formatter = new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    formatter = new Intl.DateTimeFormat("en-CA", {
      timeZone: DEFAULT_TIME_ZONE,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  }
  const parts = formatter.formatToParts(new Date());
  const part = (type) => parts.find((item) => item.type === type)?.value;
  return `${part("year")}-${part("month")}-${part("day")}T22:00`;
}

function setButtonLoading(button, isLoading, text) {
  button.disabled = isLoading;
  button.classList.toggle("loading", isLoading);
  const label = button.querySelector(".button-label");
  if (label) {
    if (!label.dataset.idle) label.dataset.idle = label.textContent;
    label.textContent = isLoading ? text : label.dataset.idle;
  }
  button.setAttribute("aria-busy", String(isLoading));
}

function updatePlannerAvailability() {
  fields.disabled = !catalogReady || !siteLoaded || calculationRunning;
  if (!siteLoaded) {
    unlockNote.classList.remove("unlocked");
    unlockNote.textContent = "Caricamento della postazione locale…";
  } else if (catalogReady) {
    unlockNote.classList.add("unlocked");
    unlockNote.textContent = "Cataloghi pronti. Il pianificatore è disponibile.";
  } else {
    unlockNote.classList.remove("unlocked");
    unlockNote.textContent = "Il catalogo locale deve essere disponibile per usare il pianificatore.";
  }
}

function catalogLabel(id) {
  return {
    messier: "M",
    ngc: "NGC",
    ic: "IC",
    sh2: "Sh2",
    vdb: "vdB",
    ldn: "LDN",
  }[String(id).toLowerCase()] || String(id);
}

function setCatalogChecking() {
  catalogReady = false;
  headerConnection.classList.remove("connected", "failed");
  headerConnection.querySelector("span:last-child").textContent = "Controllo cataloghi…";
  connectionStatus.className = "status-message";
  connectionStatus.textContent = "Controllo del catalogo locale in corso…";
  document.querySelector("#catalog-version").textContent = "Versione in controllo";
  document.querySelector("#catalog-summary").textContent = "Controllo dei cataloghi locali…";
  updatePlannerAvailability();
}

function setCatalogState(data) {
  catalogReady = Boolean(data?.ready);
  headerConnection.classList.toggle("connected", catalogReady);
  headerConnection.classList.toggle("failed", !catalogReady);
  headerConnection.querySelector("span:last-child").textContent = catalogReady
    ? "Cataloghi pronti"
    : "Cataloghi non disponibili";
  connectionStatus.className = `status-message ${catalogReady ? "success" : "error"}`;
  connectionStatus.textContent = data?.message || (catalogReady
    ? "Catalogo locale pronto."
    : "Catalogo locale non disponibile.");
  document.querySelector("#catalog-version").textContent = catalogReady && data.version
    ? `Versione ${data.version}`
    : "Versione non disponibile";
  const catalogs = Array.isArray(data?.catalogs) ? data.catalogs : [];
  document.querySelector("#catalog-summary").textContent = catalogs.length
    ? catalogs.map((catalog) => `${catalogLabel(catalog.id)} ${catalog.count}`).join(" · ")
    : "Nessun catalogo disponibile";
  verifyButton.hidden = catalogReady;
  updatePlannerAvailability();
}

async function readJson(response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    throw new Error("Il server ha restituito una risposta non leggibile.");
  }
}

async function loadCatalogStatus({retry = false} = {}) {
  setCatalogChecking();
  if (retry) {
    verifyButton.hidden = false;
    setButtonLoading(verifyButton, true, "Controllo in corso…");
  } else {
    verifyButton.hidden = true;
  }
  try {
    const response = await fetch("/api/status", {headers: {Accept: "application/json"}});
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "Controllo del catalogo non riuscito.");
    setCatalogState(data);
  } catch (error) {
    setCatalogState({
      ready: false,
      version: "",
      catalogs: [],
      message: error instanceof Error ? error.message : "Catalogo locale non disponibile.",
    });
  } finally {
    if (retry) setButtonLoading(verifyButton, false, "");
  }
}

function setSiteStatus(message, kind = "") {
  siteStatus.className = `site-status ${kind}`;
  siteStatus.textContent = message;
}

function field(selector) {
  return document.querySelector(selector);
}

function applySite(site) {
  field("#site-name").value = String(site.name);
  field("#latitude").value = String(site.latitude);
  field("#longitude").value = String(site.longitude);
  timezoneInput.value = String(site.timezone);
  field("#min-alt").value = String(site.min_alt);
  field("#max-alt").value = String(site.max_alt);
  field("#az-start").value = String(site.az_start);
  field("#az-end").value = String(site.az_end);
  updateTimeZoneNote();
}

async function loadSite() {
  try {
    const response = await fetch("/api/site", {headers: {Accept: "application/json"}});
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "Lettura della postazione non riuscita.");
    if (data.site) {
      applySite(data.site);
      setSiteStatus(`Postazione ${data.site.name} caricata.`, "success");
    } else {
      setSiteStatus("Nessuna postazione salvata. I valori di Chiusanico sono un esempio modificabile.");
    }
  } catch (error) {
    setSiteStatus(error instanceof Error ? error.message : "Postazione salvata non leggibile.", "error");
  } finally {
    siteLoaded = true;
    if (!field("#start").value) field("#start").value = localDateAtTenPm(timezoneInput.value.trim());
    updatePlannerAvailability();
  }
}

verifyButton.addEventListener("click", () => loadCatalogStatus({retry: true}));

function numberValue(selector) {
  const value = field(selector).value.trim();
  return value === "" ? NaN : Number(value);
}

function clearFieldErrors() {
  form.querySelectorAll("[aria-invalid='true']").forEach((input) => input.removeAttribute("aria-invalid"));
}

function clearFormErrors() {
  formError.hidden = true;
  formError.textContent = "";
  clearFieldErrors();
}

function showFormError(message, invalidInput) {
  formError.textContent = message;
  formError.hidden = false;
  if (invalidInput) {
    invalidInput.setAttribute("aria-invalid", "true");
    invalidInput.focus();
  }
}

function validTimeZone(value) {
  if (!value.trim()) return false;
  try {
    new Intl.DateTimeFormat("it-IT", {timeZone: value.trim()}).format();
    return true;
  } catch {
    return false;
  }
}

function validateRules(rules) {
  clearFormErrors();
  for (const [selector, valid, message] of rules) {
    const input = field(selector);
    if (!valid(input.value)) {
      showFormError(message, input);
      return false;
    }
  }
  const minAlt = numberValue("#min-alt");
  const maxAlt = numberValue("#max-alt");
  if (maxAlt <= minAlt) {
    showFormError("L’altezza massima deve essere maggiore di quella minima.", field("#max-alt"));
    return false;
  }
  const azStart = numberValue("#az-start");
  const azEnd = numberValue("#az-end");
  const isWholeHorizon = azStart === 0 && azEnd === 360;
  if (!isWholeHorizon && azStart % 360 === azEnd % 360) {
    showFormError("Gli azimut iniziale e finale uguali sono ambigui. Usa 0° → 360° per tutto l’orizzonte.", field("#az-end"));
    return false;
  }
  return true;
}

function siteRules() {
  return [
    ["#site-name", (value) => value.trim().length > 0 && value.trim().length <= 80, "Inserisci un nome per la postazione (massimo 80 caratteri)."],
    ["#latitude", (value) => Number.isFinite(Number(value)) && Number(value) >= -90 && Number(value) <= 90, "La latitudine deve essere compresa tra −90° e 90°."],
    ["#longitude", (value) => Number.isFinite(Number(value)) && Number(value) >= -180 && Number(value) <= 180, "La longitudine deve essere compresa tra −180° e 180°."],
    ["#timezone", validTimeZone, "Inserisci un fuso IANA disponibile, per esempio Europe/Rome."],
    ["#min-alt", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 90, "L’altezza minima deve essere compresa tra 0° e 90°."],
    ["#max-alt", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 90, "L’altezza massima deve essere compresa tra 0° e 90°."],
    ["#az-start", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 360, "L’azimut iniziale deve essere compreso tra 0° e 360°."],
    ["#az-end", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 360, "L’azimut finale deve essere compreso tra 0° e 360°."],
  ];
}

function validateForm() {
  return validateRules([
    ["#object", (value) => value.trim().length > 0, "Inserisci la sigla dell’oggetto."],
    ["#latitude", (value) => Number.isFinite(Number(value)) && Number(value) >= -90 && Number(value) <= 90, "La latitudine deve essere compresa tra −90° e 90°."],
    ["#longitude", (value) => Number.isFinite(Number(value)) && Number(value) >= -180 && Number(value) <= 180, "La longitudine deve essere compresa tra −180° e 180°."],
    ["#start", (value) => value !== "", "Scegli una data e un’ora della postazione."],
    ["#timezone", validTimeZone, "Inserisci un fuso IANA disponibile, per esempio Europe/Rome."],
    ["#duration", (value) => Number.isFinite(Number(value)) && Number(value) > 0 && Number(value) <= 1440, "La durata deve essere maggiore di 0 e non superare 1.440 minuti."],
    ["#min-alt", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 90, "L’altezza minima deve essere compresa tra 0° e 90°."],
    ["#max-alt", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 90, "L’altezza massima deve essere compresa tra 0° e 90°."],
    ["#az-start", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 360, "L’azimut iniziale deve essere compreso tra 0° e 360°."],
    ["#az-end", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 360, "L’azimut finale deve essere compreso tra 0° e 360°."],
  ]);
}

function currentSitePayload() {
  return {
    name: field("#site-name").value.trim(),
    latitude: numberValue("#latitude"),
    longitude: numberValue("#longitude"),
    timezone: timezoneInput.value.trim(),
    min_alt: numberValue("#min-alt"),
    max_alt: numberValue("#max-alt"),
    az_start: numberValue("#az-start"),
    az_end: numberValue("#az-end"),
  };
}

function currentPayload() {
  return {
    object: selectedObject?.name || objectInput.value.trim(),
    latitude: numberValue("#latitude"),
    longitude: numberValue("#longitude"),
    start: field("#start").value,
    timezone: timezoneInput.value.trim(),
    duration_minutes: numberValue("#duration"),
    min_alt: numberValue("#min-alt"),
    max_alt: numberValue("#max-alt"),
    az_start: numberValue("#az-start"),
    az_end: numberValue("#az-end"),
  };
}

async function saveSite() {
  setSiteStatus("");
  if (!validateRules(siteRules())) return;
  setButtonLoading(saveSiteButton, true, "Salvataggio…");
  try {
    const response = await fetch("/api/site", {
      method: "POST",
      headers: {"Content-Type": "application/json", Accept: "application/json"},
      body: JSON.stringify(currentSitePayload()),
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "Salvataggio postazione non riuscito.");
    setSiteStatus(`Postazione ${data.site.name} salvata.`, "success");
  } catch (error) {
    setSiteStatus(error instanceof Error ? error.message : "Salvataggio postazione non riuscito.", "error");
  } finally {
    setButtonLoading(saveSiteButton, false, "");
  }
}

saveSiteButton.addEventListener("click", saveSite);

function markStale() {
  if (!hasResult || calculationRunning) return;
  staleBadge.hidden = false;
  resultContent.classList.add("is-stale");
}

function updateTimeZoneNote() {
  field("#time-zone-note").textContent = timezoneInput.value.trim() || "—";
}

function closeObjectList() {
  objectResults.hidden = true;
  objectInput.setAttribute("aria-expanded", "false");
  objectInput.removeAttribute("aria-activedescendant");
  activeObjectIndex = -1;
  objectResults.querySelectorAll("[aria-selected='true']").forEach((option) => option.setAttribute("aria-selected", "false"));
}

function optionAliases(item) {
  return (Array.isArray(item.aliases) ? item.aliases : []).filter(
    (alias) => alias.toLocaleUpperCase("it-IT") !== String(item.name).toLocaleUpperCase("it-IT")
  );
}

function renderObjectOptions(items) {
  objectOptions = items;
  objectResults.replaceChildren();
  activeObjectIndex = -1;
  if (!items.length) {
    closeObjectList();
    objectSearchStatus.textContent = "Nessun oggetto trovato";
    return;
  }
  items.forEach((item, index) => {
    const option = document.createElement("li");
    option.id = `object-option-${searchGeneration}-${index}`;
    option.className = "object-option";
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", "false");
    const name = document.createElement("strong");
    name.textContent = item.name;
    option.append(name);
    if (item.type) {
      const type = document.createElement("span");
      type.className = "object-type";
      type.textContent = item.type;
      option.append(type);
    }
    const aliases = optionAliases(item);
    if (aliases.length) {
      const alias = document.createElement("span");
      alias.className = "object-aliases";
      alias.textContent = aliases.join(", ");
      option.append(alias);
    }
    option.addEventListener("mousedown", (event) => event.preventDefault());
    option.addEventListener("click", () => selectObject(index));
    objectResults.append(option);
  });
  objectResults.hidden = false;
  objectInput.setAttribute("aria-expanded", "true");
  objectSearchStatus.textContent = `${items.length} ${items.length === 1 ? "risultato disponibile" : "risultati disponibili"}. Scegli con frecce e Invio oppure con un clic.`;
}

function setActiveObject(index) {
  if (!objectOptions.length) return;
  activeObjectIndex = (index + objectOptions.length) % objectOptions.length;
  objectResults.querySelectorAll("[role='option']").forEach((option, optionIndex) => {
    option.setAttribute("aria-selected", String(optionIndex === activeObjectIndex));
  });
  const active = objectResults.children[activeObjectIndex];
  objectInput.setAttribute("aria-activedescendant", active.id);
  active.scrollIntoView({block: "nearest"});
}

function selectObject(index) {
  const item = objectOptions[index];
  if (!item) return;
  selectedObject = item;
  objectInput.value = item.name;
  objectInput.removeAttribute("aria-invalid");
  const aliases = optionAliases(item);
  objectSearchStatus.textContent = aliases.length
    ? `Selezionato ${item.name}. Alias: ${aliases.join(", ")}.`
    : `Selezionato ${item.name}.`;
  searchGeneration += 1;
  closeObjectList();
  markStale();
}

async function searchObjects(query, generation) {
  try {
    const response = await fetch(`/api/objects?q=${encodeURIComponent(query)}`, {headers: {Accept: "application/json"}});
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "Ricerca nel catalogo non riuscita.");
    if (generation !== searchGeneration || objectInput.value.trim() !== query) return;
    renderObjectOptions(Array.isArray(data.objects) ? data.objects : []);
  } catch (error) {
    if (generation !== searchGeneration) return;
    closeObjectList();
    objectSearchStatus.textContent = error instanceof Error ? error.message : "Ricerca nel catalogo non riuscita.";
  }
}

function scheduleObjectSearch() {
  window.clearTimeout(searchTimer);
  searchGeneration += 1;
  objectOptions = [];
  objectResults.replaceChildren();
  closeObjectList();
  const generation = searchGeneration;
  const query = objectInput.value.trim();
  if (!query) {
    objectSearchStatus.textContent = "";
    return;
  }
  objectSearchStatus.textContent = "Ricerca nel catalogo…";
  searchTimer = window.setTimeout(() => searchObjects(query, generation), SEARCH_DELAY_MS);
}

objectInput.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeObjectList();
    return;
  }
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    if (!objectResults.hidden && objectOptions.length) {
      event.preventDefault();
      const delta = event.key === "ArrowDown" ? 1 : -1;
      setActiveObject(activeObjectIndex < 0 ? (delta > 0 ? 0 : objectOptions.length - 1) : activeObjectIndex + delta);
    }
    return;
  }
  if (event.key === "Enter" && !objectResults.hidden && activeObjectIndex >= 0) {
    event.preventDefault();
    selectObject(activeObjectIndex);
  }
});

form.addEventListener("input", (event) => {
  if (!(event.target instanceof HTMLElement)) return;
  event.target.removeAttribute("aria-invalid");
  if (!formError.hidden) {
    formError.hidden = true;
    formError.textContent = "";
  }
  if (event.target === objectInput) {
    selectedObject = null;
    scheduleObjectSearch();
  }
  if (event.target === timezoneInput) updateTimeZoneNote();
  markStale();
});

function showLocationProposal(position) {
  proposedLocation = {
    latitude: Number(position.coords.latitude),
    longitude: Number(position.coords.longitude),
    accuracy: Number(position.coords.accuracy),
  };
  field("#proposal-latitude").textContent = `Latitudine ${proposedLocation.latitude.toFixed(4)}°`;
  field("#proposal-longitude").textContent = `Longitudine ${proposedLocation.longitude.toFixed(4)}°`;
  field("#proposal-accuracy").textContent = `Accuratezza ± ${Math.round(proposedLocation.accuracy)} m`;
  field("#location-proposal").hidden = false;
  setSiteStatus("Posizione rilevata. Conferma per usarla.");
}

function locationErrorMessage(error) {
  if (error?.code === error?.PERMISSION_DENIED || error?.code === 1) {
    return "Permesso di geolocalizzazione negato. I valori manuali restano disponibili.";
  }
  if (error?.code === error?.TIMEOUT || error?.code === 3) {
    return "Tempo scaduto durante la geolocalizzazione. I valori manuali restano disponibili.";
  }
  return "Posizione non disponibile. I valori manuali restano disponibili.";
}

function requestLocation() {
  setSiteStatus("");
  if (!navigator.geolocation?.getCurrentPosition) {
    setSiteStatus("Geolocalizzazione non disponibile in questo browser. I valori manuali restano disponibili.", "error");
    return;
  }
  setButtonLoading(detectLocationButton, true, "Rilevamento…");
  navigator.geolocation.getCurrentPosition(
    (position) => {
      setButtonLoading(detectLocationButton, false, "");
      showLocationProposal(position);
    },
    (error) => {
      setButtonLoading(detectLocationButton, false, "");
      setSiteStatus(locationErrorMessage(error), "error");
    },
    {enableHighAccuracy: true, timeout: 10000, maximumAge: 0}
  );
}

function cancelLocationProposal() {
  proposedLocation = null;
  field("#location-proposal").hidden = true;
  setSiteStatus("Posizione rilevata annullata. I valori manuali non sono cambiati.");
}

function acceptLocationProposal() {
  if (!proposedLocation) return;
  field("#latitude").value = String(proposedLocation.latitude);
  field("#longitude").value = String(proposedLocation.longitude);
  field("#latitude").removeAttribute("aria-invalid");
  field("#longitude").removeAttribute("aria-invalid");
  proposedLocation = null;
  field("#location-proposal").hidden = true;
  setSiteStatus("Posizione applicata ai campi. Salva la postazione se vuoi conservarla.", "success");
  markStale();
}

detectLocationButton.addEventListener("click", requestLocation);
field("#cancel-location").addEventListener("click", cancelLocationProposal);
field("#accept-location").addEventListener("click", acceptLocationProposal);

function formatInstant(startIso, offsetSeconds, timeZone = DEFAULT_TIME_ZONE, includeWeekday = true) {
  const instant = new Date(new Date(startIso).getTime() + Number(offsetSeconds) * 1000);
  const options = {
    timeZone,
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

function formatClock(startIso, offsetSeconds, timeZone = DEFAULT_TIME_ZONE) {
  const instant = new Date(new Date(startIso).getTime() + Number(offsetSeconds) * 1000);
  return new Intl.DateTimeFormat("it-IT", {
    timeZone,
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

function renderDarkness(data) {
  const darkness = data.darkness || {at_start: false, intervals: [], events: []};
  const events = Array.isArray(darkness.events) ? darkness.events : [];
  const intervals = Array.isArray(darkness.intervals) ? darkness.intervals : [];
  const horizon = Number(data.horizon_seconds) || HORIZON_SECONDS;
  const renderEvents = (host, kind) => {
    const matching = events.filter((event) => event.kind === kind);
    host.replaceChildren();
    if (!matching.length) {
      host.textContent = "Non presente nelle 24 h";
      return;
    }
    matching.forEach((event) => {
      const value = document.createElement("span");
      value.dataset.eventKind = kind;
      value.textContent = formatInstant(data.start, event.offset, data.timezone);
      host.append(value);
    });
  };
  renderEvents(field("#darkness-start"), "night_start");
  renderEvents(field("#darkness-end"), "night_end");

  const coversWholeHorizon = intervals.length === 1
    && Number(intervals[0].start) <= 0
    && Number(intervals[0].end) >= horizon
    && events.length === 0;
  let summary = "Buio astronomico presente nelle 24 h";
  if (coversWholeHorizon) {
    summary = "Buio astronomico per tutte le 24 h";
  } else if (!intervals.length && !events.length && !darkness.at_start) {
    summary = "Nessun buio astronomico nelle 24 h";
  } else if (darkness.at_start) {
    summary = "Le 24 ore iniziano già nel buio astronomico";
  } else if (intervals.some((interval) => Number(interval.end) >= horizon)) {
    summary = "Le 24 ore terminano nel buio astronomico";
  }
  field("#darkness-summary").textContent = summary;
}

function renderTimeline(data) {
  const intervals = field("#timeline-intervals");
  intervals.replaceChildren();
  const horizon = Number(data.horizon_seconds) || HORIZON_SECONDS;
  for (const item of data.intervals || []) {
    const segment = document.createElement("span");
    segment.className = "timeline-segment";
    segment.style.left = `${Math.max(0, Math.min(100, Number(item.start) / horizon * 100))}%`;
    segment.style.width = `${Math.max(0, Math.min(100, (Number(item.end) - Number(item.start)) / horizon * 100))}%`;
    segment.title = `${formatInstant(data.start, item.start, data.timezone)} – ${formatInstant(data.start, item.end, data.timezone)}`;
    intervals.append(segment);
  }
  const requested = field("#timeline-request");
  requested.style.width = `${Math.min(100, Number(data.duration_seconds) / horizon * 100)}%`;
  requested.title = "Periodo richiesto";
  const axis = field("#timeline-axis");
  axis.replaceChildren();
  [0, .25, .5, .75, 1].forEach((part) => {
    const label = document.createElement("span");
    label.textContent = formatClock(data.start, horizon * part, data.timezone);
    axis.append(label);
  });
  field("#timeline-date").textContent = `${formatInstant(data.start, 0, data.timezone, false)} → ${formatInstant(data.start, horizon, data.timezone, false)} · ${data.timezone}`;
  field("#timeline").setAttribute(
    "aria-label",
    `${(data.intervals || []).length} intervalli visibili nelle 24 ore. Periodo richiesto: ${formatDuration(data.duration_seconds)}. Fuso ${data.timezone}.`
  );
}

function svgElement(name, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function renderTrajectory(data, payload) {
  const host = field("#trajectory");
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
  const altitudes = samples.map((sample) => Number(sample.alt)).filter(Number.isFinite);
  const minimumSampleAltitude = altitudes.length ? Math.min(...altitudes) : 0;
  const axisBottom = Math.min(0, Math.floor(minimumSampleAltitude / 30) * 30);
  const axisSpan = 90 - axisBottom;
  const x = (offset) => left + Math.max(0, Math.min(1, offset / (Number(data.horizon_seconds) || HORIZON_SECONDS))) * plotWidth;
  const y = (alt) => top + (90 - Math.max(axisBottom, Math.min(90, alt))) / axisSpan * plotHeight;
  const svg = svgElement("svg", {viewBox: `0 0 ${width} ${height}`, class: "trajectory-svg", role: "img", "aria-labelledby": "trajectory-svg-title trajectory-svg-desc"});
  const title = svgElement("title", {id: "trajectory-svg-title"});
  title.textContent = "Traiettoria dell’altezza nelle 24 ore";
  const desc = svgElement("desc", {id: "trajectory-svg-desc"});
  desc.textContent = `Altezza geometrica dell’oggetto e fascia visibile tra ${payload.min_alt} e ${payload.max_alt} gradi.`;
  svg.append(title, desc);
  svg.append(svgElement("rect", {x: left, y: y(payload.max_alt), width: plotWidth, height: Math.max(1, y(payload.min_alt) - y(payload.max_alt)), class: "trajectory-band"}));
  for (let altitude = axisBottom; altitude <= 90; altitude += 30) {
    svg.append(svgElement("line", {x1: left, y1: y(altitude), x2: width - right, y2: y(altitude), class: "trajectory-grid"}));
    const label = svgElement("text", {x: 0, y: y(altitude) + 3, class: "trajectory-axis-label"});
    label.textContent = `${altitude}°`;
    svg.append(label);
  }
  const points = samples.map((sample) => `${x(Number(sample.offset)).toFixed(2)},${y(Number(sample.alt)).toFixed(2)}`).join(" ");
  svg.append(svgElement("polyline", {points, class: "trajectory-line"}));
  host.append(svg);
}

function renderIntervals(data) {
  const list = field("#interval-list");
  list.replaceChildren();
  const items = data.intervals || [];
  field("#interval-count").textContent = `${items.length} ${items.length === 1 ? "intervallo" : "intervalli"}`;
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
    time.textContent = `${formatInstant(data.start, item.start, data.timezone)} – ${formatInstant(data.start, item.end, data.timezone)}`;
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
  const host = field("#reason-list");
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
  const list = field("#method-notes");
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

  if (data.object?.name) {
    objectInput.value = data.object.name;
    selectedObject = data.object;
    const aliases = optionAliases(data.object);
    objectSearchStatus.textContent = aliases.length
      ? `Risolto come ${data.object.name}. Alias: ${aliases.join(", ")}.`
      : `Risolto come ${data.object.name}.`;
  }
  const summary = field("#result-summary");
  summary.className = `result-summary ${data.status}`;
  field("#result-object").textContent = data.object?.name || payload.object;
  const label = statusLabel(data.status);
  field("#result-status").textContent = label;
  field("#result-period").textContent = `${formatInstant(data.start, 0, data.timezone)} – ${formatInstant(data.start, data.duration_seconds, data.timezone)}`;
  field("#visible-duration").textContent = `${formatDuration(data.requested_visible_seconds)} su ${formatDuration(data.duration_seconds)}`;
  field("#longest-duration").textContent = formatDuration(data.longest_visible_seconds);

  const windowCard = field("#first-window-card");
  const windowTitle = field("#first-window-title");
  const windowTime = field("#first-window-time");
  const windowNote = field("#first-window-note");
  if (data.first_window) {
    windowCard.classList.remove("no-window");
    windowTitle.textContent = "Prima finestra completa";
    windowTime.textContent = `${formatInstant(data.start, data.first_window.start, data.timezone)} – ${formatInstant(data.start, data.first_window.end, data.timezone)}`;
    windowNote.textContent = Number(data.first_window.start) === 0
      ? "Coincide con l’inizio richiesto. Gli estremi includono i secondi calcolati."
      : "Prima partenza utile nelle 24 ore analizzate; gli estremi includono i secondi calcolati.";
  } else {
    windowCard.classList.add("no-window");
    windowTitle.textContent = "Nessuna soluzione nelle 24 ore analizzate";
    windowTime.textContent = "Non esiste un singolo intervallo continuo della durata richiesta.";
    const edges = data.horizon_edges || {};
    windowNote.textContent = edges.start || edges.end
      ? "Un tratto tocca il limite delle 24 ore e può continuare oltre il periodo analizzato."
      : "Intervalli più brevi possono comunque comparire qui sotto.";
  }

  renderDarkness(data);
  renderTimeline(data);
  renderTrajectory(data, payload);
  renderIntervals(data);
  renderReasons(data, payload);
  renderNotes(data);
  resultLive.textContent = `${data.object?.name || payload.object}: ${label}. Orari nel fuso ${data.timezone}.`;
}

startInput.addEventListener("change", () => {
  window.setTimeout(() => {
    if (document.activeElement === startInput) startInput.blur();
  }, 0);
});

function showResultError(message) {
  resultError.textContent = message;
  resultError.hidden = false;
  if (hasResult) markStale();
  else emptyResult.hidden = false;
  resultLive.textContent = message;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!catalogReady) {
    setCatalogState({ready: false, message: "Catalogo locale non disponibile. Riprova il controllo.", version: "", catalogs: []});
    verifyButton.focus();
    return;
  }
  if (!validateForm()) return;

  const payload = currentPayload();
  window.clearTimeout(searchTimer);
  searchGeneration += 1;
  closeObjectList();
  calculationRunning = true;
  updatePlannerAvailability();
  setButtonLoading(calculateButton, true, "Calcolo in corso…");
  resultError.hidden = true;
  resultLive.textContent = "Calcolo locale delle prossime 24 ore in corso.";

  try {
    const response = await fetch("/api/check", {
      method: "POST",
      headers: {"Content-Type": "application/json", Accept: "application/json"},
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
    if (error.code === "object") {
      showFormError(message, objectInput);
      objectSearchStatus.textContent = message;
      if (hasResult) markStale();
    } else {
      showResultError(message);
    }
    if (error.code === "catalog") {
      setCatalogState({ready: false, message, version: "", catalogs: []});
    }
  } finally {
    calculationRunning = false;
    updatePlannerAvailability();
    setButtonLoading(calculateButton, false, "");
  }
});

updateTimeZoneNote();
setCatalogChecking();
Promise.allSettled([loadCatalogStatus(), loadSite()]);
