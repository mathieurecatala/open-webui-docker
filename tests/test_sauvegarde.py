"""Sauvegarde puis restauration : on retrouve les données (base Postgres ET fichiers).

Lancé en dernier (ordre alphabétique) car la restauration redémarre Open WebUI.
"""

import secrets
import subprocess

from conftest import RACINE, compose, connexion, entete

TEMOIN = {"name": "Témoin", "email": "temoin@example.com", "password": secrets.token_urlsafe(16), "role": "user"}
FICHIER_TEMOIN = "/app/backend/data/uploads/temoin.txt"


def script(*args):
    resultat = subprocess.run(args, cwd=RACINE, capture_output=True, text=True, timeout=900)
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
    return resultat.stdout


def test_sauvegarde_puis_restauration(session_http, url, jeton_admin):
    # 1. Données témoins : un utilisateur (base Postgres) et un fichier (volume).
    reponse = session_http.post(f"{url}/api/v1/auths/add", headers=entete(jeton_admin), json=TEMOIN, timeout=30)
    assert reponse.status_code == 200, reponse.text
    id_temoin = reponse.json()["id"]
    compose("exec", "-T", "open-webui", "sh", "-c", f"echo bonjour > {FICHIER_TEMOIN}")

    # 2. Sauvegarde.
    dossier = script("./scripts/sauvegarder.sh").strip().splitlines()[-1]
    assert (RACINE / dossier / "base.dump").stat().st_size > 0

    # 3. On perd les données.
    reponse = session_http.delete(f"{url}/api/v1/users/{id_temoin}", headers=entete(jeton_admin), timeout=30)
    assert reponse.status_code == 200, reponse.text
    compose("exec", "-T", "open-webui", "rm", FICHIER_TEMOIN)
    assert connexion(session_http, url, TEMOIN["email"], TEMOIN["password"]).status_code != 200

    # 4. Restauration : tout revient.
    script("./scripts/restaurer.sh", dossier, "--oui")
    assert connexion(session_http, url, TEMOIN["email"], TEMOIN["password"]).status_code == 200
    assert compose("exec", "-T", "open-webui", "cat", FICHIER_TEMOIN).strip() == "bonjour"

    # 5. Ménage : on retire l'utilisateur témoin pour pouvoir relancer le test.
    session_http.delete(f"{url}/api/v1/users/{id_temoin}", headers=entete(jeton_admin), timeout=30)
