#!/usr/bin/env bash
# Sauvegarde à chaud d'Open WebUI : base Postgres + fichiers (documents envoyés, index de recherche).
# Crée sauvegardes/AAAAMMJJ-HHMMSS/ avec :
#   base.dump        export Postgres (format pg_dump personnalisé)
#   donnees.tar.gz   contenu du volume /app/backend/data, sans le cache (re-téléchargeable)
#   version.txt      version d'Open WebUI au moment de la sauvegarde
# Garde les SAUVEGARDES_A_GARDER dernières (14 par défaut), supprime les plus anciennes.
# Usage : ./scripts/sauvegarder.sh        (dernière ligne affichée = dossier créé)
source "$(dirname "$0")/commun.sh"

dossier="sauvegardes/$(date '+%Y%m%d-%H%M%S')"
mkdir -p "$dossier"

journal "Export de la base Postgres..."
dc exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$dossier/base.dump"

journal "Archive des fichiers d'Open WebUI..."
dc exec -T open-webui tar czf - -C /app/backend/data --exclude=./cache . > "$dossier/donnees.tar.gz"

echo "OPEN_WEBUI_VERSION=$OPEN_WEBUI_VERSION" > "$dossier/version.txt"

# Contrôle minimal : les deux fichiers ne doivent pas être vides.
for fichier in base.dump donnees.tar.gz; do
  [[ -s $dossier/$fichier ]] || { echo "ERREUR : $dossier/$fichier est vide" >&2; exit 1; }
done

# Rotation : on ne garde que les N plus récentes.
a_garder=${SAUVEGARDES_A_GARDER:-14}
ls -1d sauvegardes/*/ | sort | head -n "-$a_garder" | xargs -r rm -rf

journal "Sauvegarde terminée ($(du -sh "$dossier" | cut -f1))."
echo "$dossier"
