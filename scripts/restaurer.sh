#!/usr/bin/env bash
# Restaure une sauvegarde faite par sauvegarder.sh. ÉCRASE les données actuelles.
# Usage : ./scripts/restaurer.sh sauvegardes/AAAAMMJJ-HHMMSS [--oui]
#   --oui : ne pas demander de confirmation (pour les tests automatiques)
source "$(dirname "$0")/commun.sh"

dossier=${1:?Usage : ./scripts/restaurer.sh sauvegardes/AAAAMMJJ-HHMMSS [--oui]}
dossier=${dossier%/}
for fichier in base.dump donnees.tar.gz; do
  [[ -s $dossier/$fichier ]] || { echo "ERREUR : $dossier/$fichier introuvable ou vide" >&2; exit 1; }
done

if [[ ${2:-} != --oui ]]; then
  read -r -p "Les données actuelles seront remplacées par $dossier. Continuer ? (oui/non) " reponse
  [[ $reponse == oui ]] || { echo "Abandon."; exit 1; }
fi

journal "Arrêt d'Open WebUI et du proxy (les utilisateurs voient une page indisponible)..."
dc stop caddy open-webui

journal "Restauration de la base Postgres..."
dc exec -T postgres psql -q -U "$POSTGRES_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\" WITH (FORCE);" \
  -c "CREATE DATABASE \"$POSTGRES_DB\" OWNER \"$POSTGRES_USER\";"
dc exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner < "$dossier/base.dump"

journal "Restauration des fichiers d'Open WebUI (le cache est conservé)..."
dc run --rm --no-deps -T --entrypoint sh open-webui -c \
  'cd /app/backend/data && find . -mindepth 1 -maxdepth 1 ! -name cache -exec rm -rf {} + && tar xzf - -C .' \
  < "$dossier/donnees.tar.gz"

journal "Redémarrage..."
dc up -d open-webui caddy
attendre_open_webui
journal "Restauration terminée depuis $dossier."
