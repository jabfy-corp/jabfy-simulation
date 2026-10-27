/** House editor: draft changes are kept locally until an explicit save. */
import { $, el, field, options, text } from "./ui.js";

const LIGHTS = new Set(["on_off_light", "dimmer_light", "rgb_bulb"]);
const clone = (value) => structuredClone(value);
const id = (prefix) => `${prefix}_${crypto.randomUUID().slice(0, 8)}`;

export class HouseEditor {
  constructor(catalog, { onChange, onSelect, onError }) {
    this.catalog = catalog.device_types;
    this.onChange = onChange;
    this.onSelect = onSelect;
    this.onError = onError;
    this.home = null;
    this.baseline = null;
    this.roomId = null;
    this.deviceId = null;
    this.deviceRows = new Map();
    this.bind();
  }

  load(home) {
    this.baseline = clone(home);
    this.home = clone(home);
    this.roomId = this.home.rooms.find((room) => room.id === this.roomId)?.id || this.home.rooms[0]?.id || null;
    this.deviceId = this.home.devices.find((device) => device.id === this.deviceId)?.id || null;
    this.render();
    this.changed();
  }

  get dirty() { return this.home && JSON.stringify(this.home) !== JSON.stringify(this.baseline); }
  get selected() { return this.home?.devices.find((device) => device.id === this.deviceId) || null; }

  changed() {
    text($("home-title"), this.home.name);
    $("discard-changes").disabled = !this.dirty;
    this.onChange(clone(this.home), this.dirty);
  }

  selectDevice(deviceId, notify = true) {
    this.deviceId = deviceId;
    this.renderDevice();
    for (const [id, row] of this.deviceRows) row.button.classList.toggle("selected", id === deviceId);
    if (notify) this.onSelect(this.selected);
  }

  bind() {
    $("home-name").addEventListener("change", (event) => {
      if (!this.home) return;
      this.home.name = event.target.value.trim();
      this.changed();
    });
    $("room-select").addEventListener("change", (event) => { this.roomId = event.target.value; this.renderRoom(); });
    $("device-select").addEventListener("change", (event) => this.selectDevice(event.target.value));
    $("room-form").addEventListener("submit", (event) => event.preventDefault());
    $("device-form").addEventListener("submit", (event) => event.preventDefault());
    $("room-form").addEventListener("change", (event) => this.editRoom(event.target));
    $("device-form").addEventListener("change", (event) => this.editDevice(event.target));
    $("add-room").addEventListener("click", () => this.addRoom());
    $("add-device").addEventListener("click", () => this.addDevice());
    $("delete-room").addEventListener("click", () => {
      if (!this.home || !this.roomId) return;
      this.home.rooms = this.home.rooms.filter((room) => room.id !== this.roomId);
      this.home.devices = this.home.devices.filter((device) => device.room_id !== this.roomId);
      this.cleanAutomations();
      this.roomId = this.home.rooms[0]?.id || null;
      if (!this.home.devices.some((d) => d.id === this.deviceId)) this.deviceId = null;
      this.render(); this.changed(); this.onSelect(this.selected);
    });
    $("delete-device").addEventListener("click", () => {
      if (!this.home) return;
      this.home.devices = this.home.devices.filter((device) => device.id !== this.deviceId);
      this.deviceId = null;
      this.cleanAutomations(); this.render(); this.changed(); this.onSelect(null);
    });
    $("automation-form").addEventListener("submit", (event) => {
      event.preventDefault();
      const form = event.target;
      const motion = form.elements.motion_device_id.value;
      const target = form.elements.target_device_id.value;
      if (!motion || !target || !this.home) return;
      if (this.home.automations.some((a) => a.motion_device_id === motion && a.target_device_id === target)) {
        this.onError("Cette liaison existe déjà."); return;
      }
      this.home.automations.push({ id: id("rule"), motion_device_id: motion, target_device_id: target });
      this.renderAutomations(); this.changed();
    });
    $("discard-changes").addEventListener("click", () => { if (this.baseline) this.load(this.baseline); });
    $("export-home").addEventListener("click", () => this.export());
    $("import-home").addEventListener("click", () => $("import-file").click());
    $("import-file").addEventListener("change", (event) => this.import(event.target.files[0]));
    window.addEventListener("beforeunload", (event) => { if (this.dirty) { event.preventDefault(); event.returnValue = ""; } });
  }

  addRoom() {
    if (!this.home) return;
    const right = Math.max(0, ...this.home.rooms.map((room) => room.x + room.width));
    const room = { id: id("room"), name: `Pièce ${this.home.rooms.length + 1}`, x: right, z: 0, width: 4, depth: 4, height: 2.7, color: "#dce4cf" };
    this.home.rooms.push(room); this.roomId = room.id;
    this.render(); this.changed();
    $("room-form").elements.name.focus();
  }

