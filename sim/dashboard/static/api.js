/** Same-origin JSON API; mutations always reach the real simulator backend. */
export async function request(path, { timeout = 15000, ...options } = {}) {
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), timeout);
  try {
    const response = await fetch(path, {
      cache: "no-store", ...options,
      headers: { "Content-Type": "application/json", ...options.headers }, signal: abort.signal,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail ?? data.error;
      const message = typeof detail === "string" ? detail
        : Array.isArray(detail) ? detail.map((entry) => `${(entry.loc || []).slice(1).join(".")} : ${entry.msg}`).join(" · ")
          : `Le serveur a répondu ${response.status}.`;
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Le serveur met trop de temps à répondre.");
    throw error;
  } finally { clearTimeout(timer); }
}

export const api = {
  state: () => request("/api/state", { timeout: 5000 }),
  home: () => request("/api/home"),
  catalog: () => request("/api/catalog"),
  save: (home) => request("/api/home", { method: "PUT", body: JSON.stringify(home), timeout: 60000 }),
  command: (id, action, params = {}, context_revision) => request(`/api/devices/${encodeURIComponent(id)}/commands`, {
    method: "POST", body: JSON.stringify({ action, params, ...(context_revision === undefined ? {} : { context_revision }) }), timeout: 30000,
  }),
  event: (id, event) => request(`/api/devices/${encodeURIComponent(id)}/events`, { method: "POST", body: JSON.stringify({ event }) }),
  context: () => request("/api/ai/context"),
  models: () => request("/api/ai/models", { timeout: 15000 }),
  propose: (model, prompt) => request("/api/ai/propose", { method: "POST", body: JSON.stringify({ model, prompt }), timeout: 180000 }),
};
