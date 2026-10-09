#!/usr/bin/env bash
# Fonctions partagées par les scripts d'exploitation. Chargé avec : source "$(dirname "$0")/commun.sh"
set -euo pipefail

# Toujours travailler depuis la racine du projet (là où se trouve docker-compose.yml).
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ ! -f .env ]]; then
  echo "ERREUR : fichier .env absent. Faire d'abord : cp .env.example .env" >&2
  exit 1
fi
# Charge les variables de .env (mots de passe, versions...). Comme docker compose, une variable déjà définie dans
# l'environnement garde la priorité sur .env (ex. OLLAMA_VOLUME dans la CI) : on la remet après le chargement.
deja_definies=$(export -p)
set -a
# shellcheck disable=SC1091
source .env
set +a
eval "$deja_definies"
unset deja_definies

dc() { docker compose "$@"; }

journal() { echo "[$(date '+%H:%M:%S')] $*"; }

# Appel de l'API d'Open WebUI depuis l'intérieur du conteneur (pas de souci de certificat ni de DNS).
# Usage : api METHODE CHEMIN [JETON] [CORPS_JSON]
api() {
  local methode=$1 chemin=$2 jeton=${3:-} corps=${4:-}
  local args=(-sS -X "$methode" -H "Content-Type: application/json")
  [[ -n $jeton ]] && args+=(-H "Authorization: Bearer $jeton")
  [[ -n $corps ]] && args+=(--data-binary @-)
  printf '%s' "$corps" | dc exec -T open-webui curl "${args[@]}" "http://localhost:8080$chemin"
}

# Extrait un champ d'une réponse JSON : echo '{"a":1}' | champ a
champ() { python3 -c 'import sys,json; print(json.load(sys.stdin).get(sys.argv[1], ""))' "$1"; }

# Construit un objet JSON à partir de paires clé valeur : json email a@b.fr password secret
json() { python3 -c 'import sys,json; a=sys.argv[1:]; print(json.dumps(dict(zip(a[::2], a[1::2]))))' "$@"; }

# Attend que le conteneur Open WebUI soit déclaré « healthy » (10 minutes maximum).
attendre_open_webui() {
  journal "Attente d'Open WebUI..."
  for _ in $(seq 1 120); do
    if [[ $(docker inspect -f '{{.State.Health.Status}}' "$(dc ps -q open-webui)" 2>/dev/null) == healthy ]]; then
      journal "Open WebUI est prêt."
      return 0
    fi
    sleep 5
  done
  echo "ERREUR : Open WebUI n'est pas prêt après 10 minutes. Voir : docker compose logs open-webui" >&2
  return 1
}

# Ouvre une session administrateur et affiche le jeton.
jeton_admin() {
  api POST /api/v1/auths/signin "" "$(json email "$ADMIN_EMAIL" password "$ADMIN_PASSWORD")" | champ token
}
