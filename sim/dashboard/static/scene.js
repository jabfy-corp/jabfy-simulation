/** WebGL house view. Geometry comes from the draft; light/state comes only from telemetry. */
import * as THREE from "three";
import { OrbitControls } from "./vendor/OrbitControls.js";

const LAMPS = new Set(["on_off_light", "dimmer_light", "rgb_bulb"]);

export class HouseScene {
  constructor(container, { onSelect, onMode }) {
    this.container = container;
    this.onSelect = onSelect;
    this.onMode = onMode;
    this.mode = "orbit";
    this.devices = new Map();
    this.walls = [];
    this.labels = [];
    this.keys = new Set();
    this.home = { rooms: [], devices: [] };
    this.selected = null;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#e8ebde");
    this.camera = new THREE.PerspectiveCamera(43, 1, 0.05, 500);
    this.camera.position.set(12, 13, 15);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    container.append(this.renderer.domElement);
    this.renderer.domElement.tabIndex = 0;
    this.renderer.domElement.setAttribute("aria-label", "Maison 3D interactive. Cliquez pour sélectionner un appareil. En visite : flèches pour se déplacer, glisser pour regarder, Échap pour sortir.");
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.maxPolarAngle = Math.PI / 2.1;
    this.controls.minDistance = 3;
    this.controls.maxDistance = 160;
    this.scene.add(new THREE.HemisphereLight(0xfff6de, 0x819474, 1.65));
    const sun = new THREE.DirectionalLight(0xfff9e6, 2.4);
    sun.position.set(10, 18, 8);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    Object.assign(sun.shadow.camera, { left: -30, right: 30, top: 30, bottom: -30, near: 1, far: 80 });
    sun.shadow.normalBias = 0.04;
    this.scene.add(sun);
    this.house = new THREE.Group();
    this.scene.add(this.house);
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), this.material("#dde3d0"));
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.15;
    ground.receiveShadow = true;
    this.scene.add(ground);
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.bindPointer();
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.resize();
    this.lastTime = performance.now();
    this.renderer.setAnimationLoop((time) => this.animate(time));
  }

  material(color, extra = {}) {
    return new THREE.MeshStandardMaterial({ color, roughness: 0.8, ...extra });
  }

  box(parent, x, y, z, width, height, depth, color) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), this.material(color));
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  }

  cylinder(parent, radius, height, y, color) {
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, height, 24), this.material(color));
    mesh.position.y = y;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  }

  setHome(home, { fit = false } = {}) {
    this.home = home;
    this.house.traverse((item) => {
      item.geometry?.dispose();
      const materials = Array.isArray(item.material) ? item.material : [item.material];
      for (const material of materials) { material?.map?.dispose(); material?.dispose(); }
    });
    this.house.clear();
    this.devices.clear();
    this.lightCount = 0;
    this.walls = [];
    this.labels = [];
    for (const room of home.rooms) this.buildRoom(room);
    for (const device of home.devices) {
      const room = home.rooms.find((item) => item.id === device.room_id);
      if (room) this.buildDevice(device, room);
    }
    this.updateWalls();
    this.select(this.selected);
    if (this.lastStates) this.updateState(this.lastStates);
    if (fit || !this.hasFramed) { this.fit(); this.hasFramed = true; }
  }

  buildRoom(room) {
    const group = new THREE.Group();
    group.position.set(room.x, 0, room.z);
    this.house.add(group);
    this.box(group, room.width / 2, 0, room.depth / 2, room.width, 0.16, room.depth, room.color || "#d9d2bc");
    // A simple open doorway on each side makes the single-floor prototype traversable.
    const opening = Math.min(1.1, room.width * 0.5, room.depth * 0.5);
    const height = room.height || 2.6;
    const wallColor = "#f2eee0";
    for (const [length, axis, fixed, cutaway] of [
      [room.width, "x", 0, false], [room.width, "x", room.depth, true],
      [room.depth, "z", 0, false], [room.depth, "z", room.width, true],
    ]) {
      const wall = new THREE.Group();
      group.add(wall);
      const side = (length - opening) / 2;
      for (const midpoint of [side / 2, length - side / 2]) {
        this.box(wall, axis === "x" ? midpoint : fixed, height / 2 + 0.08, axis === "z" ? midpoint : fixed,
          axis === "x" ? side : 0.13, height, axis === "z" ? side : 0.13, wallColor);
      }
      const lintelHeight = Math.max(0.1, height - 2.1);
      this.box(wall, axis === "x" ? length / 2 : fixed, height - lintelHeight / 2 + 0.08,
        axis === "z" ? length / 2 : fixed, axis === "x" ? opening : 0.13,
        lintelHeight, axis === "z" ? opening : 0.13, wallColor);
      this.walls.push({ group: wall, cutaway });
    }
    const label = this.label(room.name, `${Math.round(room.width * room.depth * 10) / 10} m²`);
    label.position.set(room.width / 2, 0.2, room.depth / 2);
    group.add(label);
    this.labels.push(label);
    this.furnish(group, room);
  }

  furnish(group, room) {
    if (room.width < 3 || room.depth < 3) return;
    const name = room.name.toLowerCase();
    if (/salon|séjour|living/.test(name)) {
      this.box(group, room.width * 0.38, 0.38, room.depth - 0.8, 1.8, 0.55, 0.72, "#91a486");
      this.box(group, room.width * 0.38, 0.78, room.depth - 1.08, 1.8, 0.45, 0.16, "#91a486");
      this.box(group, room.width * 0.38, 0.4, room.depth - 1.9, 1.25, 0.1, 0.7, "#b5946d");
      this.box(group, room.width * 0.38, 0.22, room.depth - 1.9, 0.65, 0.3, 0.4, "#b5946d");
    } else if (/cuisine|kitchen/.test(name)) {
      this.box(group, room.width - 0.4, 0.55, room.depth * 0.7, 0.55, 0.9, Math.min(2, room.depth * 0.5), "#c4c8b7");
      this.box(group, room.width - 0.4, 1.04, room.depth * 0.7, 0.64, 0.09, Math.min(2.1, room.depth * 0.5 + 0.1), "#ede8db");
    } else if (/chambre|bedroom/.test(name)) {
      this.box(group, room.width * 0.65, 0.33, room.depth * 0.55, 1.4, 0.45, 2, "#c8b495");
      this.box(group, room.width * 0.65, 0.61, room.depth * 0.55, 1.38, 0.16, 1.95, "#eeebdd");
    }
  }

  label(title, subtitle) {
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 144;
    const context = canvas.getContext("2d");
    context.fillStyle = "#526448";
    context.textAlign = "center";
    context.font = "600 36px system-ui";
    context.fillText(title.slice(0, 28), 256, 59);
    context.fillStyle = "#7d896b";
    context.font = "25px system-ui";
    context.fillText(subtitle, 256, 103);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthTest: false, transparent: true }));
    sprite.scale.set(2.8, 0.79, 1);
    return sprite;
  }

  buildDevice(device, room) {
    const group = new THREE.Group();
    group.position.set(room.x + device.x, 0.1, room.z + device.z);
    group.userData.deviceId = device.id;
    this.house.add(group);
    const selection = new THREE.Mesh(new THREE.TorusGeometry(0.36, 0.025, 8, 48), new THREE.MeshBasicMaterial({ color: "#50814a" }));
    selection.rotation.x = -Math.PI / 2;
    selection.position.y = 0.04;
    group.add(selection);
    let indicator;
    let light;
    let door;
    if (LAMPS.has(device.type)) {
      this.cylinder(group, 0.23, 0.07, 0.08, "#6d785e");
      this.cylinder(group, 0.035, 1.25, 0.7, "#b1986c");
      indicator = new THREE.Mesh(new THREE.SphereGeometry(0.24, 24, 16), this.material("#dedfce", { emissive: 0xffdb82, emissiveIntensity: 0 }));
      indicator.position.y = 1.44;
      group.add(indicator);
      // Bound shader cost for large imported homes; every bulb still shows its state.
      if (this.lightCount < 16) {
        light = new THREE.PointLight(0xffd37d, 0, 7, 2);
        light.position.set(0, 1.65, 0);
        group.add(light);
        this.lightCount += 1;
      }
    } else if (device.type === "door_lock") {
      door = this.box(group, 0, 1, 0, 0.78, 1.9, 0.1, "#a8926b");
      indicator = this.box(group, 0.23, 0.95, 0.08, 0.1, 0.2, 0.05, "#91a47d");
    } else if (device.type === "smart_tv") {
      this.box(group, 0, 0.35, 0, 1.05, 0.5, 0.38, "#b49d7b");
      this.box(group, 0, 1.05, 0, 1.18, 0.72, 0.1, "#424d40");
      indicator = this.box(group, 0, 1.05, 0.06, 1.08, 0.61, 0.012, "#2d382f");
    } else {
      const thermostat = device.type === "thermostat";
      this.cylinder(group, 0.15, 0.05, 0.03, "#a6ad95");
      this.cylinder(group, 0.025, 0.9, 0.5, "#b4b7a4");
      this.box(group, 0, 1.01, 0, thermostat ? 0.37 : 0.28, thermostat ? 0.32 : 0.25, 0.14, "#f0f0e5");
      indicator = this.box(group, 0, 1.02, 0.08, 0.15, 0.12, 0.018, "#879679");
    }
    group.traverse((item) => { if (item.isMesh) item.userData.deviceId = device.id; });
    this.devices.set(device.id, { group, indicator, light, selection, door, type: device.type });
  }

  updateState(devices) {
    this.lastStates = devices;
    for (const [id, visual] of this.devices) {
      const live = devices.find((device) => device.id === id && device.type === visual.type);
      const state = live?.state || {};
      const on = String(state.state || "").toUpperCase() === "ON";
      if (LAMPS.has(visual.type)) {
        const brightness = state.brightness == null ? 1 : Math.max(0, Math.min(1, state.brightness / 254));
        const color = state.color && typeof state.color === "object" ? new THREE.Color().setRGB((state.color.r ?? 255) / 255, (state.color.g ?? 225) / 255, (state.color.b ?? 170) / 255, THREE.SRGBColorSpace) : new THREE.Color("#ffdf92");
        if (visual.light) {
          visual.light.color.copy(color);
          visual.light.intensity = on ? 30 * brightness : 0;
        }
        visual.indicator.material.color.set(on ? "#fff3cc" : "#b2b5a2");
        visual.indicator.material.emissive.copy(color);
        visual.indicator.material.emissiveIntensity = on ? 2 * brightness : 0;
      } else {
        const alert = state.smoke === true || state.alarm === true;
        const active = state.occupancy === true || state.running_state === "heat" || state.state === "UNLOCK";
        const tvOn = String(state.switch ?? state.power).toLowerCase() === "on";
        visual.indicator.material.color.set(!live ? "#9ca394" : alert ? "#df7850" : active ? "#d1a34c" : visual.type === "smart_tv" ? tvOn ? "#75b6a5" : "#26392d" : "#739f63");
        visual.indicator.material.emissive.set(alert ? "#9c3620" : tvOn ? "#236c58" : "#000000");
        visual.indicator.material.emissiveIntensity = tvOn || alert ? 0.8 : 0;
        if (visual.door) visual.door.rotation.y = state.state === "UNLOCK" ? -0.35 : 0;
      }
    }
  }

  select(id) {
    this.selected = id;
    for (const [deviceId, device] of this.devices) device.selection.visible = id === deviceId;
  }

  bounds() {
    if (!this.home.rooms.length) return { minX: -3, maxX: 3, minZ: -3, maxZ: 3 };
    return {
      minX: Math.min(...this.home.rooms.map((r) => r.x)), maxX: Math.max(...this.home.rooms.map((r) => r.x + r.width)),
      minZ: Math.min(...this.home.rooms.map((r) => r.z)), maxZ: Math.max(...this.home.rooms.map((r) => r.z + r.depth)),
    };
  }

  fit() {
    this.mode = "orbit";
    this.controls.enabled = true;
    const b = this.bounds();
    const center = new THREE.Vector3((b.minX + b.maxX) / 2, 0.5, (b.minZ + b.maxZ) / 2);
    const size = Math.max(b.maxX - b.minX, b.maxZ - b.minZ, 5);
    const distance = size * Math.max(1.1, 0.85 / Math.max(this.camera.aspect, 0.4));
    this.camera.position.copy(center).add(new THREE.Vector3(distance * 0.9, distance * 1.06, distance));
    this.controls.target.copy(center);
    this.controls.update();
    this.updateWalls();
    this.onMode?.("orbit");
  }

  visit(roomId) {
    const room = this.home.rooms.find((r) => r.id === roomId) || this.home.rooms[0];
    if (!room) return;
    this.mode = "visit";
    this.controls.enabled = false;
    this.camera.position.set(room.x + room.width * 0.23, Math.min(1.6, room.height - 0.2), room.z + room.depth * 0.8);
    this.yaw = Math.atan2(
      this.camera.position.x - (room.x + room.width / 2),
      this.camera.position.z - (room.z + room.depth / 2),
    );
    this.pitch = -0.08;
    this.camera.rotation.order = "YXZ";
    this.camera.rotation.set(this.pitch, this.yaw, 0);
    this.updateWalls();
    this.onMode?.("visit");
    this.renderer.domElement.focus({ preventScroll: true });
  }

  updateWalls() {
    for (const wall of this.walls) wall.group.visible = this.mode === "visit" || !wall.cutaway;
    for (const label of this.labels) label.visible = this.mode !== "visit";
  }

  bindPointer() {
    const canvas = this.renderer.domElement;
    canvas.addEventListener("pointerdown", (event) => {
      this.down = { x: event.clientX, y: event.clientY, lastX: event.clientX, lastY: event.clientY, moved: false };
      if (this.mode === "visit") canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener("pointermove", (event) => {
      if (!this.down) return;
      if (Math.hypot(event.clientX - this.down.x, event.clientY - this.down.y) > 5) this.down.moved = true;
      if (this.mode === "visit") {
        this.yaw -= (event.clientX - this.down.lastX) * 0.005;
        this.pitch = THREE.MathUtils.clamp(this.pitch - (event.clientY - this.down.lastY) * 0.005, -1.25, 1.25);
        this.camera.rotation.set(this.pitch, this.yaw, 0);
      }
      this.down.lastX = event.clientX;
      this.down.lastY = event.clientY;
    });
    canvas.addEventListener("pointerup", (event) => {
      if (this.down && !this.down.moved) {
        const rect = canvas.getBoundingClientRect();
        this.pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
        this.raycaster.setFromCamera(this.pointer, this.camera);
        const hits = this.raycaster.intersectObjects([...this.devices.values()].map((d) => d.group), true);
        const id = hits.find((hit) => hit.object.userData.deviceId)?.object.userData.deviceId;
        if (id) this.onSelect?.(id);
      }
      this.down = null;
    });
    canvas.addEventListener("pointercancel", () => { this.down = null; });
    window.addEventListener("keydown", (event) => {
      if (this.mode !== "visit" || /INPUT|TEXTAREA|SELECT|BUTTON/.test(event.target.tagName)) return;
      if (event.key === "Escape") { this.fit(); return; }
      const mapping = { w: "forward", z: "forward", ArrowUp: "forward", s: "back", ArrowDown: "back", a: "left", q: "left", ArrowLeft: "left", d: "right", ArrowRight: "right" };
      const direction = mapping[event.key];
      if (direction) { this.keys.add(direction); event.preventDefault(); }
    });
    window.addEventListener("keyup", () => this.keys.clear());
    window.addEventListener("blur", () => { this.keys.clear(); this.down = null; });
  }

  move(direction, active) {
    if (active) this.keys.add(direction);
    else this.keys.delete(direction);
  }

  animate(time) {
    const dt = Math.min((time - this.lastTime) / 1000, 0.05);
    this.lastTime = time;
    if (this.mode === "visit") {
      const forward = (this.keys.has("forward") ? 1 : 0) - (this.keys.has("back") ? 1 : 0);
      const side = (this.keys.has("right") ? 1 : 0) - (this.keys.has("left") ? 1 : 0);
      const length = Math.hypot(forward, side) || 1;
      this.camera.position.x += (-Math.sin(this.yaw) * forward + Math.cos(this.yaw) * side) / length * dt * 2.4;
      this.camera.position.z += (-Math.cos(this.yaw) * forward - Math.sin(this.yaw) * side) / length * dt * 2.4;
      const bounds = this.bounds();
      this.camera.position.x = THREE.MathUtils.clamp(this.camera.position.x, bounds.minX - 2, bounds.maxX + 2);
      this.camera.position.z = THREE.MathUtils.clamp(this.camera.position.z, bounds.minZ - 2, bounds.maxZ + 2);
    } else this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  resize() {
    const { width, height } = this.container.getBoundingClientRect();
    if (!width || !height) return;
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }
}