  addDevice() {
    if (!this.home) return;
    const room = this.home.rooms.find((r) => r.id === this.roomId) || this.home.rooms[0];
    if (!room) { this.onError("Ajoutez d’abord une pièce pour y placer un appareil."); return; }
    const device = { id: id("device"), name: "Nouvelle lampe", type: "on_off_light", room_id: room.id, x: Math.min(1, room.width / 2), z: Math.min(1, room.depth / 2) };
    this.home.devices.push(device); this.deviceId = device.id;
    this.render(); this.changed(); this.onSelect(device);
    $("device-form").elements.name.focus();
  }

  editRoom(input) {
    const room = this.home.rooms.find((r) => r.id === this.roomId);
    if (!room || !input.name || !input.checkValidity()) return;
    room[input.name] = input.type === "number" ? Number(input.value) : input.value;
    for (const device of this.home.devices.filter((d) => d.room_id === room.id)) {
      device.x = Math.min(device.x, room.width);
      device.z = Math.min(device.z, room.depth);
    }
    options($("room-select"), this.home.rooms.map((r) => ({ value: r.id, label: r.name })), this.roomId);
    this.renderDevice(); this.renderDeviceList(); this.changed();
  }

  editDevice(input) {
    const device = this.selected;
    if (!device || !input.name || !input.checkValidity()) return;
    device[input.name] = input.type === "number" ? Number(input.value) : input.value;
    if (input.name === "room_id") {
      const room = this.home.rooms.find((r) => r.id === device.room_id);
      device.x = Math.min(device.x, room.width); device.z = Math.min(device.z, room.depth);
      this.renderDevice();
    }
    if (input.name === "type") this.cleanAutomations();
    if (input.name === "name") {
      const option = Array.from($("device-select").options).find((item) => item.value === device.id);
      if (option) text(option, device.name);
    }
    this.renderDeviceList(); this.renderAutomations(); this.changed(); this.onSelect(device);
    text($("device-title"), device.name);
  }

  cleanAutomations() {
    this.home.automations = this.home.automations.filter((rule) =>
      this.home.devices.some((d) => d.id === rule.motion_device_id && d.type === "motion_sensor")
      && this.home.devices.some((d) => d.id === rule.target_device_id && LIGHTS.has(d.type)));
  }

  render() {
    $("home-name").value = this.home.name;
    options($("room-select"), this.home.rooms.map((room) => ({ value: room.id, label: room.name })), this.roomId);
    this.renderRoom(); this.renderDeviceList(); this.renderDevice(); this.renderAutomations();
    $("add-device").disabled = !this.home.rooms.length;
    $("discard-changes").disabled = !this.dirty;
  }

  renderRoom() {
    const room = this.home.rooms.find((r) => r.id === this.roomId);
    const form = $("room-form");
    form.replaceChildren();
    $("delete-room").disabled = !room;
    if (!room) return;
    const numeric = { type: "number", step: 0.1 };
    form.append(
      field("Nom", "name", room.name, { full: true }),
      field("Position X (m)", "x", room.x, { ...numeric, min: -100, max: 100 }),
      field("Position Z (m)", "z", room.z, { ...numeric, min: -100, max: 100 }),
      field("Largeur (m)", "width", room.width, { ...numeric, min: 1, max: 30 }),
      field("Profondeur (m)", "depth", room.depth, { ...numeric, min: 1, max: 30 }),
      field("Hauteur (m)", "height", room.height, { ...numeric, min: 2, max: 6 }),
      field("Couleur du sol", "color", room.color, { type: "color" }),
    );
    form.elements.name.maxLength = 100;
  }

  renderDevice() {
    const device = this.selected;
    options($("device-select"), [{ value: "", label: "Choisir un appareil" }, ...this.home.devices.map((d) => ({ value: d.id, label: d.name }))], this.deviceId || "");
    $("device-edit").hidden = !device;
    $("device-empty").hidden = Boolean(device);
    text($("device-title"), device?.name || "Choisir un appareil");
    const form = $("device-form");
    form.replaceChildren();
    if (!device) return;
    const room = this.home.rooms.find((r) => r.id === device.room_id);
    form.append(
      field("Nom", "name", device.name, { full: true }),
      field("Type", "type", device.type, { full: true, choices: this.catalog.map((type) => ({ value: type.type, label: type.label })) }),
      field("Pièce", "room_id", device.room_id, { full: true, choices: this.home.rooms.map((r) => ({ value: r.id, label: r.name })) }),
      field("Position X (m)", "x", device.x, { type: "number", min: 0, max: room?.width || 30, step: 0.1 }),
      field("Position Z (m)", "z", device.z, { type: "number", min: 0, max: room?.depth || 30, step: 0.1 }),
    );
    form.elements.name.maxLength = 100;
  }

