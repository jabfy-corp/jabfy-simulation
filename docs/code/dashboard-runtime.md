# `sim/dashboard/runtime.py`

> **Rôle** — État vivant du simulateur (`Dashboard`) : boucle de tick, événements, révision du contexte, file de commandes.

Dépôt : [jabfy-simulation](README.md) · 383 lignes · statut : **actif**

Docstring du module : *Live local dashboard. Sensor inputs are queued onto the simulator tick thread.*

## À retenir

- `_revision` l.78 : empreinte sha256 de l'état.
- `context()` l.155 : inventaire + bloc bus par appareil.
- `command` l.204 refuse si `context_revision` a changé (409) l.208 — le simulateur le vérifie, Core non.
- `_run` l.325 : un seul thread de tick.

## Contenu (ligne → élément)

| ligne | élément | note |
|---|---|---|
| 26 | `EVENT_LIMIT` | constante |
| 29 | classe `Dashboard` | A bounded event feed and immutable snapshots shared with HTTP readers. — méthodes : `__init__` 32, `start` 52, `_attach` 57, `_detach` 66, `close` 71, `_revision` 78, `_event` 81, `_on_message` 90, `_capture` 101, `house` 149, `context` 155, `_submit` 188, `command` 204, `sensor_event` 215, `replace_home` 233, `_require_connection` 297, `snapshot` 302, `trigger_motion` 310, `_run` 325 |

## Relations

- **Utilise** : [sim/dashboard/commands.py](dashboard-commands.md), [sim/devices/security.py](devices-security.md), [sim/home/catalog.py](home-catalog.md), [sim/home/conversion.py](home-conversion.md)
- **Utilisé par** : [sim/dashboard/app.py](dashboard-app.md)
