# `sim/dashboard/static/app.js`

> **Rôle** — Chef d'orchestre de l'UI : onglets, sauvegarde maison, santé, événements, polling.

Dépôt : [jabfy-simulation](README.md) · 264 lignes · statut : **actif**

## À retenir

- `poll` l.211, `start` l.244.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 24 | `notice()` |  |
| 30 | `showTab()` |  |
| 56 | `setMode()` |  |
| 91 | `selectDevice()` |  |
| 97 | `draftChanged()` |  |
| 117 | `saveHome()` |  |
| 146 | `renderHealth()` |  |
| 160 | `eventEntity()` |  |
| 173 | `renderEvents()` |  |
| 206 | `refreshSoon()` |  |
| 211 | `poll()` |  |
| 244 | `start()` |  |

## Relations

- **Utilise** : [sim/dashboard/static/ai.js](static-ai-js.md), [sim/dashboard/static/api.js](static-api-js.md), [sim/dashboard/static/controls.js](static-controls-js.md), [sim/dashboard/static/editor.js](static-editor-js.md), [sim/dashboard/static/scene.js](static-scene-js.md), [sim/dashboard/static/ui.js](static-ui-js.md)
- **Utilisé par** : aucun import direct (point d'entrée, appelé par HTTP, CLI ou navigateur)
