# `sim/dashboard/static/ai.js`

> **Rôle** — Onglet IA : envoie la demande à `/api/ai/prompt` puis interroge le run toutes les 500 ms.

Dépôt : [jabfy-simulation](README.md) · 96 lignes · statut : **actif**

## À retenir

- `send` l.58, polling l.66-69.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 8 | classe `AIInspector` | méthodes : `constructor` 9, `open` 22, `refresh` 24, `update` 52, `send` 58, `render` 79 |

## Relations

- **Utilise** : [sim/dashboard/static/api.js](static-api-js.md), [sim/dashboard/static/ui.js](static-ui-js.md)
- **Utilisé par** : [sim/dashboard/static/app.js](static-app-js.md)
