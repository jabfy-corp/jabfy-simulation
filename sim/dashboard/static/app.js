/** Entry point: connects the editor, 3D view and real simulation state. */
import { api } from "./api.js";
import { HouseScene } from "./scene.js";
import { HouseEditor } from "./editor.js";
import { DeviceControls, describeState } from "./controls.js";
import { AIInspector } from "./ai.js";
import { $, el, text, clock, humanize } from "./ui.js";

let scene;
let editor;
let controls;
let ai;
let state;
let online = false;
let saving = false;
let userError = "";
let activeTab = "home";
let lastReceived;
let revision;
let timer;
let polling = false;
const eventNodes = new Map();

function notice(message, error = false) {
  $("notice").hidden = !message;
  $("notice").dataset.error = String(error);
  text($("notice"), message);
}

function showTab(name, focus = false) {
  activeTab = name;
  for (const tab of document.querySelectorAll("[data-tab]")) {
    const selected = tab.dataset.tab === name;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    $("panel-" + tab.dataset.tab).hidden = !selected;
    if (selected && focus) tab.focus();
  }
  if (name === "ai") ai?.open();
}

for (const tab of document.querySelectorAll("[data-tab]")) {
  tab.addEventListener("click", () => showTab(tab.dataset.tab));
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const tabs = ["home", "device", "ai"];
    let index = tabs.indexOf(activeTab);
    if (event.key === "Home") index = 0;
    else if (event.key === "End") index = 2;
    else index = (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    showTab(tabs[index], true);
  });
}

function setMode(mode) {
  $("orbit-mode").classList.toggle("active", mode === "orbit");
  $("visit-mode").classList.toggle("active", mode === "visit");
  $("orbit-mode").setAttribute("aria-pressed", String(mode === "orbit"));
  $("visit-mode").setAttribute("aria-pressed", String(mode === "visit"));
  $("walk-pad").hidden = mode !== "visit";
  text($("navigation-help"), mode === "visit"
    ? "Glissez pour regarder · ZQSD / WASD / flèches pour marcher · Échap pour sortir"
    : "Glissez pour tourner · Molette pour zoomer · Cliquez sur un appareil");
}

try {
  scene = new HouseScene($("scene"), {
    onSelect: (id) => { editor?.selectDevice(id); },
    onMode: setMode,
  });
  $("scene-loading").hidden = true;
} catch (error) {
  text($("scene-loading"), "La vue 3D nécessite WebGL. L’éditeur et les commandes restent disponibles dans le panneau à droite.");
  console.error("Impossible d’initialiser la vue 3D", error);
}

$("orbit-mode").addEventListener("click", () => scene?.fit());
$("fit-view").addEventListener("click", () => scene?.fit());
$("visit-mode").addEventListener("click", () => scene?.visit(editor?.roomId));
for (const button of $("walk-pad").querySelectorAll("button")) {
  button.addEventListener("pointerdown", (event) => {
    event.preventDefault(); button.setPointerCapture(event.pointerId);
    scene?.move(button.dataset.walk, true);
  });
  for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) {
    button.addEventListener(type, () => scene?.move(button.dataset.walk, false));
  }
}

function selectDevice(device) {
  scene?.select(device?.id || null);
  controls?.select(device);
  if (device) showTab("device");
}

function draftChanged(home, dirty) {
  userError = "";
  scene?.setHome(home);
  $("scene-empty").hidden = Boolean(home.rooms.length);
  $("save-home").disabled = !dirty || saving;
  $("save-status").dataset.dirty = String(dirty);
  text($("save-status"), saving ? "Enregistrement et reconfiguration de la simulation…" : dirty ? "Modifications locales · Enregistrez pour les appliquer." : "Maison enregistrée · Les états évoluent en direct.");
  $("discard-changes").disabled = !dirty;
  $("room-shortcuts").replaceChildren();
  for (const room of home.rooms) {
    const button = el("button", "", room.name);
    button.type = "button";
    button.title = `Visiter ${room.name}`;
    button.addEventListener("click", () => scene?.visit(room.id));
    $("room-shortcuts").append(button);
  }
  controls?.select(editor?.selected);
  ai?.update();
}

async function saveHome() {
  if (!editor?.dirty || saving || !editor.validate()) return;
  saving = true; userError = "";
  $("save-home").disabled = true;
  document.querySelector(".inspector").inert = true;
  text($("save-status"), "Enregistrement et reconfiguration de la simulation…");
  notice("La simulation se reconfigure pour prendre en compte la maison.");
  try {
    const result = await api.save(editor.home);
    const home = result.home || result;
    editor.load(home);
    revision = undefined;
    ai.loaded = false;
    notice("");
    text($("save-status"), "Maison enregistrée. La simulation reprend avec cette configuration.");
    if (activeTab === "ai") ai.refresh();
  } catch (error) {
    userError = `Enregistrement non confirmé : ${error.message}`;
    notice(userError, true);
    text($("save-status"), "Modifications conservées dans l’éditeur.");
  } finally {
    saving = false;
    document.querySelector(".inspector").inert = false;
    $("save-home").disabled = !editor.dirty;
    refreshSoon();
  }
}
$("save-home").addEventListener("click", saveHome);

