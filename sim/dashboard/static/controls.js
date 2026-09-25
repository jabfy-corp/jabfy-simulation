/** Device capabilities become controls; all actions are verified by the backend. */
import { api } from "./api.js";
import { $, el, field, text, feedback, format, humanize } from "./ui.js";

export function describeState(device) {
  if (!device) return "Enregistrez la maison pour activer cet appareil.";
  const state = device.state || {};
  const numeric = (value, unit) => Number.isFinite(value) ? `${format.format(value)} ${unit}` : "—";
  if (["on_off_light", "dimmer_light", "rgb_bulb"].includes(device.type)) {
    if (!state.state) return "État en attente";
    return `${state.state === "ON" ? "Allumée" : "Éteinte"}${state.brightness != null ? ` · ${Math.round(state.brightness / 254 * 100)} %` : ""}`;
  }
  if (device.type === "motion_sensor") return state.occupancy ? "Présence détectée" : "Aucun mouvement";
  if (device.type === "smoke_sensor") return state.smoke ? "Alerte : fumée détectée" : "Aucune fumée";
  if (device.type === "door_lock") return state.state === "LOCK" ? "Porte verrouillée" : "Porte déverrouillée";
  if (device.type === "temperature_sensor") return `${numeric(state.temperature, "°C")} · ${numeric(state.humidity, "% d’humidité")}`;
  if (device.type === "thermostat") return `${numeric(state.local_temperature, "°C")} · Consigne ${numeric(state.occupied_heating_setpoint, "°C")}${state.running_state === "heat" ? " · Chauffe" : " · Au repos"}`;
  if (device.type === "smart_tv") return String(state.switch ?? state.power).toLowerCase() === "on" ? "Télévision allumée" : "Télévision éteinte";
  if (device.type === "alarm_siren") return state.alarm ? "Alarme déclenchée" : state.state === "armed" ? "Sirène armée" : "Sirène désarmée";
  return Object.entries(state).map(([key, value]) => `${humanize(key)} : ${value}`).join(" · ") || "État en attente";
}

export class DeviceControls {
  constructor(catalog, onAction) {
    this.catalog = catalog.device_types;
    this.onAction = onAction;
    this.device = null;
    this.state = null;
    this.online = false;
    this.busy = false;
    this.signature = null;
  }

  select(device) {
    this.device = device;
    const signature = device ? `${device.id}:${device.type}` : "none";
    if (signature !== this.signature) {
      this.signature = signature;
      this.render();
      feedback("control-feedback", "");
    }
    this.update(this.state, this.online);
  }

  update(state, online) {
    this.state = state;
    this.online = online;
    const live = state?.devices?.find((d) => d.id === this.device?.id && d.type === this.device?.type);
    text($("device-state"), this.device ? describeState(live) : "Aucun appareil sélectionné");
    text($("device-live-badge"), !live ? "Brouillon" : online ? "En direct" : "Dernier état");
    const connected = state?.status === "running" && state?.broker?.connected && (!state.pipeline || state.stats?.bus?.connected);
    const ready = online && connected && Boolean(live) && !this.busy;
    for (const button of $("manual-controls").querySelectorAll("button")) button.disabled = !ready;
  }

  render() {
    const container = $("manual-controls"); container.replaceChildren();
    if (!this.device) return;
    const capabilities = this.catalog.find((item) => item.type === this.device.type);
    if (!capabilities) return;
    const direct = el("div", "button-row");
    for (const action of capabilities.actions) {
      const properties = action.params?.properties || {};
      if (!Object.keys(properties).length) {
        const button = el("button", "secondary", action.label);
        button.type = "button";
        button.addEventListener("click", () => this.execute(action.action, {}));
        direct.append(button);
      } else container.append(this.actionForm(action));
    }
    if (direct.childElementCount) container.prepend(direct);
    const events = { motion: "Simuler un mouvement (5 s)", smoke_on: "Simuler de la fumée", smoke_off: "Dissiper la fumée" };
    for (const event of capabilities.sensor_events) {
      const button = el("button", "secondary", events[event] || humanize(event));
      button.type = "button";
      button.addEventListener("click", () => this.simulate(event));
      container.append(button);
    }
    if (!capabilities.actions.length && !capabilities.sensor_events.length) container.append(el("p", "muted small", "Cet appareil publie ses mesures automatiquement. Il ne possède pas de commande manuelle."));
  }

  actionForm(action) {
    const form = el("form", "control-form");
    form.append(el("h4", "", action.label));
    const live = this.state?.devices?.find((d) => d.id === this.device.id)?.state || {};
    const labels = { brightness: "Luminosité (0–254)", temperature: "Consigne (°C)", color: "Couleur" };
    for (const [name, schema] of Object.entries(action.params.properties || {})) {
      if (name === "color") form.append(field("Couleur", name, "#ffdc90", { type: "color" }));
      else {
        const value = name === "temperature" ? live.occupied_heating_setpoint ?? 21 : name === "brightness" ? live.brightness ?? 180 : schema.default ?? schema.minimum ?? 0;
        form.append(field(labels[name] || schema.title || humanize(name), name, value, {
          type: ["number", "integer"].includes(schema.type) ? "number" : "text",
          min: schema.minimum, max: schema.maximum, step: schema.type === "integer" ? 1 : 0.1,
        }));
      }
    }
    const submit = el("button", "secondary", "Appliquer");
    submit.type = "submit"; form.append(submit);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const params = {};
      for (const [name, schema] of Object.entries(action.params.properties || {})) {
        const value = form.elements[name].value;
        if (name === "color") params.color = { r: parseInt(value.slice(1, 3), 16), g: parseInt(value.slice(3, 5), 16), b: parseInt(value.slice(5, 7), 16) };
        else params[name] = ["number", "integer"].includes(schema.type) ? Number(value) : value;
      }
      this.execute(action.action, params);
    });
    return form;
  }

  async run(operation, success) {
    if (this.busy || !this.device) return;
    this.busy = true; this.update(this.state, this.online);
    feedback("control-feedback", "Commande envoyée, vérification en cours…");
    try {
      const result = await operation();
      if (["rejected", "failed"].includes(result.status)) throw new Error(result.reason || "La commande n’a pas été exécutée.");
      feedback("control-feedback", success);
      this.onAction?.();
    } catch (error) { feedback("control-feedback", error.message, true); }
    finally { this.busy = false; this.update(this.state, this.online); }
  }

  execute(action, params) {
    const device = this.device;
    if (device) this.run(() => api.command(device.id, action, params), `Commande exécutée pour ${device.name}.`);
  }

  simulate(event) {
    const device = this.device;
    if (device) this.run(() => api.event(device.id, event), `Événement simulé pour ${device.name}. Consultez son état et le journal.`);
  }
}
