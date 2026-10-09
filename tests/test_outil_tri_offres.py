"""Tests unitaires de l'outil Open WebUI tri-offres, sur une API simulée (pas besoin de la pile)."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "outils"))
import tri_offres  # noqa: E402


def il_y_a(jours):
    return (datetime.now(timezone.utc) - timedelta(days=jours)).isoformat()


OFFRES = [
    {"id": 1, "entreprise": "A", "titre": "DevOps Docker", "lieu": "Télétravail", "url": "u1",
     "vue_premiere_fois": il_y_a(1)},
    {"id": 2, "entreprise": "B", "titre": "Admin Docker", "lieu": "Lyon", "url": "u2",
     "vue_premiere_fois": il_y_a(2)},
    {"id": 3, "entreprise": "C", "titre": "Plateforme docker", "lieu": "Full remote", "url": "u3",
     "vue_premiere_fois": il_y_a(30)},
    {"id": 4, "entreprise": "D", "titre": "Dev React", "lieu": "Remote", "url": "u4",
     "vue_premiere_fois": il_y_a(1)},
]


class FausseReponse:
    def __init__(self, corps):
        self.corps = corps

    def raise_for_status(self):
        pass

    def json(self):
        return self.corps


@pytest.fixture
def appels(monkeypatch):
    """Remplace requests.get par une API simulée qui pagine par 2 et garde la trace des appels."""
    traces = []

    def faux_get(url, params, timeout):
        traces.append((url, dict(params)))
        debut = params["decalage"]
        page = OFFRES[debut : debut + 2]
        return FausseReponse({"total": len(OFFRES), "limite": 2, "decalage": debut, "offres": page})

    monkeypatch.setattr(tri_offres.requests, "get", faux_get)
    return traces


def test_offres_docker_en_teletravail_cette_semaine(appels):
    outil = tri_offres.Tools()
    texte = outil.chercher_offres(mot_cle="Docker", teletravail=True, jours=7)
    assert "1 offre(s)" in texte
    assert "DevOps Docker chez A" in texte
    assert "Lyon" not in texte  # pas en télétravail
    assert "Plateforme" not in texte  # trop ancienne


def test_appel_api_filtre_les_offres_gardees_et_actives(appels):
    tri_offres.Tools().chercher_offres()
    url, params = appels[0]
    assert url == "http://tri-offres:8000/offres"
    assert params["gardee"] == "true" and params["active"] == "true"


def test_pagination_parcourt_toutes_les_pages(appels):
    # La fausse API ne rend que 2 offres par page : l'outil doit enchaîner les pages.
    offres = tri_offres.Tools()._toutes_les_offres()
    assert [o["id"] for o in offres] == [1, 2, 3, 4]
    assert [p["decalage"] for _, p in appels] == [0, 2]


def test_sans_filtre_teletravail(appels):
    texte = tri_offres.Tools().chercher_offres(mot_cle="docker", teletravail=False, jours=7)
    assert "2 offre(s)" in texte and "Lyon" in texte


def test_aucune_offre(appels):
    assert "Aucune offre" in tri_offres.Tools().chercher_offres(mot_cle="Cobol")


def test_api_injoignable(monkeypatch):
    def en_panne(*args, **kwargs):
        raise requests.ConnectionError("connexion refusée")

    monkeypatch.setattr(tri_offres.requests, "get", en_panne)
    assert "Impossible de joindre" in tri_offres.Tools().chercher_offres()
