"""
title: Offres d'emploi (tri-offres)
author: Mathieu Recatala
description: Interroge l'API tri-offres pour lister les offres récentes, filtrées par mot-clé et télétravail.
version: 1.0.0
license: MIT
"""

# Outil (« Tool ») Open WebUI. Installé par scripts/initialiser.sh via l'API d'Open WebUI.
# Le modèle l'appelle quand on lui demande par exemple :
#   « Quelles offres en télétravail mentionnent Docker cette semaine ? »

import os
from datetime import datetime, timedelta, timezone

import requests
from pydantic import BaseModel, Field

# Mots qui signalent une offre en télétravail dans le champ « lieu ».
MOTS_TELETRAVAIL = ("télétravail", "teletravail", "remote", "à distance", "a distance")


def est_en_teletravail(offre: dict) -> bool:
    lieu = (offre.get("lieu") or "").lower()
    return any(mot in lieu for mot in MOTS_TELETRAVAIL)


def est_recente(offre: dict, jours: int, maintenant: datetime) -> bool:
    texte = offre.get("vue_premiere_fois")
    if not texte:
        return False
    vue = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    if vue.tzinfo is None:
        vue = vue.replace(tzinfo=timezone.utc)
    return vue >= maintenant - timedelta(days=jours)


class Tools:
    class Valves(BaseModel):
        # Réglable par l'administrateur dans Open WebUI (Espace de travail > Outils > Valves).
        url_api: str = Field(
            default=os.environ.get("TRI_OFFRES_URL", "http://tri-offres:8000"),
            description="Adresse de l'API tri-offres",
        )
        delai_secondes: int = Field(default=10, description="Délai maximal d'une requête")

    def __init__(self):
        self.valves = self.Valves()

    def _toutes_les_offres(self) -> list:
        """Récupère toutes les offres actives et gardées, page par page."""
        offres, decalage, limite = [], 0, 500
        while True:
            reponse = requests.get(
                f"{self.valves.url_api.rstrip('/')}/offres",
                params={"gardee": "true", "active": "true", "limite": limite, "decalage": decalage},
                timeout=self.valves.delai_secondes,
            )
            reponse.raise_for_status()
            page = reponse.json()
            offres.extend(page["offres"])
            # On avance du nombre d'offres reçues (l'API peut rendre moins que « limite »).
            decalage += len(page["offres"])
            if decalage >= page["total"] or not page["offres"]:
                return offres

    def chercher_offres(self, mot_cle: str = "Docker", teletravail: bool = True, jours: int = 7) -> str:
        """
        Liste les offres d'emploi récentes dont le titre mentionne un mot-clé, éventuellement en télétravail.
        :param mot_cle: mot à chercher dans le titre de l'offre (ex. "Docker", "Python"). Vide = toutes.
        :param teletravail: true pour ne garder que les offres en télétravail.
        :param jours: période en jours : 7 pour « cette semaine », 30 pour « ce mois-ci », 1 seulement pour « aujourd'hui ».
        :return: la liste des offres trouvées, une par ligne, ou un message d'erreur clair.
        """
        try:
            offres = self._toutes_les_offres()
        except requests.RequestException as erreur:
            return f"Impossible de joindre l'API tri-offres ({self.valves.url_api}) : {erreur}"

        maintenant = datetime.now(timezone.utc)
        mot = (mot_cle or "").lower()
        trouvees = [
            o
            for o in offres
            if mot in (o.get("titre") or "").lower()
            and (not teletravail or est_en_teletravail(o))
            and est_recente(o, jours, maintenant)
        ]
        if not trouvees:
            return "Aucune offre ne correspond à ces critères."
        lignes = [f"{len(trouvees)} offre(s) trouvée(s) :"]
        for o in trouvees:
            lignes.append(f"- {o['titre']} chez {o['entreprise']} ({o['lieu']}) : {o['url']}")
        return "\n".join(lignes)
