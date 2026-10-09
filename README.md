# Open WebUI auto-hébergé avec Docker

[![CI](https://github.com/mathieurecatala/open-webui-docker/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/mathieurecatala/open-webui-docker/actions/workflows/ci.yml)

## 1. Ce que c'est (et ce que ce n'est pas)

**Projet personnel de Mathieu Recatala, octobre 2026, construit avec Claude Code.** Il est déployé **en local avec Docker, sans cloud** :
pas d'Azure ni d'autre hébergeur (pas de compte pour l'instant). Aucun client, aucune mission : c'est un kit que j'ai
construit pour apprendre à installer proprement un assistant IA privé pour une petite entreprise.

Le kit installe [Open WebUI](https://github.com/open-webui/open-webui) (interface de discussion type ChatGPT) avec un
modèle d'IA qui tourne **sur la machine elle-même, sans clé ni abonnement**, et le rend exploitable par quelqu'un
d'autre : sauvegarde, restauration, mise à jour, tests automatiques, dossier d'exploitation.

## 2. Démarrage en 3 commandes

Prérequis : Docker avec Compose v2, Python 3 (pour les scripts), environ 18 Go de disque (mesuré le 09/10/2026 : images Docker 17 Go, dont Ollama 9 Go et Open WebUI 6,5 Go, plus le modèle
1 Go ; compter 7 Go de plus pendant une mise à jour d'Open WebUI) et 4 Go de RAM libres.

```bash
cp .env.example .env
docker compose up -d
./scripts/initialiser.sh      # crée l'administrateur, installe l'outil, attend le modèle
```

Puis ouvrir <https://localhost> (certificat local : accepter l'avertissement du navigateur) et se connecter avec
`ADMIN_EMAIL` / `ADMIN_PASSWORD` du fichier `.env`.

Tests : `pip install -r requirements-tests.txt && pytest` (la pile doit tourner).

## 3. Architecture

```
                    Navigateur des salariés
                            │  HTTPS (443) ; HTTP 80 redirigé
                            ▼
                 ┌──────────────────────┐
                 │  Caddy (proxy)       │  seul service qui publie des ports
                 └──────────┬───────────┘
                            │  réseau Docker interne
                            ▼
                 ┌──────────────────────┐
                 │  Open WebUI          │  interface + API, outil Python « tri-offres »
                 └──┬────────┬───────┬──┘
                    │        │       │
          ┌─────────▼──┐ ┌───▼────┐ ┌▼────────────────────┐
          │ Postgres   │ │ Ollama │ │ tri-offres (simulé) │
          │ comptes,   │ │ modèle │ │ API des offres      │
          │ discussions│ │ local  │ │ d'emploi            │
          └────────────┘ └────────┘ └─────────────────────┘
  Volumes : postgres, open-webui (fichiers), ollama (modèles), caddy (certificats)
```

L'outil métier (`outils/tri_offres.py`) est un « Tool » Open WebUI : quand on demande à l'assistant *« Quelles offres
en télétravail mentionnent Docker cette semaine ? »* avec l'outil activé (bouton « + » > Outils dans la discussion),
le modèle peut appeler la fonction `chercher_offres`, qui interroge l'API `GET /offres` du service tri-offres et renvoie
la liste. Open WebUI utilise par défaut l'appel d'outil « natif » (le modèle demande lui-même l'outil) ; les tests
vérifient cette demande, puis l'exécution complète par l'API en mode « legacy ». C'est le principe pour relier l'assistant aux données d'une entreprise (catalogue, tickets, stock...).

## 4. Choix techniques et pourquoi

| Choix | Pourquoi |
|---|---|
| Open WebUI **v0.11.4 épinglée** | Version marquée « Latest » sur la page des versions d'Open WebUI le 09/10/2026 (publiée le 21/09/2026). Une version précise ne change pas toute seule ; on met à jour quand on l'a décidé, avec `scripts/mettre-a-jour.sh`. |
| **Postgres** plutôt que SQLite | Base robuste, sauvegarde à chaud avec `pg_dump`, prête pour plusieurs utilisateurs simultanés. |
| **Ollama + qwen2.5:1.5b** | Gratuit, tourne sur CPU (environ 1 Go). Le 0.5b, essayé d'abord, répondait « 3 » à « 2 + 2 » : trop peu fiable. |
| **Caddy** | HTTPS automatique (Let's Encrypt en production, certificat local en dev) avec un fichier de configuration de 20 lignes. |
| **tri-offres simulé** | Le vrai service a besoin de sa base et d'une collecte sur Internet ; le service simulé reprend son contrat d'API (`GET /offres`, mêmes filtres, mêmes champs) avec des données fictives : démonstration et CI reproductibles. |
| Scripts **bash** | Lisibles par un administrateur système, sans outil à installer. |
| Tests **pytest** | Tournent contre la vraie pile : santé, connexion, réponse du modèle, appel de l'outil par le modèle, sauvegarde/restauration. |

### Brancher une API compatible OpenAI à la place (ou en plus) du modèle local

Dans `.env` (jamais dans le dépôt) :

```bash
OPENAI_API_BASE_URL=https://api.fournisseur.example/v1
OPENAI_API_KEY=la-cle-fournie-par-le-fournisseur
```

puis `docker compose up -d`. La connexion OpenAI n'est activée que si `OPENAI_API_KEY` est rempli. Attention : les
questions des salariés partent alors chez ce fournisseur.

## 5. Sécurité

**Ce qui est fait**
- Seul Caddy est exposé ; Open WebUI (port 8080), Postgres (5432), Ollama (11434) et tri-offres (8000) ne sont
  joignables que sur le réseau Docker interne. Un test le vérifie pour chacun des quatre ports : fermé depuis la
  machine, non publié par Docker, mais ouvert depuis l'intérieur du réseau Docker.
- HTTPS partout, HTTP redirigé, en-têtes de sécurité de base.
- Inscription publique fermée : seul l'administrateur crée des comptes (vérifié par un test).
- Aucun secret dans le dépôt : `.env` est ignoré par Git, `gitleaks` tourne avant chaque commit (`pre-commit`) et dans
  la CI sur tout l'historique.
- Modèle local : les conversations ne quittent pas la machine. Télémétrie désactivée.
- Versions d'images épinglées ; mise à jour toujours précédée d'une sauvegarde.

**Ce qui manquerait en production réelle**
- Remplacer **tous** les mots de passe et la clé de `.env` par des valeurs aléatoires longues (`openssl rand -hex 32`),
  idéalement gardées dans un coffre de secrets.
- Lancer `initialiser.sh` juste après le premier démarrage, avant d'ouvrir l'accès réseau : tant que l'administrateur
  n'existe pas, le premier compte créé devient administrateur.
- Authentification d'entreprise (SSO OIDC, par exemple Entra ID) au lieu de mots de passe locaux.
- Sauvegardes planifiées (cron) et copiées **hors de la machine** (autre site, stockage chiffré) ; test de restauration
  régulier.
- Supervision (alerte si `/health` ne répond plus), journaux centralisés, mises à jour de sécurité de l'hôte.
- Rôles et groupes d'utilisateurs ; relire chaque outil Python avant de l'installer (un outil exécute du code sur le
  serveur : seul l'administrateur doit pouvoir en ajouter).
- Machine plus puissante (ou GPU) si beaucoup d'utilisateurs : sur CPU, une réponse prend quelques secondes.

## 6. Exploitation

Voir [`DOSSIER_EXPLOITATION.md`](DOSSIER_EXPLOITATION.md) : démarrer, arrêter, sauvegarder, restaurer, mettre à jour,
lire les journaux, que faire si le modèle ne répond plus. En bref :

```bash
./scripts/sauvegarder.sh                              # -> sauvegardes/AAAAMMJJ-HHMMSS/
./scripts/restaurer.sh sauvegardes/AAAAMMJJ-HHMMSS
./scripts/mettre-a-jour.sh v0.11.5                    # exemple : étiquette de la version suivante ; sauvegarde d'abord
```

## 7. Ce qui viendrait ensuite (non fait)

- **Déploiement sur Azure Container Apps** (non fait, pas de compte) : on remplacerait Postgres par Azure Database for
  PostgreSQL, les volumes par Azure Files, Caddy par l'entrée HTTPS gérée de Container Apps et les secrets par Key
  Vault ; Ollama tournerait dans un conteneur avec plus de mémoire, ou serait remplacé par Azure OpenAI.
- Connexion au vrai service [tri-offres-api](https://github.com/mathieurecatala/tri-offres-api) (même contrat d'API : seule l'adresse `TRI_OFFRES_URL` changerait).
- Sauvegardes planifiées et externalisées, supervision.
- Base documentaire interne (RAG) : envoyer les documents de l'entreprise pour que l'assistant s'en serve.

## 8. Licences

- Ce dépôt : licence MIT (fichier `LICENSE`).
- **Open WebUI** est distribué sous la *Open WebUI License* (BSD avec une clause de marque) :
  <https://github.com/open-webui/open-webui/blob/main/LICENSE>. La marque est conservée : le nom affiché est
  « Assistant interne (Open WebUI) », Open WebUI ajoutant lui-même la mention. La clause 4 de la licence interdit de
  modifier ou retirer la marque « Open WebUI », sauf dans l'un de ces trois cas (texte original) :
  > (i) deployments or distributions where the total number of end users (defined as individual natural persons with
  > direct access to the application) does not exceed fifty (50) within any rolling thirty (30) day period; (ii) the
  > licensee has obtained specific prior written permission from the copyright holder; or (iii) where the licensee has
  > obtained a duly executed enterprise license expressly permitting such modification.

  Soit : (i) au plus 50 utilisateurs finaux sur toute période glissante de 30 jours, OU (ii) une autorisation écrite
  préalable du titulaire des droits, OU (iii) une licence entreprise signée qui l'autorise expressément.
- Ollama (MIT), Caddy (Apache 2.0), PostgreSQL (licence PostgreSQL), modèle Qwen2.5 1.5B (Apache 2.0).
