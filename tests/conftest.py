"""Outils communs aux tests. Les tests d'intégration supposent la pile démarrée et initialisée :
    cp .env.example .env && docker compose up -d && ./scripts/initialiser.sh
"""

import os
import subprocess
from pathlib import Path

import pytest
import requests
import urllib3

RACINE = Path(__file__).resolve().parent.parent

# Le certificat de dev est signé par l'autorité locale de Caddy : on ne le vérifie pas dans les tests.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def lire_env():
    valeurs = {}
    fichier = RACINE / ".env"
    if fichier.exists():
        for ligne in fichier.read_text(encoding="utf-8").splitlines():
            if "=" in ligne and not ligne.lstrip().startswith("#"):
                cle, valeur = ligne.split("=", 1)
                valeurs[cle.strip()] = valeur.strip()
    valeurs.update({k: v for k, v in os.environ.items() if k in valeurs})
    return valeurs


ENV = lire_env()


def compose(*args, entree=None):
    """Lance une commande docker compose dans le dossier du projet et rend sa sortie."""
    resultat = subprocess.run(
        ["docker", "compose", *args], cwd=RACINE, input=entree, capture_output=True, text=True
    )
    assert resultat.returncode == 0, resultat.stderr
    return resultat.stdout


@pytest.fixture(scope="session")
def url():
    """Adresse publique, via le proxy Caddy."""
    return f"https://localhost:{ENV.get('HTTPS_PORT', '443')}"


@pytest.fixture(scope="session")
def session_http():
    s = requests.Session()
    s.trust_env = False  # ignore les proxys et autorités de la machine : on parle à localhost
    s.verify = False
    return s


def connexion(session_http, url, email, mot_de_passe):
    return session_http.post(
        f"{url}/api/v1/auths/signin", json={"email": email, "password": mot_de_passe}, timeout=30
    )


@pytest.fixture
def jeton_admin(session_http, url):
    reponse = connexion(session_http, url, ENV["ADMIN_EMAIL"], ENV["ADMIN_PASSWORD"])
    assert reponse.status_code == 200, reponse.text
    return reponse.json()["token"]


def entete(jeton):
    return {"Authorization": f"Bearer {jeton}"}


