#!/usr/bin/env bash
# Initialisation après le premier démarrage (à relancer sans risque, le script est idempotent) :
#   1. crée le premier compte administrateur à partir de ADMIN_EMAIL / ADMIN_PASSWORD (.env) ;
#   2. vérifie que l'inscription publique est fermée ;
#   3. installe (ou met à jour) l'outil « tri-offres » dans Open WebUI ;
#   4. attend la fin du téléchargement du modèle local.
# Usage : ./scripts/initialiser.sh
source "$(dirname "$0")/commun.sh"

attendre_open_webui

# 1. Administrateur : on essaie de se connecter ; sinon on crée le premier compte.
jeton=$(jeton_admin || true)
if [[ -z $jeton ]]; then
  journal "Création du compte administrateur $ADMIN_EMAIL"
  reponse=$(api POST /api/v1/auths/signup "" \
    "$(json name "$ADMIN_NAME" email "$ADMIN_EMAIL" password "$ADMIN_PASSWORD")")
  role=$(echo "$reponse" | champ role)
  if [[ $role != admin ]]; then
    echo "ERREUR : création de l'administrateur impossible : $reponse" >&2
    exit 1
  fi
  jeton=$(jeton_admin)
else
  journal "Le compte administrateur existe déjà."
fi

# 2. L'inscription publique doit être fermée (ENABLE_SIGNUP=false).
inscription=$(api GET /api/v1/auths/admin/config "$jeton" | champ ENABLE_SIGNUP)
if [[ $inscription != False ]]; then
  echo "ERREUR : l'inscription publique est ouverte (ENABLE_SIGNUP=$inscription)." >&2
  exit 1
fi
journal "Inscription publique : fermée."

# 3. Outil tri-offres : création, ou mise à jour s'il existe déjà.
contenu=$(cat outils/tri_offres.py)
corps=$(python3 -c '
import json, sys
print(json.dumps({
    "id": "tri_offres",
    "name": "Offres d emploi (tri-offres)",
    "content": sys.argv[1],
    "meta": {"description": "Offres d emploi récentes, filtrées par mot-clé et télétravail"},
}))' "$contenu")
if [[ $(api GET /api/v1/tools/id/tri_offres "$jeton" | champ id) == tri_offres ]]; then
  api POST /api/v1/tools/id/tri_offres/update "$jeton" "$corps" > /dev/null
  journal "Outil tri-offres mis à jour."
else
  resultat=$(api POST /api/v1/tools/create "$jeton" "$corps")
  [[ $(echo "$resultat" | champ id) == tri_offres ]] || { echo "ERREUR outil : $resultat" >&2; exit 1; }
  journal "Outil tri-offres installé."
fi

# 4. Le modèle local est téléchargé par le service « ollama-modele » : on attend qu'il ait fini.
journal "Attente du modèle $OLLAMA_MODEL (premier téléchargement : quelques minutes)..."
dc up --no-deps ollama-modele > /dev/null 2>&1 || true
if ! dc exec -T ollama ollama list | grep -q "^${OLLAMA_MODEL}"; then
  echo "ERREUR : le modèle $OLLAMA_MODEL n'est pas disponible. Voir : docker compose logs ollama-modele" >&2
  exit 1
fi
journal "Modèle $OLLAMA_MODEL disponible."
journal "Initialisation terminée. Interface : https://${SITE_ADDRESS}:${HTTPS_PORT}"
