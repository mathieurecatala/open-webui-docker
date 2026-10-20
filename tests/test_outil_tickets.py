"""Tests unitaires de l'outil Open WebUI « tickets », sur un service simulé (pas besoin de la pile)."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "outils"))
import tickets  # noqa: E402


def il_y_a(jours):
    return (datetime.now(timezone.utc) - timedelta(days=jours)).isoformat()


def ticket(id_, titre, categorie, priorite, jours, description=""):
    return {
        "id": id_, "reference": f"TCK-{id_}", "titre": titre, "description": description,
        "categorie": categorie, "priorite": priorite, "statut": "ouvert", "demandeur": "Personne fictive",
        "service": "Service fictif", "cree_le": il_y_a(jours), "url": f"u{id_}",
    }


# Le service ne rend que des tickets encore ouverts (filtre statut) : l'outil filtre le reste lui-même.
TICKETS = [
    ticket(1, "Outlook ne reçoit plus les courriels", "messagerie", "urgente", 1),
    ticket(2, "Signature des courriels", "messagerie", "basse", 2),
    ticket(3, "Messagerie lente", "messagerie", "urgente", 30),
    ticket(4, "Imprimante hors ligne", "imprimante", "urgente", 1),
    ticket(5, "Accès refusé", "acces", "normale", 1, description="Le réseau Wi-Fi refuse le mot de passe."),
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
    """Remplace requests.get par un service simulé qui pagine par 2 et garde la trace des appels."""
    traces = []

    def faux_get(url, params, timeout):
        traces.append((url, dict(params)))
        debut = params["decalage"]
        page = TICKETS[debut : debut + 2]
        return FausseReponse({"total": len(TICKETS), "limite": 2, "decalage": debut, "tickets": page})

    monkeypatch.setattr(tickets.requests, "get", faux_get)
    return traces


def test_tickets_urgents_sur_la_messagerie_cette_semaine(appels):
    texte = tickets.Tools().chercher_tickets(mot_cle="messagerie", urgents=True, jours=7)
    assert "1 ticket(s)" in texte
    assert "TCK-1 [urgente, ouvert] Outlook ne reçoit plus les courriels" in texte
    assert "Signature" not in texte  # non urgent
    assert "lente" not in texte  # trop ancien
    assert "Imprimante" not in texte  # autre sujet


def test_appel_du_service_filtre_les_tickets_ouverts(appels):
    tickets.Tools().chercher_tickets()
    url, params = appels[0]
    assert url == "http://tickets:8000/tickets"
    assert params["statut"] == "ouvert,en_cours"


def test_pagination_parcourt_toutes_les_pages(appels):
    # Le faux service ne rend que 2 tickets par page : l'outil doit enchaîner les pages.
    trouves = tickets.Tools()._tickets_ouverts()
    assert [t["id"] for t in trouves] == [1, 2, 3, 4, 5]
    assert [p["decalage"] for _, p in appels] == [0, 2, 4]


def test_sans_filtre_urgence(appels):
    texte = tickets.Tools().chercher_tickets(mot_cle="messagerie", urgents=False, jours=7)
    assert "2 ticket(s)" in texte and "Signature" in texte


def test_mot_cle_sans_accent_ni_majuscule_cherche_aussi_la_description(appels):
    texte = tickets.Tools().chercher_tickets(mot_cle="RESEAU", jours=7)
    assert "1 ticket(s)" in texte and "TCK-5" in texte


def test_aucun_ticket(appels):
    assert "Aucun ticket" in tickets.Tools().chercher_tickets(mot_cle="Cobol")


def test_service_injoignable(monkeypatch):
    def en_panne(*args, **kwargs):
        raise requests.ConnectionError("connexion refusée")

    monkeypatch.setattr(tickets.requests, "get", en_panne)
    assert "Impossible de joindre le service de tickets" in tickets.Tools().chercher_tickets()
