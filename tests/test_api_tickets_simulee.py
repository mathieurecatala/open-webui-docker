"""Tests du service de tickets simulé (sans la pile) : chaque filtre exclut bien quelque chose."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tickets-simule"))
import serveur  # noqa: E402


def references(params):
    return [t["reference"] for t in serveur.filtrer(params)]


def test_sans_filtre_tous_les_tickets_du_plus_recent_au_plus_ancien():
    tickets = serveur.filtrer({})
    assert len(tickets) == len(serveur.TICKETS)
    dates = [t["cree_le"] for t in tickets]
    assert dates == sorted(dates, reverse=True)


def test_filtre_statut_exclut_les_tickets_resolus_et_fermes():
    trouves = references({"statut": "ouvert,en_cours"})
    assert "TCK-1044" not in trouves and "TCK-1047" not in trouves
    assert "TCK-1041" in trouves and "TCK-1042" in trouves


def test_filtre_priorite_exclut_les_tickets_non_urgents():
    trouves = references({"priorite": "urgente"})
    assert "TCK-1043" not in trouves and "TCK-1046" not in trouves


def test_filtre_texte_cherche_titre_description_et_categorie():
    trouves = references({"texte": "messagerie"})
    assert "TCK-1042" in trouves  # catégorie seulement
    assert "TCK-1045" not in trouves  # autre sujet


def test_la_semaine_a_toujours_des_resultats_et_un_ticket_ancien():
    anciens = [t for t in serveur.TICKETS if t["cree_le"] < (serveur.MAINTENANT - serveur.timedelta(days=7)).isoformat()]
    assert [t["reference"] for t in anciens] == ["TCK-1031"]
