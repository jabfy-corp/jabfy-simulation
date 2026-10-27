/** Jabfy Core reasons and acts through the bus; this panel only follows the run. */
import { api } from "./api.js";
import { $, el, text, options, feedback } from "./ui.js";

const TERMINAL = new Set(["completed", "failed", "rejected", "no_action"]);
const STEP_LABELS = { pending: "en attente", requested: "demandée", approved: "approuvée", rejected: "refusée", executed: "exécutée", failed: "échec" };

export class AIInspector {
  constructor({ getHome, getDirty, onAction }) {
    this.getHome = getHome;
    this.getDirty = getDirty;
    this.onAction = onAction;
    this.loaded = false;
    this.loading = false;
    this.busy = false;
    this.runId = null;
    this.modelsAvailable = false;
    $("refresh-ai").addEventListener("click", () => this.refresh());
    $("ai-form").addEventListener("submit", (event) => { event.preventDefault(); this.send(); });
  }

  async open() { if (!this.loaded && !this.loading) await this.refresh(); }

  async refresh() {
    if (this.loading) return;
    this.loading = true;
    $("refresh-ai").disabled = true;
    text($("ai-status"), "Recherche des modèles et lecture de l’inventaire…");
    const [context, models] = await Promise.allSettled([api.context(), api.models()]);
    if (context.status === "fulfilled") text($("ai-context"), JSON.stringify(context.value, null, 2));
    else text($("ai-context"), `Inventaire indisponible : ${context.reason.message}`);
    if (models.status === "fulfilled") {
      const data = models.value;
      const items = Array.isArray(data) ? data : data.models || [];
      const modelOptions = items.map((model) => typeof model === "string" ? { value: model, label: model } : { value: model.id || model.name, label: model.name || model.id });
      this.modelsAvailable = data.available !== false && modelOptions.length > 0;
      options($("ai-model"), modelOptions.length ? modelOptions : [{ value: "", label: "Aucun modèle disponible" }]);
      const unavailableReason = data.available === false && /ollama/i.test(String(data.reason || ""))
        ? "Ollama est indisponible. Démarrez Ollama avec un modèle local, puis actualisez."
        : data.reason || "Aucun modèle local disponible. Démarrez Ollama et installez un modèle pour utiliser l’IA.";
      text($("ai-status"), this.modelsAvailable ? `${modelOptions.length} modèle${modelOptions.length > 1 ? "s" : ""} disponible${modelOptions.length > 1 ? "s" : ""}.` : unavailableReason);
    } else {
      this.modelsAvailable = false;
      options($("ai-model"), [{ value: "", label: "IA indisponible" }]);
      text($("ai-status"), `IA indisponible : ${models.reason.message}`);
    }
    this.loading = false; this.loaded = true;
    $("refresh-ai").disabled = false;
    this.update();
  }

  update(revision) {
    if (revision !== undefined) this.revision = revision;
    $("ask-ai").disabled = !this.modelsAvailable || this.busy || this.getDirty();
    if (this.getDirty()) feedback("ai-feedback", "Enregistrez la maison avant d’envoyer une consigne.");
  }

  async send() {
    if (this.busy || this.getDirty() || !$("ai-form").reportValidity()) return;
    this.busy = true; $("ai-proposal").hidden = true;
    this.update(); feedback("ai-feedback", "Consigne envoyée à Jabfy Core…");
    try {
      const { prompt_id: id } = await api.prompt($("ai-model").value, $("ai-prompt").value);
      this.runId = id;
      let run = await api.run(id);
      while (this.runId === id && !TERMINAL.has(run.status)) {
        this.render(run);
        await new Promise((resolve) => setTimeout(resolve, 500));
        run = await api.run(id);
      }
      this.render(run);
      if (run.status === "completed") feedback("ai-feedback", `${run.steps.length} action${run.steps.length > 1 ? "s" : ""} exécutée${run.steps.length > 1 ? "s" : ""}.`);
      else if (run.status === "no_action") feedback("ai-feedback", "Jabfy Core n’a lancé aucune action.");
      else feedback("ai-feedback", `Arrêt : ${run.error || "la séquence n’a pas abouti."}`, true);
    } catch (error) { feedback("ai-feedback", error.message, true); }
    finally { this.busy = false; this.update(); this.onAction?.(); }
  }

  render(run) {
    if (run.status === "queued" || run.status === "planning") {
      feedback("ai-feedback", "Jabfy Core analyse la maison…");
      return;
    }
    text($("ai-explanation"), run.explanation || "");
    $("ai-commands").replaceChildren();
    for (const step of run.steps) {
      const device = this.getHome()?.devices.find((d) => d.id === step.device_id);
      const delay = step.delay_ms ? `après ${step.delay_ms / 1000} s · ` : "";
      const params = Object.keys(step.params || {}).length ? ` ${JSON.stringify(step.params)}` : "";
      const reason = step.reason && step.status !== "executed" ? ` (${step.reason})` : "";
      $("ai-commands").append(el("li", "", `${delay}${device?.name || step.device_id} : ${step.action}${params} — ${STEP_LABELS[step.status] || step.status}${reason}`));
    }
    $("ai-proposal").hidden = false;
    if (run.status === "running") feedback("ai-feedback", "Exécution en cours…");
  }
}
