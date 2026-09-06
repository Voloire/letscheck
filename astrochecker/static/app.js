"use strict";

const DEFAULT_TIME_ZONE = "Europe/Rome";
const HORIZON_SECONDS = 86400;
const SEARCH_DELAY_MS = 250;

const form = document.querySelector("#planner-form");
const fields = document.querySelector("#planner-fields");
const verifyButton = document.querySelector("#verify-connection");
const calculateButton = document.querySelector("#calculate");
const ideasButton = document.querySelector("#ideas");
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
const resultsTitle = document.querySelector("#results-title");
const objectInput = document.querySelector("#object");
const objectResults = document.querySelector("#object-results");
const objectSearchStatus = document.querySelector("#object-search-status");
const siteStatus = document.querySelector("#site-status");
const timezoneInput = document.querySelector("#timezone");
const startInput = document.querySelector("#start");
const suggestionList = document.querySelector("#suggestion-list");
const suggestionsEmpty = document.querySelector("#suggestions-empty");
const acceptedPlan = document.querySelector("#accepted-plan");
const acceptedPlanSummary = document.querySelector("#accepted-plan-summary");
const ninaSequenceName = document.querySelector("#nina-sequence-name");
const exportAcceptedNina = document.querySelector("#export-accepted-nina");
const ninaExportStatus = document.querySelector("#nina-export-status");
const nightPlan = document.querySelector("#night-plan");
const nightBlocks = document.querySelector("#night-blocks");
const nightGaps = document.querySelector("#night-gaps");
const nightTimeline = document.querySelector("#night-timeline");

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
let selectedSuggestion = null;
let acceptedSuggestion = null;
let selectedResult = null;
let ninaExportRunning = false;

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
    unlockNote.textContent = "Loading your local site…";
  } else if (catalogReady) {
    unlockNote.classList.add("unlocked");
    unlockNote.textContent = "Catalogs are ready. The planner is available.";
  } else {
    unlockNote.classList.remove("unlocked");
    unlockNote.textContent = "The local catalog must be available before you can plan.";
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
  headerConnection.querySelector("span:last-child").textContent = "Checking catalogs…";
  connectionStatus.className = "status-message";
  connectionStatus.textContent = "Checking the local catalog…";
  document.querySelector("#catalog-version").textContent = "Versione in controllo";
  document.querySelector("#catalog-summary").textContent = "Controllo dei cataloghi locali…";
  updatePlannerAvailability();
}

function setCatalogState(data) {
  catalogReady = Boolean(data?.ready);
  headerConnection.classList.toggle("connected", catalogReady);
  headerConnection.classList.toggle("failed", !catalogReady);
  headerConnection.querySelector("span:last-child").textContent = catalogReady
    ? "Catalogs ready"
    : "Catalogs unavailable";
  connectionStatus.className = `status-message ${catalogReady ? "success" : "error"}`;
  connectionStatus.textContent = data?.message || (catalogReady
    ? "Local catalog ready."
    : "Local catalog unavailable.");
  document.querySelector("#catalog-version").textContent = catalogReady && data.version
    ? `Versione ${data.version}`
    : "Version unavailable";
  const catalogs = Array.isArray(data?.catalogs) ? data.catalogs : [];
  document.querySelector("#catalog-summary").textContent = catalogs.length
    ? catalogs.map((catalog) => `${catalogLabel(catalog.id)} ${catalog.count}`).join(" · ")
    : "No catalogs available";
  verifyButton.hidden = catalogReady;
  updatePlannerAvailability();
}

