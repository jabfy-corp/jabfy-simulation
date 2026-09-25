/** Small DOM helpers. Configuration and model text are never inserted as HTML. */
export const $ = (id) => document.getElementById(id);
export function el(tag, className = "", value) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = value;
  return node;
}
export function text(node, value) {
  const next = String(value ?? "");
  if (node.textContent !== next) node.textContent = next;
}
export function feedback(id, message, error = false) {
  text($(id), message);
  $(id).dataset.error = String(error);
}
export function options(select, items, value) {
  select.replaceChildren();
  for (const item of items) {
    const option = el("option", "", item.label);
    option.value = item.value;
    select.append(option);
  }
  if (value != null) select.value = value;
}
export function field(label, name, value, { type = "text", full = false, min, max, step, choices, required = true } = {}) {
  const wrapper = el("label", `field${full ? " full" : ""}`, label);
  const input = el(choices ? "select" : "input");
  input.name = name;
  if (choices) options(input, choices, value);
  else {
    input.type = type;
    input.value = value ?? "";
    if (min !== undefined) input.min = min;
    if (max !== undefined) input.max = max;
    if (step !== undefined) input.step = step;
  }
  input.required = required;
  wrapper.append(input);
  return wrapper;
}
export const format = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
export const clock = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
export const humanize = (value) => String(value || "").replaceAll("_", " ");
