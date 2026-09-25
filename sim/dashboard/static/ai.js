/** Model proposals are previews. Applying them is a separate explicit action. */
import { api } from "./api.js";
import { $, el, text, options, feedback } from "./ui.js";

export class AIInspector {
  constructor({ getHome, getDirty, onAction }) {
    this.getHome = getHome;
    this.getDirty = getDirty;
    this.onAction = onAction;
    this.loaded = false;
    this.loading = false;
    this.busy = false;
    this.plan = null;
    this.modelsAvailable = false;
    $("refresh-ai").addEventListener("click", () => this.refresh());
    $("ai-form").addEventListener("submit", (event) => { event.preventDefault(); this.propose(); });
    $("apply-ai").addEventListener("click", () => this.apply());
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
    const outdated = this.plan && this.revision && this.plan.context_revision !== this.revision;
    $("apply-ai").disabled = !this.plan?.commands?.length || this.busy || this.getDirty() || Boolean(outdated);
    if (outdated) feedback("ai-feedback", "La maison a changé depuis cette proposition. Demandez une nouvelle proposition.", true);
    else if (this.getDirty()) feedback("ai-feedback", "Enregistrez la maison avant de demander ou d’appliquer une proposition.");
  }

  async propose() {
    if (this.busy || this.getDirty() || !$("ai-form").reportValidity()) return;
    this.busy = true; this.plan = null; $("ai-proposal").hidden = true;
    this.update(); feedback("ai-feedback", "L’IA analyse la maison. Cela peut prendre quelques instants…");
    try {
      const plan = await api.propose($("ai-model").value, $("ai-prompt").value);
      if (!Array.isArray(plan.commands)) throw new Error("La réponse ne contient pas de proposition valide.");
      this.plan = plan;
      text($("ai-explanation"), plan.explanation || "Vérifiez les actions suivantes.");
      $("ai-commands").replaceChildren();
      for (const command of plan.commands) {
        const device = this.getHome()?.devices.find((d) => d.id === command.device_id);
        const line = `${device?.name || command.device_id} : ${command.action}${Object.keys(command.params || {}).length ? ` ${JSON.stringify(command.params)}` : ""}`;
        $("ai-commands").append(el("li", "", line));
      }
      $("ai-proposal").hidden = false;
      feedback("ai-feedback", plan.commands.length ? "Aucune commande n’est envoyée avant votre clic sur Appliquer." : "L’IA ne propose aucune action sur les appareils.");
    } catch (error) { feedback("ai-feedback", error.message, true); }
    finally { this.busy = false; this.update(); }
  }

  async apply() {
    if (!this.plan || this.busy || this.getDirty() || $("apply-ai").disabled) return;
    this.busy = true; this.update();
    let executed = 0;
    try {
      for (const command of this.plan.commands) {
        feedback("ai-feedback", `Exécution ${executed + 1}/${this.plan.commands.length}…`);
        const result = await api.command(command.device_id, command.action, command.params || {}, this.plan.context_revision);
        if (result.status !== "executed") throw new Error(result.reason || "La commande a été refusée.");
        executed += 1;
      }
      feedback("ai-feedback", `${executed} action${executed > 1 ? "s" : ""} exécutée${executed > 1 ? "s" : ""}.`);
    } catch (error) { feedback("ai-feedback", `${executed} action(s) exécutée(s), puis arrêt : ${error.message}`, true); }
    finally { this.plan = null; this.busy = false; this.update(); this.onAction?.(); }
  }
}
