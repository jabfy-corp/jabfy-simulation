# Sécurité

jabfy-simulation est un laboratoire local. Il ne pilote que des appareils virtuels et ne doit pas être exposé sur un réseau.

## Ce qui est en place

- **Loopback par défaut.** L'interface écoute sur `127.0.0.1` ; dans le conteneur, 8080 et 1883 ne sont publiés que sur `127.0.0.1`. Core et Ollama n'ont aucun port publié sur l'hôte.
- **Même origine.** Les routes qui modifient l'état refusent une requête dont l'`Origin` n'est pas celle du serveur.
- **Destinations fixées par le serveur.** Les topics MQTT sont construits côté serveur ; une commande ne fournit ni destination, ni niveau de confiance, ni approbation.
- **Core à adresse configurée.** L'adresse de Core vient de la configuration serveur (`--core-url`, `JABFY_CORE_URL`), pas de la requête.
- **Vérification obligatoire.** Chaque commande passe par jabfy-guard (une règle par appareil, paramètres bornés, 60 commandes par minute) puis par le bus.
- **Audit chaîné.** Les décisions sont écrites dans un journal JSONL à chaîne SHA-256, à côté du fichier de la maison.
- **Pas de secret dans la maison.** Le document Home ne contient ni adresse réseau, ni jeton, ni décision de sécurité.
- **Pas de CDN.** Three.js est fourni localement avec sa licence ; aucun script externe n'est chargé.

## Limites

- Le simulateur autorise une commande sensible comme `unlock` émise depuis l'interface (`allow_sensitive_simulation`), ce que Core ne fait pas. Cette permission est propre au laboratoire.
- Aucune authentification : toute personne qui atteint le port 8080 peut piloter la maison.
- Les permissions du laboratoire ne doivent pas être reprises telles quelles pour du matériel réel (voir [Architecture du prototype de maison](house-architecture.md)).

## Signaler un problème

Les notes sur une faille non corrigée vont dans `docs/_interne/`, qui n'est jamais publié.