async function readJson(response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    throw new Error("The server returned an unreadable response.");
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
    if (!response.ok) throw new Error(data.error || "Catalog check failed.");
    setCatalogState(data);
  } catch (error) {
    setCatalogState({
      ready: false,
      version: "",
      catalogs: [],
      message: error instanceof Error ? error.message : "Local catalog unavailable.",
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
    if (!response.ok) throw new Error(data.error || "Could not load the saved site.");
    if (data.site) {
      applySite(data.site);
      setSiteStatus(`Site ${data.site.name} loaded.`, "success");
    } else {
      setSiteStatus("No saved site yet. The Chiusanico values are just editable examples.");
    }
  } catch (error) {
    setSiteStatus(error instanceof Error ? error.message : "Saved site could not be read.", "error");
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
    new Intl.DateTimeFormat("en-US", {timeZone: value.trim()}).format();
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
    showFormError("Matching start and end azimuths are ambiguous. Use 0° → 360° for the whole horizon.", field("#az-end"));
    return false;
  }
  return true;
}

function siteRules() {
  return [
    ["#site-name", (value) => value.trim().length > 0 && value.trim().length <= 80, "Enter a site name (up to 80 characters)."],
    ["#latitude", (value) => Number.isFinite(Number(value)) && Number(value) >= -90 && Number(value) <= 90, "Latitude must be between −90° and 90°."],
    ["#longitude", (value) => Number.isFinite(Number(value)) && Number(value) >= -180 && Number(value) <= 180, "Longitude must be between −180° and 180°."],
    ["#timezone", validTimeZone, "Enter a valid IANA time zone, such as Europe/Rome."],
    ["#min-alt", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 90, "L’altezza minima deve essere compresa tra 0° e 90°."],
    ["#max-alt", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 90, "L’altezza massima deve essere compresa tra 0° e 90°."],
    ["#az-start", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 360, "L’azimut iniziale deve essere compreso tra 0° e 360°."],
    ["#az-end", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 360, "L’azimut finale deve essere compreso tra 0° e 360°."],
  ];
}

function validateForm({requireObject = true} = {}) {
  const rules = [
    ["#latitude", (value) => Number.isFinite(Number(value)) && Number(value) >= -90 && Number(value) <= 90, "Latitude must be between −90° and 90°."],
    ["#longitude", (value) => Number.isFinite(Number(value)) && Number(value) >= -180 && Number(value) <= 180, "Longitude must be between −180° and 180°."],
    ["#start", (value) => value !== "", "Choose a site date and time."],
    ["#timezone", validTimeZone, "Enter a valid IANA time zone, such as Europe/Rome."],
    ["#duration", (value) => Number.isFinite(Number(value)) && Number(value) > 0 && Number(value) <= 1440, "Duration must be greater than 0 and no more than 1,440 minutes."],
    ["#min-alt", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 90, "L’altezza minima deve essere compresa tra 0° e 90°."],
    ["#max-alt", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 90, "L’altezza massima deve essere compresa tra 0° e 90°."],
    ["#az-start", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 360, "L’azimut iniziale deve essere compreso tra 0° e 360°."],
    ["#az-end", (value) => Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 360, "L’azimut finale deve essere compreso tra 0° e 360°."],
  ];
  if (requireObject) rules.unshift(["#object", (value) => value.trim().length > 0, "Enter the object ID."]);
  return validateRules(rules);
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
  setButtonLoading(saveSiteButton, true, "Saving…");
  try {
    const response = await fetch("/api/site", {
      method: "POST",
      headers: {"Content-Type": "application/json", Accept: "application/json"},
      body: JSON.stringify(currentSitePayload()),
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "Could not save the site.");
    setSiteStatus(`Site ${data.site.name} saved.`, "success");
  } catch (error) {
    setSiteStatus(error instanceof Error ? error.message : "Could not save the site.", "error");
  } finally {
    setButtonLoading(saveSiteButton, false, "");
  }
}

saveSiteButton.addEventListener("click", saveSite);

function markStale() {
  if (!hasResult || calculationRunning) return;
  staleBadge.hidden = false;
  resultContent.classList.add("is-stale");
  nightPlan.classList.add("is-stale");
  acceptedSuggestion = null;
  acceptedPlan.hidden = true;
  ninaExportStatus.textContent = "Recalculate before exporting this plan.";
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
  const values = [...(Array.isArray(item.common_names) ? item.common_names : []), ...(Array.isArray(item.related_ids) ? item.related_ids : []), ...(Array.isArray(item.aliases) ? item.aliases : [])];
  return [...new Set(values)].filter(
    (alias) => alias.toLocaleUpperCase("en-US") !== String(item.name).toLocaleUpperCase("en-US")
  );
}

function formatTargetLabel(item, fallback = "Target") {
  const name = item?.name || item?.object || fallback;
  const nickname = Array.isArray(item?.common_names) ? item.common_names[0] : "";
  return nickname && nickname.toLocaleUpperCase("en-US") !== String(name).toLocaleUpperCase("en-US")
    ? `${name} — ${nickname}`
    : name;
}

function renderObjectOptions(items) {
  objectOptions = items;
  objectResults.replaceChildren();
  activeObjectIndex = -1;
  if (!items.length) {
    closeObjectList();
    objectSearchStatus.textContent = "No objects found";
    return;
  }
  items.forEach((item, index) => {
    const option = document.createElement("li");
    option.id = `object-option-${searchGeneration}-${index}`;
    option.className = "object-option";
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", "false");
    const name = document.createElement("strong");
    name.textContent = formatTargetLabel(item);
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
  objectSearchStatus.textContent = `${items.length} ${items.length === 1 ? "result available" : "results available"}. Use the arrow keys and Enter, or click a result.`;
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
    ? `Selected ${formatTargetLabel(item)}. Aliases: ${aliases.join(", ")}.`
    : `Selected ${formatTargetLabel(item)}.`;
  searchGeneration += 1;
  closeObjectList();
  markStale();
}

async function searchObjects(query, generation) {
  try {
    const response = await fetch(`/api/objects?q=${encodeURIComponent(query)}`, {headers: {Accept: "application/json"}});
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "Catalog search failed.");
    if (generation !== searchGeneration || objectInput.value.trim() !== query) return;
    renderObjectOptions(Array.isArray(data.objects) ? data.objects : []);
  } catch (error) {
    if (generation !== searchGeneration) return;
    closeObjectList();
    objectSearchStatus.textContent = error instanceof Error ? error.message : "Catalog search failed.";
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
  objectSearchStatus.textContent = "Searching the catalog…";
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
  field("#proposal-latitude").textContent = `Latitude ${proposedLocation.latitude.toFixed(4)}°`;
  field("#proposal-longitude").textContent = `Longitude ${proposedLocation.longitude.toFixed(4)}°`;
  field("#proposal-accuracy").textContent = `Accuracy ± ${Math.round(proposedLocation.accuracy)} m`;
  field("#location-proposal").hidden = false;
  setSiteStatus("Location found. Confirm to use it.");
}

function locationErrorMessage(error) {
  if (error?.code === error?.PERMISSION_DENIED || error?.code === 1) {
    return "Location permission was denied. Manual values are still available.";
  }
  if (error?.code === error?.TIMEOUT || error?.code === 3) {
    return "Location lookup timed out. Manual values are still available.";
  }
  return "Location is unavailable. Manual values are still available.";
}

function requestLocation() {
  setSiteStatus("");
  if (!navigator.geolocation?.getCurrentPosition) {
    setSiteStatus("Location lookup is unavailable in this browser. Manual values are still available.", "error");
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
  setSiteStatus("Location proposal canceled. Manual values were not changed.");
}

function acceptLocationProposal() {
  if (!proposedLocation) return;
  field("#latitude").value = String(proposedLocation.latitude);
  field("#longitude").value = String(proposedLocation.longitude);
  field("#latitude").removeAttribute("aria-invalid");
  field("#longitude").removeAttribute("aria-invalid");
  proposedLocation = null;
  field("#location-proposal").hidden = true;
  setSiteStatus("Location applied. Save the site if you want to keep it.", "success");
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
  return new Intl.DateTimeFormat("en-US", options).format(instant);
}

function formatClock(startIso, offsetSeconds, timeZone = DEFAULT_TIME_ZONE) {
  const instant = new Date(new Date(startIso).getTime() + Number(offsetSeconds) * 1000);
  return new Intl.DateTimeFormat("en-US", {
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
    full: "Visible for the full duration",
    partial: "Only partly visible",
    none: "Not visible for the requested period",
  }[status] || "Unknown result";
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
      host.textContent = "Not present in the 24-hour window";
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
  let summary = "Astronomical darkness appears in the 24-hour window";
  if (coversWholeHorizon) {
    summary = "Astronomical darkness covers all 24 hours";
  } else if (!intervals.length && !events.length && !darkness.at_start) {
    summary = "No astronomical darkness in the 24-hour window";
  } else if (darkness.at_start) {
    summary = "The 24-hour window starts in astronomical darkness";
  } else if (intervals.some((interval) => Number(interval.end) >= horizon)) {
    summary = "The 24-hour window ends in astronomical darkness";
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
  requested.title = "Requested period";
  const suggestionMarker = field("#timeline-suggestion");
  suggestionMarker.hidden = true;
  const suggestion = acceptedSuggestion || selectedSuggestion || (Array.isArray(data.suggestions) ? data.suggestions[0] : null);
  if (suggestion && suggestion.tier !== "future") {
    const startOffset = (Date.parse(suggestion.start) - Date.parse(data.start)) / 1000;
    const availableDuration = Number(suggestion.available_duration_seconds ?? suggestion.duration_seconds);
    const endOffset = startOffset + availableDuration;
    const left = Math.max(0, Math.min(horizon, startOffset));
    const right = Math.max(left, Math.min(horizon, endOffset));
    if (right > left) {
      suggestionMarker.style.left = `${left / horizon * 100}%`;
      suggestionMarker.style.width = `${(right - left) / horizon * 100}%`;
      suggestionMarker.title = `${acceptedSuggestion ? "Accepted" : "Suggested"} window (up to ${formatDuration(availableDuration)}): ${formatInstant(suggestion.start, 0, data.timezone)} – ${formatInstant(suggestion.start, availableDuration, data.timezone)}`;
      suggestionMarker.hidden = false;
    }
  }
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
    `${(data.intervals || []).length} visible intervals in 24 hours. Requested period: ${formatDuration(data.duration_seconds)}. ${suggestion?.tier === "future" ? "Suggested window is on a future date and is listed above." : suggestion ? `${acceptedSuggestion ? "Accepted" : "Suggested"} window is highlighted.` : ""} Time zone ${data.timezone}.`
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
    note.textContent = "Trajectory unavailable.";
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
  title.textContent = "Altitude trajectory over 24 hours";
  const desc = svgElement("desc", {id: "trajectory-svg-desc"});
  desc.textContent = `Geometric object altitude and visible band between ${payload.min_alt} e ${payload.max_alt} gradi.`;
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
  field("#interval-count").textContent = `${items.length} ${items.length === 1 ? "interval" : "intervals"}`;
  if (!items.length) {
    const empty = document.createElement("li");
    empty.className = "empty-intervals";
    empty.textContent = "No interval meets both the balcony limits and astronomical darkness.";
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
    ["Below minimum altitude", requested.some((sample) => Number(sample.alt) < payload.min_alt)],
    ["Above maximum altitude", requested.some((sample) => Number(sample.alt) > payload.max_alt)],
    ["Outside the azimuth sector", requested.some((sample) => !azimuthVisible(Number(sample.az), payload.az_start, payload.az_end))],
    ["Sun above −18°", requested.some((sample) => Number(sample.sun_alt) > -18)],
  ];
  const statusReason = {
    full: "All criteria met for the requested period",
    partial: "The requested period is only partly visible",
    none: "The requested period has no complete continuous window",
  }[data.status] || "Unknown result";
  const reasons = [[statusReason, true], ...sampledReasons.map(([label, active]) => [`Samples every 5 minutes: ${label}`, active])];
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

function renderSuggestions(data) {
  const card = field("#suggestions-card");
  const items = Array.isArray(data.suggestions) ? data.suggestions : [];
  if (data.status === "full") {
    card.hidden = true;
    return;
  }
  card.hidden = false;
  const note = field("#suggestions-note");
  suggestionList.replaceChildren();
  selectedSuggestion = null;
  acceptedSuggestion = null;
  acceptedPlan.hidden = true;
  ninaExportStatus.textContent = "";
  suggestionsEmpty.hidden = Boolean(items.length);
  if (!items.length) {
    note.textContent = "This object has no valid suggestion for these settings.";
    return;
  }
  const labels = {adjust: "Adjust the current time", future: "Choose a future date", widest: "Use the widest continuous window"};
  items.forEach((suggestion, index) => {
    const item = document.createElement("article");
    item.className = "suggestion-item";
    const select = document.createElement("button");
    select.className = "suggestion-select";
    select.type = "button";
    select.setAttribute("aria-pressed", "false");
    const badge = document.createElement("span");
    badge.className = "suggestion-tier";
    badge.textContent = index === 0 ? "The Best" : `Alternative ${index}`;
    const stars = document.createElement("span");
    stars.className = "suggestion-stars";
    const starCount = Math.max(1, Math.min(5, Number(suggestion.stars) || (5 - index)));
    stars.textContent = `${"★".repeat(starCount)}${"☆".repeat(5 - starCount)}`;
    stars.setAttribute("aria-label", `${starCount} out of 5 stars`);
    const copy = document.createElement("span");
    copy.className = "suggestion-copy";
    const title = document.createElement("strong");
    title.textContent = labels[suggestion.tier] || "Suggestion";
    const time = document.createElement("span");
    time.className = "suggestion-time";
    time.textContent = `${formatInstant(suggestion.start, 0, data.timezone)} – ${formatInstant(suggestion.end, 0, data.timezone)}`;
    const detail = document.createElement("small");
    detail.textContent = `${suggestion.reason || "Valid observing window."} ` + (suggestion.tier === "widest"
      ? `Available for ${formatDuration(suggestion.duration_seconds)} of the ${formatDuration(suggestion.requested_duration_seconds)} requested.`
      : `Continuous duration: ${formatDuration(suggestion.duration_seconds)}.`);
    const availableDuration = Number(suggestion.available_duration_seconds ?? suggestion.duration_seconds);
    if (availableDuration > Number(suggestion.duration_seconds)) detail.textContent += ` This window supports up to ${formatDuration(availableDuration)}.`;
    if (suggestion.tier === "future") detail.textContent += " Future date — not shown on today's timeline.";
    copy.append(title, time, detail);
    select.append(badge, stars, copy);
    const accept = document.createElement("button");
    accept.className = "button button-secondary button-compact suggestion-accept";
    accept.type = "button";
    accept.textContent = "Accept this window";
    accept.addEventListener("click", () => acceptSuggestion(suggestion, item));
    select.addEventListener("click", () => selectSuggestion(suggestion, item));
    item.append(select, accept);
    suggestionList.append(item);
  });
  note.textContent = data.suggestion_note || "Suggestions calculated locally.";
}

function selectSuggestion(suggestion, item) {
  selectedSuggestion = suggestion;
  suggestionList.querySelectorAll(".suggestion-item").forEach((candidate) => {
    const active = candidate === item;
    candidate.classList.toggle("selected", active);
    candidate.querySelector(".suggestion-select")?.setAttribute("aria-pressed", String(active));
  });
  if (selectedResult) renderTimeline(selectedResult);
  resultLive.textContent = "Suggestion selected. Accept it to prepare the NINA export.";
}

function acceptSuggestion(suggestion, item) {
  selectSuggestion(suggestion, item);
  acceptedSuggestion = suggestion;
  acceptedPlan.hidden = false;
  acceptedPlanSummary.textContent = `${formatTargetLabel(selectedResult?.object, "Target")} · ${formatInstant(suggestion.start, 0, selectedResult.timezone)} – ${formatInstant(suggestion.end, 0, selectedResult.timezone)} · ${formatDuration(suggestion.duration_seconds)}`;
  ninaSequenceName.value = `AstroChecker_${(selectedResult?.object?.name || "target").replace(/[^A-Za-z0-9._-]+/g, "-")}`;
  ninaSequenceName.removeAttribute("aria-invalid");
  ninaExportStatus.className = "status-message";
  ninaExportStatus.textContent = "Accepted locally. Choose a sequence name, then export it to NINA.";
  renderTimeline(selectedResult);
  resultLive.textContent = "Suggestion accepted. The NINA export is ready.";
}

function renderNightPlan(data) {
  resultsTitle.textContent = "Night plan";
  emptyResult.hidden = true;
  resultError.hidden = true;
  resultContent.hidden = true;
  nightPlan.hidden = false;
  nightPlan.classList.remove("is-stale");
  staleBadge.hidden = true;
  hasResult = true;

  const blocks = Array.isArray(data.blocks) ? data.blocks : [];
  const gaps = Array.isArray(data.gaps) ? data.gaps : [];
  nightBlocks.replaceChildren();
  nightGaps.replaceChildren();
  nightTimeline.replaceChildren();
  field("#night-note").textContent = data.note || "Plan calculated locally.";
  field("#night-coverage").textContent = `${Number(data.coverage_percent || 0).toLocaleString("en-US")}%`;

  if (data.night_start && data.night_end) {
    field("#night-period").textContent = `${formatInstant(data.night_start, 0, data.timezone)} → ${formatInstant(data.night_end, 0, data.timezone)} · ${formatDuration(data.night_duration_seconds)}`;
  } else {
    field("#night-period").textContent = "No complete astronomical night for the selected date and site.";
  }
  field("#night-chain").textContent = blocks.length
    ? blocks.map((block) => formatTargetLabel(block.target, "Target")).join(" → ")
    : "No sequence available";

  blocks.forEach((block, index) => {
    const item = document.createElement("li");
    const number = document.createElement("span");
    number.className = "idea-index";
    number.textContent = String(index + 1);
    const detail = document.createElement("div");
    detail.className = "night-block-detail";
    const title = document.createElement("strong");
    const target = block.target || {};
    title.textContent = `${formatTargetLabel(target)} · ${target.type || block.type || "DSO"}`;
    const times = document.createElement("span");
    times.textContent = `${formatInstant(block.start, 0, data.timezone)} → ${formatInstant(block.end, 0, data.timezone)} · ${formatDuration(block.duration_seconds)}`;
    const reason = document.createElement("small");
    reason.textContent = block.reason || "Visible in the balcony window.";
    detail.append(title, times, reason);
    if (block.short_fill) {
      const badge = document.createElement("span");
      badge.className = "short-fill-badge";
      badge.textContent = "Short block";
      detail.append(badge);
    }
    item.append(number, detail);
    nightBlocks.append(item);
  });
  if (!blocks.length) {
    const empty = document.createElement("li");
    empty.className = "empty-intervals";
    empty.textContent = data.note || "No target is visible during astronomical night.";
    nightBlocks.append(empty);
  }

  gaps.forEach((gap) => {
    const item = document.createElement("li");
    item.textContent = `Open gap · ${formatInstant(gap.start, 0, data.timezone)} → ${formatInstant(gap.end, 0, data.timezone)} · ${formatDuration(gap.duration_seconds)}`;
    nightGaps.append(item);
  });
  field("#night-gaps-card").hidden = gaps.length === 0;

  const total = Number(data.night_duration_seconds || 0);
  const segments = [
    ...blocks.map((block, index) => ({...block, kind: "target", colorIndex: index})),
    ...gaps.map((gap) => ({...gap, kind: "gap"})),
  ].sort((a, b) => Date.parse(a.start) - Date.parse(b.start));
  segments.forEach((segment) => {
    const bar = document.createElement("span");
    bar.className = segment.kind === "gap" ? "night-segment gap" : `night-segment target target-${segment.colorIndex % 5}`;
    bar.style.flexBasis = total > 0 ? `${100 * Number(segment.duration_seconds || 0) / total}%` : "0%";
    bar.title = segment.kind === "gap"
      ? `Open gap · ${formatDuration(segment.duration_seconds)}`
      : `${formatTargetLabel(segment.target, "Target")} · ${formatDuration(segment.duration_seconds)}`;
    nightTimeline.append(bar);
  });
}

function clearSuggestionAcknowledgement() {
  selectedSuggestion = null;
  acceptedSuggestion = null;
  selectedResult = null;
  acceptedPlan.hidden = true;
  ninaExportStatus.textContent = "";
}

async function exportAcceptedSuggestion() {
  if (!acceptedSuggestion || !selectedResult || ninaExportRunning) return;
  const sequenceName = ninaSequenceName.value.trim();
  if (!sequenceName) {
    ninaSequenceName.setAttribute("aria-invalid", "true");
    ninaSequenceName.focus();
    ninaExportStatus.className = "status-message error";
    ninaExportStatus.textContent = "Enter a name for the NINA sequence.";
    return;
  }
  ninaSequenceName.removeAttribute("aria-invalid");
  ninaExportRunning = true;
  exportAcceptedNina.disabled = true;
  exportAcceptedNina.classList.add("loading");
  exportAcceptedNina.setAttribute("aria-busy", "true");
  ninaExportStatus.className = "status-message";
  ninaExportStatus.textContent = "Creating the NINA Legacy XML locally…";
  try {
    const response = await fetch("/api/nina/legacy-sequence", {
      method: "POST",
      headers: {"Content-Type": "application/json", Accept: "application/json"},
      body: JSON.stringify({
        object: selectedResult.object,
        duration_seconds: acceptedSuggestion.duration_seconds,
        suggestion_start: acceptedSuggestion.start,
        suggestion_end: acceptedSuggestion.end,
        sequence_name: sequenceName,
      }),
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "NINA sequence export failed.");
    ninaExportStatus.className = "status-message success";
    ninaExportStatus.textContent = `Saved locally to Downloads: ${data.filename || data.path}`;
    resultLive.textContent = `NINA Legacy sequence saved: ${data.filename || data.path}`;
  } catch (error) {
    ninaExportStatus.className = "status-message error";
    ninaExportStatus.textContent = error instanceof Error ? error.message : "NINA sequence export failed.";
    resultLive.textContent = ninaExportStatus.textContent;
  } finally {
    ninaExportRunning = false;
    exportAcceptedNina.disabled = false;
    exportAcceptedNina.classList.remove("loading");
    exportAcceptedNina.removeAttribute("aria-busy");
  }
}

exportAcceptedNina.addEventListener("click", exportAcceptedSuggestion);

function renderResult(data, payload) {
  resultsTitle.textContent = "Observing window";
  nightPlan.hidden = true;
  emptyResult.hidden = true;
  resultError.hidden = true;
  resultContent.hidden = false;
  resultContent.classList.remove("is-stale");
  nightPlan.classList.remove("is-stale");
  staleBadge.hidden = true;
  hasResult = true;
  selectedResult = data;

  if (data.object?.name) {
    objectInput.value = data.object.name;
    selectedObject = data.object;
    const aliases = optionAliases(data.object);
    objectSearchStatus.textContent = aliases.length
      ? `Resolved as ${formatTargetLabel(data.object)}. Aliases: ${aliases.join(", ")}.`
      : `Resolved as ${formatTargetLabel(data.object)}.`;
  }
  const summary = field("#result-summary");
  summary.className = `result-summary ${data.status}`;
  field("#result-object").textContent = formatTargetLabel(data.object, payload.object);
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
    windowTitle.textContent = "First complete window";
    windowTime.textContent = `${formatInstant(data.start, data.first_window.start, data.timezone)} – ${formatInstant(data.start, data.first_window.end, data.timezone)}`;
    windowNote.textContent = Number(data.first_window.start) === 0
      ? "It starts at the requested time. Endpoints include the calculated seconds."
      : "First useful start in the analyzed 24 hours; endpoints include the calculated seconds.";
  } else {
    windowCard.classList.add("no-window");
    windowTitle.textContent = "No solution in the analyzed 24 hours";
    windowTime.textContent = "There is no single continuous interval of the requested duration.";
    const edges = data.horizon_edges || {};
    windowNote.textContent = edges.start || edges.end
      ? "One interval reaches the 24-hour boundary and may continue beyond the analyzed period."
      : "Shorter intervals may still appear below.";
  }

  renderDarkness(data);
  renderTimeline(data);
  renderTrajectory(data, payload);
  renderIntervals(data);
  renderReasons(data, payload);
  renderNotes(data);
  renderSuggestions(data);
  resultLive.textContent = `${data.object?.name || payload.object}: ${label}. Times in the time zone ${data.timezone}.`;
}

async function requestIdeas() {
  if (!catalogReady) {
    setCatalogState({ready: false, message: "Local catalog unavailable. Check again.", version: "", catalogs: []});
    verifyButton.focus();
    return;
  }
  if (!validateForm({requireObject: false})) return;
  clearSuggestionAcknowledgement();
  calculationRunning = true;
  updatePlannerAvailability();
  setButtonLoading(ideasButton, true, "Finding ideas…");
  emptyResult.hidden = true;
  resultContent.hidden = true;
  nightPlan.hidden = true;
  resultError.hidden = true;
  resultLive.textContent = "Finding a local observing sequence…";
  try {
    const response = await fetch("/api/ideas", {
      method: "POST",
      headers: {"Content-Type": "application/json", Accept: "application/json"},
      body: JSON.stringify(currentPayload()),
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "Idea planning failed.");
    renderNightPlan(data);
    resultLive.textContent = data.note || "Idea plan ready.";
  } catch (error) {
    showResultError(error instanceof Error ? error.message : "Idea planning failed.");
    nightPlan.hidden = true;
  } finally {
    calculationRunning = false;
    updatePlannerAvailability();
    setButtonLoading(ideasButton, false, "");
  }
}

ideasButton.addEventListener("click", requestIdeas);

function releaseDateTimePickerFocus() {
  const completeMinute = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(startInput.value);
  if (!completeMinute || Number.isNaN(startInput.valueAsNumber)) return;
  window.setTimeout(() => {
    if (document.activeElement === startInput) startInput.blur();
  }, 0);
}

startInput.addEventListener("input", releaseDateTimePickerFocus);
startInput.addEventListener("change", releaseDateTimePickerFocus);

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
    setCatalogState({ready: false, message: "Local catalog unavailable. Check again.", version: "", catalogs: []});
    verifyButton.focus();
    return;
  }
  if (!validateForm()) return;
  clearSuggestionAcknowledgement();

  const payload = currentPayload();
  window.clearTimeout(searchTimer);
  searchGeneration += 1;
  closeObjectList();
  calculationRunning = true;
  updatePlannerAvailability();
  setButtonLoading(calculateButton, true, "Calculating…");
  resultError.hidden = true;
  resultLive.textContent = "Calculating the next 24 hours locally…";

  try {
    const response = await fetch("/api/check", {
      method: "POST",
      headers: {"Content-Type": "application/json", Accept: "application/json"},
      body: JSON.stringify(payload),
    });
    const data = await readJson(response);
    if (!response.ok) {
      const error = new Error(data.error || "Calculation failed.");
      error.code = data.code;
      throw error;
    }
    renderResult(data, payload);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Calculation failed. Try again.";
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
