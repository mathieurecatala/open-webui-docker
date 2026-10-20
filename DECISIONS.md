# Décisions

- 09/10/2026 : pile locale Docker, sans cloud, avec un modèle local gratuit via Ollama et un outil métier d'exemple
  branché sur une API interne simulée.
- 09/10/2026 : Open WebUI épinglé en **v0.11.4**, version marquée « Latest » (non pré-version) sur
  <https://github.com/open-webui/open-webui/releases> le 09/10/2026, publiée le 21/09/2026. Ollama 0.40.2, Postgres 17.11-alpine, Caddy 2.11.7-alpine, Python 3.12.15-slim. Toutes les versions sont dans `.env`.
- 09/10/2026 : modèle `qwen2.5:1.5b` plutôt que `0.5b` : le 0.5b répondait « 3 » à « 2 + 2 » (test rouge),
  le 1.5b (environ 1 Go) répond juste et appelle correctement l'outil métier.
- 09/10/2026 : premier administrateur créé par `scripts/initialiser.sh` via l'API d'Open WebUI
  (`ENABLE_SIGNUP=false` + `ENABLE_INITIAL_ADMIN_SIGNUP=true` : seul le tout premier compte peut s'inscrire).
  Alternative non retenue : `WEBUI_ADMIN_EMAIL/PASSWORD` au démarrage (un script se relance sans risque et vérifie l'état). Risque documenté
  dans le README : lancer l'initialisation avant d'ouvrir l'accès réseau.
- 09/10/2026 : sauvegarde à chaud (pg_dump + tar du volume sans `cache/`, re-téléchargeable et lourd : 265 Mo).
  La restauration arrête Open WebUI et Caddy, recrée la base et conserve `cache/`.
- 09/10/2026 : les scripts appellent l'API d'Open WebUI depuis l'intérieur du conteneur (`docker compose exec`) : pas de
  problème de certificat ni de DNS, quel que soit `SITE_ADDRESS`.
- 09/10/2026 : CI sur `ubuntu-24.04` (et non `ubuntu-latest`, qui a basculé vers Ubuntu 26 le 19/10/2026). Modèle Ollama mis
  en cache (`OLLAMA_VOLUME=./cache-ollama`, clé = empreinte de `.env.example`). Gitleaks : binaire v8.30.1 téléchargé
  dans la CI, et hook pre-commit à la même version.
- 09/10/2026 : depuis les versions récentes, Open WebUI appelle les outils en mode « natif » par défaut. Par
  l'API sans discussion ouverte, il renvoie la demande d'appel sans l'exécuter. Test scindé : demande de l'outil en mode
  natif (nom et paramètres), puis exécution de bout en bout avec `params.function_calling = "legacy"`.
- 09/10/2026 : la CI démarre la pile en **v0.11.3** (avant-dernière version), initialise, puis lance
  `mettre-a-jour.sh` vers la version épinglée et rejoue tous les tests : la mise à jour est testée entre deux vraies
  versions à chaque push. `OPEN_WEBUI_VERSION_DEPART` dans la CI, à changer à chaque nouvelle version épinglée.
- 09/10/2026 : `scripts/commun.sh` laisse la priorité aux variables déjà définies dans l'environnement sur
  `.env`, comme docker compose. Sinon `mettre-a-jour.sh` remplaçait `OLLAMA_VOLUME=./cache-ollama` (CI) par `ollama`
  et recréait Ollama sur un volume vide (« Model not found » après la mise à jour, vu dans la CI).
- 20/10/2026 : outil métier d'exemple, un service de tickets de support **simulé** dans la pile (`tickets-simule/`, bibliothèque standard Python) : un vrai
  outil de tickets demande son propre serveur et des données réelles. Contrat : `GET /tickets` (statut, priorite,
  texte, limite, decalage, et statut et priorite acceptent plusieurs valeurs séparées par des virgules). Réponse
  dans une enveloppe total/limite/decalage/tickets. Données fictives (personnes et services inventés), dates relatives au démarrage pour
  que « cette semaine » ait toujours des résultats. Chaque filtre exclut au moins un ticket (fermé, ancien, non
  urgent, autre sujet) : les tests vérifient vraiment quelque chose.
- 20/10/2026 : l'outil demande au service les tickets encore ouverts (`statut=ouvert,en_cours`), puis filtre lui-même
  le sujet (titre, description, catégorie, sans tenir compte des accents), l'urgence et la semaine (`cree_le`) : le
  service ne filtre pas par date.