  renderDeviceList() {
    const list = $("device-list");
    list.replaceChildren(); this.deviceRows.clear();
    for (const device of this.home.devices) {
      const button = el("button", device.id === this.deviceId ? "selected" : "");
      button.type = "button";
      const room = this.home.rooms.find((r) => r.id === device.room_id);
      button.append(el("span", "", device.name));
      const status = el("span", "device-state", room?.name || "");
      button.append(status);
      button.addEventListener("click", () => this.selectDevice(device.id));
      list.append(button); this.deviceRows.set(device.id, { button, status });
    }
    if (!this.home.devices.length) list.append(el("p", "muted small", "Aucun appareil pour le moment."));
  }

  renderAutomations() {
    const list = $("automation-list"); list.replaceChildren();
    for (const rule of this.home.automations) {
      const sensor = this.home.devices.find((d) => d.id === rule.motion_device_id);
      const lamp = this.home.devices.find((d) => d.id === rule.target_device_id);
      const row = el("div", "automation-item");
      row.append(el("span", "", `${sensor?.name || rule.motion_device_id} → ${lamp?.name || rule.target_device_id}`));
      const remove = el("button", "", "×");
      remove.type = "button"; remove.setAttribute("aria-label", `Supprimer la liaison ${sensor?.name} vers ${lamp?.name}`);
      remove.addEventListener("click", () => { this.home.automations = this.home.automations.filter((r) => r.id !== rule.id); this.renderAutomations(); this.changed(); });
      row.append(remove); list.append(row);
    }
    const sensors = this.home.devices.filter((d) => d.type === "motion_sensor");
    const lamps = this.home.devices.filter((d) => LIGHTS.has(d.type));
    const form = $("automation-form");
    options(form.elements.motion_device_id, [{ value: "", label: "Choisir un détecteur" }, ...sensors.map((d) => ({ value: d.id, label: d.name }))]);
    options(form.elements.target_device_id, [{ value: "", label: "Choisir une lampe" }, ...lamps.map((d) => ({ value: d.id, label: d.name }))]);
    form.querySelector("button").disabled = !sensors.length || !lamps.length;
  }

  validate() {
    if (!this.home.name.trim()) { $("home-name").focus(); this.onError("Donnez un nom à la maison."); return false; }
    for (const formId of ["room-form", "device-form"]) if (!$(formId).reportValidity()) return false;
    return true;
  }

  export() {
    if (!this.home) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(this.home, null, 2)], { type: "application/json" }));
    const link = el("a"); link.href = url; link.download = `${this.home.id || "maison"}.json`;
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async import(file) {
    if (!file) return;
    try {
      if (file.size > 1024 * 1024) throw new Error("Le fichier dépasse 1 Mo.");
      const home = JSON.parse(await file.text());
      if (home.schema_version !== 1 || typeof home.name !== "string" || !Array.isArray(home.rooms) || !Array.isArray(home.devices) || !Array.isArray(home.automations)) throw new Error("Format de maison invalide (version 1 attendue).");
      if (home.rooms.length > 30 || home.devices.length > 200) throw new Error("Le prototype accepte jusqu’à 30 pièces et 200 appareils.");
      for (const room of home.rooms) {
        if (typeof room.name !== "string" || typeof room.id !== "string" || !/^#[0-9a-f]{6}$/i.test(room.color)) throw new Error("Une pièce a un nom, un identifiant ou une couleur invalide.");
        for (const key of ["x", "z", "width", "depth", "height"]) if (!Number.isFinite(room[key]) || Math.abs(room[key]) > 100) throw new Error("Dimensions ou positions de pièce invalides.");
        if (room.width < 1 || room.depth < 1 || room.height < 2 || room.width > 30 || room.depth > 30 || room.height > 6) throw new Error("Dimensions de pièce hors limites.");
      }
      for (const device of home.devices) {
        if (typeof device.name !== "string" || typeof device.id !== "string" || !Number.isFinite(device.x) || !Number.isFinite(device.z) || !home.rooms.some((r) => r.id === device.room_id) || !this.catalog.some((type) => type.type === device.type)) throw new Error("Un appareil est invalide ou référence une pièce inconnue.");
      }
      const deviceIds = new Set(home.devices.map((device) => device.id));
      for (const rule of home.automations) {
        if (!rule || typeof rule.id !== "string" || !deviceIds.has(rule.motion_device_id) || !deviceIds.has(rule.target_device_id)) throw new Error("Une automatisation référence un appareil inconnu.");
      }
      this.home = home; this.roomId = home.rooms[0]?.id || null; this.deviceId = null;
      this.render(); this.changed(); this.onSelect(null);
    } catch (error) { this.onError(`Import impossible : ${error.message}`); }
    finally { $("import-file").value = ""; }
  }
}
