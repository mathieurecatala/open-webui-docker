"""Tests d'intégration : la pile complète tourne et répond via le proxy Caddy."""

import json
import secrets
import socket

import pytest
import requests

from conftest import ENV, RACINE, compose, connexion, entete


def test_sante_via_le_proxy(session_http, url):
    reponse = session_http.get(f"{url}/health", timeout=30)
    assert reponse.status_code == 200
    assert reponse.json() == {"status": True}


def test_http_redirige_vers_https():
    port = ENV.get("HTTP_PORT", "80")
    reponse = requests.Session()
    reponse.trust_env = False
    reponse = reponse.get(f"http://localhost:{port}/health", allow_redirects=False, timeout=30)
    assert reponse.status_code in (301, 308)
    assert reponse.headers["Location"].startswith("https://")


@pytest.mark.parametrize(
    "service, port",
    [("open-webui", 8080), ("postgres", 5432), ("ollama", 11434), ("tri-offres", 8000)],
)
def test_service_interne_non_expose(service, port):
    # Seul Caddy publie des ports : les services internes ne sont pas joignables depuis la machine...
    with socket.socket() as s:
        s.settimeout(2)
        assert s.connect_ex(("127.0.0.1", port)) != 0, f"{service} est joignable sur le port {port}"
    # ... Docker ne publie aucun port pour eux (":0" = non publié)...
    assert compose("port", service, str(port)).strip() == ":0"
    # ... mais ils répondent bien sur le réseau interne (le test n'est pas vide).
    # Depuis le conteneur Caddy : nc -z réussit seulement si le port est ouvert (sinon compose() échoue).
    compose("exec", "-T", "caddy", "nc", "-z", "-w", "5", service, str(port))


def test_connexion_admin(session_http, url):
    reponse = connexion(session_http, url, ENV["ADMIN_EMAIL"], ENV["ADMIN_PASSWORD"])
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["role"] == "admin"


def test_mauvais_mot_de_passe_refuse(session_http, url):
    reponse = connexion(session_http, url, ENV["ADMIN_EMAIL"], "pas-le-bon")
    assert reponse.status_code in (400, 401, 403)


def test_inscription_publique_fermee(session_http, url):
    reponse = session_http.post(
        f"{url}/api/v1/auths/signup",
        json={"name": "Intrus", "email": "intrus@example.com", "password": secrets.token_urlsafe(16)},
        timeout=30,
    )
    assert reponse.status_code == 403


def test_reponse_du_modele_local(session_http, url, jeton_admin):
    reponse = session_http.post(
        f"{url}/api/chat/completions",
        headers=entete(jeton_admin),
        json={
            "model": ENV["OLLAMA_MODEL"],
            "messages": [{"role": "user", "content": "Combien font 2 + 2 ? Réponds uniquement par le chiffre."}],
            "stream": False,
            "temperature": 0,
        },
        timeout=300,
    )
    assert reponse.status_code == 200, reponse.text
    texte = reponse.json()["choices"][0]["message"]["content"]
    assert "4" in texte or "quatre" in texte.lower(), texte


def test_outil_tri_offres_installe(session_http, url, jeton_admin):
    reponse = session_http.get(f"{url}/api/v1/tools/", headers=entete(jeton_admin), timeout=30)
    assert reponse.status_code == 200
    assert "tri_offres" in [outil["id"] for outil in reponse.json()]


def test_outil_joint_le_service_tri_offres_depuis_open_webui():
    # On exécute le code de l'outil DANS le conteneur Open WebUI, contre le service tri-offres de la pile.
    code = (RACINE / "outils" / "tri_offres.py").read_text(encoding="utf-8")
    code += "\nprint(Tools().chercher_offres('Docker', True, 7))\n"
    sortie = compose("exec", "-T", "open-webui", "python", "-", entree=code)
    assert "Ingénieur DevOps Docker / Kubernetes chez Nuage Clair" in sortie
    assert "Lyon" not in sortie  # offre sur site exclue
    assert "Swarm" not in sortie  # offre rejetée par les règles de tri
    assert "MLOps" not in sortie  # offre fermée


QUESTION_OFFRES = "Quelles offres en télétravail mentionnent Docker cette semaine ?"


def poser_question_avec_outil(session_http, url, jeton_admin, **params):
    return session_http.post(
        f"{url}/api/chat/completions",
        headers=entete(jeton_admin),
        json={
            "model": ENV["OLLAMA_MODEL"],
            "messages": [{"role": "user", "content": QUESTION_OFFRES}],
            "tool_ids": ["tri_offres"],
            "stream": False,
            "temperature": 0,
            "params": params,
        },
        timeout=300,
    )


def test_le_modele_demande_l_outil_en_mode_natif(session_http, url, jeton_admin):
    # Mode « natif » (par défaut dans l'interface) : le modèle demande lui-même l'appel de l'outil.
    # Par l'API sans discussion ouverte, Open WebUI renvoie cette demande sans l'exécuter
    # (dans l'interface, il l'exécute) : on vérifie donc la demande et ses paramètres.
    reponse = poser_question_avec_outil(session_http, url, jeton_admin)
    assert reponse.status_code == 200, reponse.text
    appels = reponse.json()["choices"][0]["message"].get("tool_calls") or []
    assert appels, f"l'outil n'a pas été demandé : {reponse.text[:500]}"
    assert appels[0]["function"]["name"] == "chercher_offres"
    arguments = json.loads(appels[0]["function"]["arguments"])
    assert "docker" in arguments["mot_cle"].lower()
    assert arguments.get("teletravail", True) is True


def test_le_modele_appelle_l_outil_tri_offres(session_http, url, jeton_admin):
    # Bout en bout par l'API (mode « legacy ») : Open WebUI exécute l'outil et renvoie son résultat.
    # On vérifie l'appel et son résultat (déterministes), pas la rédaction du petit modèle.
    reponse = poser_question_avec_outil(session_http, url, jeton_admin, function_calling="legacy")
    assert reponse.status_code == 200, reponse.text
    appels = [s for s in reponse.json().get("sources", []) if s.get("tool_result")]
    assert appels, f"l'outil n'a pas été appelé : {reponse.text[:500]}"
    assert appels[0]["source"]["name"] == "tri_offres/chercher_offres"
    assert "Nuage Clair" in appels[0]["document"][0]
