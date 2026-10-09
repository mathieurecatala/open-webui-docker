#!/usr/bin/env bash
# Met à jour Open WebUI vers une nouvelle version épinglée, avec sauvegarde préalable.
# Usage : ./scripts/mettre-a-jour.sh v0.11.5   (exemple : l'étiquette de la nouvelle version)
#
# Retour arrière si la nouvelle version pose problème :
#   ./scripts/mettre-a-jour.sh <ancienne version>                         (remet l'ancienne image)
#   ./scripts/restaurer.sh sauvegardes/<dossier affiché ci-dessous> --oui  (remet les données d'avant)
# La restauration est nécessaire si la nouvelle version a modifié la base (migrations) :
# une ancienne version ne sait pas toujours relire une base migrée.
source "$(dirname "$0")/commun.sh"

nouvelle=${1:?Usage : ./scripts/mettre-a-jour.sh <étiquette, ex. v0.11.5>}
ancienne=$OPEN_WEBUI_VERSION
if [[ $nouvelle == main || $nouvelle == latest || $nouvelle == dev ]]; then
  echo "ERREUR : utiliser une version précise (ex. v0.11.5), jamais main/latest/dev." >&2
  exit 1
fi

journal "Téléchargement de l'image $nouvelle (avant tout changement)..."
docker pull "ghcr.io/open-webui/open-webui:$nouvelle"

journal "Sauvegarde avant mise à jour..."
sauvegarde=$(./scripts/sauvegarder.sh | tail -n 1)

journal "Passage de $ancienne à $nouvelle dans .env..."
sed -i.bak "s/^OPEN_WEBUI_VERSION=.*/OPEN_WEBUI_VERSION=$nouvelle/" .env
export OPEN_WEBUI_VERSION=$nouvelle
dc up -d open-webui caddy

if attendre_open_webui; then
  journal "Mise à jour terminée : $ancienne -> $nouvelle."
  journal "Sauvegarde d'avant mise à jour : $sauvegarde"
else
  echo "ÉCHEC de la mise à jour. Pour revenir en arrière :" >&2
  echo "  ./scripts/mettre-a-jour.sh $ancienne" >&2
  echo "  ./scripts/restaurer.sh $sauvegarde --oui" >&2
  exit 1
fi
