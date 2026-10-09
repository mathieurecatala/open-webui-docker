# Décisions

- 09/10/2026 : pile locale Docker, sans cloud (pas de compte Azure) ; modèle local gratuit via Ollama ; outil métier
  branché sur l'API tri-offres.
- 09/10/2026 : Open WebUI épinglé en **v0.11.4**, version marquée « Latest » (non pré-version) sur
  <https://github.com/open-webui/open-webui/releases> le 09/10/2026, publiée le 21/09/2026 ; Ollama 0.40.2, Postgres 17.11-alpine, Caddy 2.11.7-alpine, Python 3.12.15-slim. Toutes les versions sont dans `.env`.
- 09/10/2026 : modèle `qwen2.5:1.5b` plutôt que `0.5b` : le 0.5b répondait « 3 » à « 2 + 2 » (test rouge) ;
  le 1.5b (environ 1 Go) répond juste et appelle correctement l'outil tri-offres.
- 09/10/2026 : tri-offres **simulé** dans la pile (`tri-offres-simule/`, bibliothèque standard Python) : le vrai service
  demande sa propre base et une collecte Internet. Le simulé reprend le contrat de l'API [tri-offres-api](https://github.com/mathieurecatala/tri-offres-api)
  (`GET /offres` : entreprise, gardee, texte, active, limite, decalage ; enveloppe total/limite/decalage/offres ;
  champs d'OffreSortie). Dates relatives au démarrage pour que « cette semaine » ait toujours des résultats.
- 09/10/2026 : l'outil filtre le télétravail sur le champ `lieu` (mots « télétravail », « remote »…) et la semaine sur
  `vue_premiere_fois`, côté outil : l'API ne propose pas ces filtres (son `texte` ne cherche que titre et lieu).
- 09/10/2026 : premier administrateur créé par `scripts/initialiser.sh` via l'API d'Open WebUI
  (`ENABLE_SIGNUP=false` + `ENABLE_INITIAL_ADMIN_SIGNUP=true` : seul le tout premier compte peut s'inscrire).
  Alternative non retenue : `WEBUI_ADMIN_EMAIL/PASSWORD` au démarrage (un script se relance sans risque et vérifie l'état). Risque documenté
  dans le README : lancer l'initialisation avant d'ouvrir l'accès réseau.
- 09/10/2026 : sauvegarde à chaud (pg_dump + tar du volume sans `cache/`, re-téléchargeable et lourd : 265 Mo).
  La restauration arrête Open WebUI et Caddy, recrée la base et conserve `cache/`.
- 09/10/2026 : les scripts appellent l'API d'Open WebUI depuis l'intérieur du conteneur (`docker compose exec`) : pas de
  problème de certificat ni de DNS, quel que soit `SITE_ADDRESS`.
- 09/10/2026 : CI sur `ubuntu-24.04` (et non `ubuntu-latest`, qui bascule vers Ubuntu 26 le 19/10). Modèle Ollama mis
  en cache (`OLLAMA_VOLUME=./cache-ollama`, clé = empreinte de `.env.example`). Gitleaks : binaire v8.30.1 téléchargé
  dans la CI, et hook pre-commit à la même version.
- 09/10/2026 : depuis les versions récentes, Open WebUI appelle les outils en mode « natif » par défaut ; par
  l'API sans discussion ouverte, il renvoie la demande d'appel sans l'exécuter. Test scindé : demande de l'outil en mode
  natif (nom et paramètres), puis exécution de bout en bout avec `params.function_calling = "legacy"`.
- 09/10/2026 : la CI démarre la pile en **v0.11.3** (avant-dernière version), initialise, puis lance
  `mettre-a-jour.sh` vers la version épinglée et rejoue tous les tests : la mise à jour est testée entre deux vraies
  versions à chaque push. `OPEN_WEBUI_VERSION_DEPART` dans la CI, à changer à chaque nouvelle version épinglée.
- 09/10/2026 : `scripts/commun.sh` laisse la priorité aux variables déjà définies dans l'environnement sur
  `.env`, comme docker compose. Sinon `mettre-a-jour.sh` remplaçait `OLLAMA_VOLUME=./cache-ollama` (CI) par `ollama`
  et recréait Ollama sur un volume vide (« Model not found » après la mise à jour, vu dans la CI).