function renderHealth() {
  const running = online && state?.status === "running";
  const connected = running && state?.broker?.connected;
  text($("connection"), !online ? "Connexion perdue" : state.status === "starting" ? "Démarrage…" : state.status === "reconfiguring" ? "Reconfiguration…" : state.status === "error" ? "Simulation en erreur" : state.status === "stopped" ? "Simulation arrêtée" : connected ? "Simulation en cours" : "MQTT déconnecté");
  $("connection").dataset.status = connected ? "running" : "error";
  document.body.dataset.offline = String(!online);
  text($("scene-status"), lastReceived ? `${online ? "Actualisé" : "Derniers états"} à ${clock.format(lastReceived)}` : "En attente");
  text($("simulation-summary"), state ? `${state.devices.length} appareils · ${state.ticks} ticks · ${state.stats?.bus?.executed ?? 0} actions exécutées` : "Connexion au simulateur…");
  if (saving) return;
  const message = !online ? "Le simulateur ne répond plus. Les derniers états restent affichés. Reconnexion automatique…"
    : userError || state.error || (state.status === "error" ? "La simulation est en erreur." : state.status === "stopped" ? "La simulation est arrêtée." : !state.broker?.connected ? "Connexion MQTT en attente. Les commandes seront disponibles dès la connexion rétablie." : "");
  notice(message, !online || Boolean(userError) || state?.status === "error");
}

function eventEntity(entity) {
  const home = editor?.home;
  const devices = home?.devices || [];
  const raw = String(entity || "");
  const normalized = raw.includes(".") ? raw.split(".").slice(1).join(".") : raw;
  return devices.slice().sort((a, b) => b.id.length - a.id.length).find((device) => {
    // Match the exact namespace used by sim.home.conversion.device_wire_id().
    const wireId = `sim_${home.id}_${device.id}`;
    return device.id === raw || normalized === device.id || normalized.startsWith(`${device.id}_`)
      || normalized === wireId || normalized.startsWith(`${wireId}_`);
  });
}

function renderEvents(events) {
  const list = $("events");
  if (!eventNodes.size) list.replaceChildren();
  const shown = events.slice(0, 18);
  const wanted = new Set(shown.map((event) => event.id));
  for (const [id, node] of eventNodes) if (!wanted.has(id)) { node.remove(); eventNodes.delete(id); }
  for (const event of shown) {
    let node = eventNodes.get(event.id);
    if (!node) {
      node = el("li"); node.append(el("strong"), el("time"), el("small")); eventNodes.set(event.id, node);
    }
    const type = event.type || "";
    const labels = { "command.requested": "Action proposée", "command.approved": "Action autorisée", "command.rejected": "Action refusée", "command.executed": "Action exécutée", "command.failed": "Échec de l’action", "state.changed": "État mis à jour", "simulation.motion": "Mouvement simulé", "simulation.smoke_on": "Fumée simulée", "simulation.smoke_off": "Fumée dissipée", "home.saved": "Maison enregistrée" };
    const device = eventEntity(event.entity);
    let detail = [device?.name || event.entity, event.action, event.reason].filter(Boolean).join(" · ");
    if (type === "state.changed" && device && event.value) detail = `${device.name} · ${describeState({ ...device, state: event.value })}`;
    text(node.children[0], labels[type] || humanize(type.replaceAll(".", " ")));
    const date = new Date(event.time);
    text(node.children[1], Number.isNaN(date.getTime()) ? "—" : clock.format(date));
    node.children[1].dateTime = event.time;
    text(node.children[2], detail);
    node.dataset.error = String(/failed|rejected|error/.test(type));
  }
  let next = list.firstElementChild;
  for (const event of shown) {
    const node = eventNodes.get(event.id);
    if (node !== next) list.insertBefore(node, next);
    next = node.nextElementSibling;
  }
  if (!shown.length && !list.childElementCount) list.append(el("li", "muted small", "Aucune action pour le moment. Sélectionnez un appareil pour le piloter."));
  text($("event-summary"), `${events.length} événements récents`);
}

function refreshSoon() {
  clearTimeout(timer);
  if (!polling) void poll();
}

async function poll() {
  if (polling) return;
  polling = true;
  try {
    const next = await api.state();
    if (!Array.isArray(next.devices)) throw new Error("Réponse invalide du simulateur.");
    state = next; online = true; lastReceived = new Date();
    if (revision && revision !== state.home_revision && !saving) {
      if (!editor.dirty) editor.load(await api.home());
      else {
        editor.baseline = await api.home();
        userError = "La maison a changé sur le serveur. Votre brouillon reste ouvert ; annulez les modifications pour recharger la version enregistrée.";
      }
    }
    revision = state.home_revision;
    scene?.updateState(state.devices);
    controls?.update(state, true);
    ai?.update(state.home_revision);
    renderEvents(state.events || []);
    for (const [id, row] of editor.deviceRows) {
      const live = state.devices.find((device) => device.id === id);
      text(row.status, live ? describeState(live) : "À enregistrer");
    }
  } catch (error) {
    online = false;
    controls?.update(state, false);
  } finally {
    renderHealth();
    polling = false;
    timer = setTimeout(poll, document.hidden ? 3000 : 800);
  }
}

async function start() {
  try {
    const [home, catalog] = await Promise.all([api.home(), api.catalog()]);
    controls = new DeviceControls(catalog, refreshSoon);
    editor = new HouseEditor(catalog, {
      onChange: draftChanged, onSelect: selectDevice,
      onError: (message) => { userError = message; notice(message, true); },
    });
    ai = new AIInspector({ getHome: () => editor.home, getDirty: () => editor.dirty, onAction: refreshSoon });
    editor.load(home);
    if (activeTab === "ai") ai.open();
    void poll();
  } catch (error) {
    notice(`Chargement impossible : ${error.message} Nouvelle tentative automatique…`, true);
    text($("save-status"), "En attente du serveur local.");
    setTimeout(start, 5000);
  }
}

document.addEventListener("visibilitychange", () => { if (!document.hidden && editor) refreshSoon(); });
void start();
