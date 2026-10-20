"""
title: Tickets de support
author: Mathieu Recatala
description: Interroge le service de tickets pour lister les tickets ouverts récents, filtrés par sujet et urgence.
version: 1.0.0
license: MIT
"""

# Outil (« Tool ») Open WebUI. Installé par scripts/initialiser.sh via l'API d'Open WebUI.
# Le modèle l'appelle quand on lui demande par exemple :
#   « Quels tickets urgents encore ouverts parlent de la messagerie cette semaine ? »

import os
import unicodedata
from datetime import datetime, timedelta, timezone

import requests
from pydantic import BaseModel, Field

# Statuts d'un ticket « encore ouvert » (les autres : resolu, ferme).
STATUTS_OUVERTS = "ouvert,en_cours"


def sans_accents(texte: str) -> str:
    """Minuscules sans accents : « Réseau » et « reseau » se retrouvent."""
    decompose = unicodedata.normalize("NFKD", (texte or "").lower())
    return "".join(c for c in decompose if not unicodedata.combining(c))


def parle_de(ticket: dict, mot: str) -> bool:
    champs = (ticket.get("titre"), ticket.get("description"), ticket.get("categorie"))
    return any(mot in sans_accents(champ) for champ in champs)


def est_recent(ticket: dict, jours: int, maintenant: datetime) -> bool:
    texte = ticket.get("cree_le")
    if not texte:
        return False
    cree = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    if cree.tzinfo is None:
        cree = cree.replace(tzinfo=timezone.utc)
    return cree >= maintenant - timedelta(days=jours)


class Tools:
    class Valves(BaseModel):
        # Réglable par l'administrateur dans Open WebUI (Espace de travail > Outils > Valves).
        url_api: str = Field(
            default=os.environ.get("TICKETS_URL", "http://tickets:8000"),
            description="Adresse du service de tickets",
        )
        delai_secondes: int = Field(default=10, description="Délai maximal d'une requête")

    def __init__(self):
        self.valves = self.Valves()

    def _tickets_ouverts(self) -> list:
        """Récupère tous les tickets encore ouverts, page par page."""
        tickets, decalage, limite = [], 0, 500
        while True:
            reponse = requests.get(
                f"{self.valves.url_api.rstrip('/')}/tickets",
                params={"statut": STATUTS_OUVERTS, "limite": limite, "decalage": decalage},
                timeout=self.valves.delai_secondes,
            )
            reponse.raise_for_status()
            page = reponse.json()
            tickets.extend(page["tickets"])
            # On avance du nombre de tickets reçus (le service peut rendre moins que « limite »).
            decalage += len(page["tickets"])
            if decalage >= page["total"] or not page["tickets"]:
                return tickets

    def chercher_tickets(self, mot_cle: str = "", urgents: bool = False, jours: int = 7) -> str:
        """
        Liste les tickets de support informatique encore ouverts sur un sujet, par exemple les tickets urgents sur la messagerie cette semaine.
        :param mot_cle: un seul mot, le sujet du ticket (ex. "messagerie", "imprimante", "VPN"). Vide = tous les sujets.
        :param urgents: true pour ne garder que les tickets urgents.
        :param jours: période en jours : 7 pour « cette semaine », 30 pour « ce mois-ci », 1 seulement pour « aujourd'hui ».
        :return: la liste des tickets trouvés, un par ligne, ou un message d'erreur clair.
        """
        try:
            tickets = self._tickets_ouverts()
        except requests.RequestException as erreur:
            return f"Impossible de joindre le service de tickets ({self.valves.url_api}) : {erreur}"

        maintenant = datetime.now(timezone.utc)
        mot = sans_accents(mot_cle).strip()
        trouves = [
            t
            for t in tickets
            if parle_de(t, mot)
            and (not urgents or t.get("priorite") == "urgente")
            and est_recent(t, jours, maintenant)
        ]
        if not trouves:
            return "Aucun ticket ouvert ne correspond à ces critères."
        lignes = [f"{len(trouves)} ticket(s) trouvé(s) :"]
        for t in trouves:
            lignes.append(
                f"- {t['reference']} [{t['priorite']}, {t['statut']}] {t['titre']}"
                f" ({t['demandeur']}, {t['service']}, créé le {t['cree_le'][:10]}) : {t['url']}"
            )
        return "\n".join(lignes)
