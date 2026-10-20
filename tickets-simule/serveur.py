"""Service simulé de tickets de support informatique interne.

Pourquoi simulé : un vrai outil de tickets (GLPI, Jira Service Management, ServiceNow...) demande son propre
serveur et des données réelles. Pour une démonstration reproductible (et la CI), on sert un jeu de tickets fixe et
fictif, avec des dates calculées par rapport au démarrage pour que « cette semaine » ait toujours un sens.

Contrat :
  GET /health
  GET /tickets?statut=ouvert,en_cours&priorite=urgente&texte=&limite=50&decalage=0
      -> {"total", "limite", "decalage", "tickets": [Ticket, ...]}
  statut et priorite acceptent plusieurs valeurs séparées par des virgules.
"""

import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

MAINTENANT = datetime.now(timezone.utc)

STATUTS = ("ouvert", "en_cours", "resolu", "ferme")
PRIORITES = ("basse", "normale", "urgente")


def _ticket(id_, titre, description, categorie, priorite, statut, demandeur, service, jours):
    cree = (MAINTENANT - timedelta(days=jours)).isoformat()
    reference = f"TCK-{id_}"
    return {
        "id": id_,
        "reference": reference,
        "titre": titre,
        "description": description,
        "categorie": categorie,
        "priorite": priorite,
        "statut": statut,
        "demandeur": demandeur,
        "service": service,
        "cree_le": cree,
        "mis_a_jour_le": MAINTENANT.isoformat(),
        "url": f"https://support.exemple.invalid/tickets/{reference}",
    }


# Jeu de tickets fictif (personnes et services inventés). Chaque filtre de l'outil exclut au moins un ticket :
# résolu ou fermé, trop ancien, non urgent, autre sujet.
TICKETS = [
    _ticket(1041, "Outlook ne reçoit plus aucun courriel", "Plus rien n'arrive depuis ce matin, l'envoi marche.",
            "messagerie", "urgente", "ouvert", "Claire Martin", "Comptabilité", 1),
    _ticket(1042, "Boîte partagée de l'accueil inaccessible", "Message « accès refusé » pour toute l'équipe.",
            "messagerie", "urgente", "en_cours", "Hugo Lefèvre", "Accueil", 2),
    _ticket(1043, "Mettre à jour la signature des courriels", "Nouveau logo à intégrer dans la signature.",
            "messagerie", "basse", "ouvert", "Inès Garnier", "Communication", 1),
    _ticket(1044, "Courriels bloqués dans la boîte d'envoi", "Résolu après redémarrage du poste.",
            "messagerie", "urgente", "ferme", "Paul Roche", "Achats", 3),
    _ticket(1031, "Messagerie lente depuis la migration", "Chaque ouverture de dossier prend 20 secondes.",
            "messagerie", "urgente", "ouvert", "Léa Dubois", "Direction", 20),
    _ticket(1045, "Imprimante du 2e étage hors ligne", "Plus aucune impression possible au 2e étage.",
            "imprimante", "urgente", "ouvert", "Marc Petit", "Logistique", 1),
    _ticket(1046, "VPN : connexion impossible depuis l'agence de Nantes", "Erreur d'authentification au VPN.",
            "reseau", "normale", "ouvert", "Sophie Bernard", "Commercial", 4),
    _ticket(1047, "Logiciel de paie : erreur à l'export", "L'export du fichier de virements échoue.",
            "logiciel", "urgente", "resolu", "Julien Moreau", "Ressources humaines", 2),
]


def _liste(valeur):
    return [v.strip() for v in valeur.split(",") if v.strip()]


def filtrer(params):
    """Applique les filtres de GET /tickets : statut, priorite, texte (titre, description, catégorie)."""
    resultat = list(TICKETS)
    if params.get("statut"):
        statuts = _liste(params["statut"])
        resultat = [t for t in resultat if t["statut"] in statuts]
    if params.get("priorite"):
        priorites = _liste(params["priorite"])
        resultat = [t for t in resultat if t["priorite"] in priorites]
    if params.get("texte"):
        texte = params["texte"].lower()
        resultat = [
            t
            for t in resultat
            if texte in t["titre"].lower() or texte in t["description"].lower() or texte in t["categorie"]
        ]
    # Tri : plus récents d'abord, puis id décroissant.
    resultat.sort(key=lambda t: (t["cree_le"], t["id"]), reverse=True)
    return resultat


class Gestionnaire(BaseHTTPRequestHandler):
    def _repondre(self, code, corps):
        donnees = json.dumps(corps, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(donnees)))
        self.end_headers()
        self.wfile.write(donnees)

    def do_GET(self):
        url = urlparse(self.path)
        params = {cle: valeurs[-1] for cle, valeurs in parse_qs(url.query).items()}
        if url.path == "/health":
            return self._repondre(200, {"statut": "ok"})
        if url.path == "/tickets":
            try:
                limite = int(params.get("limite", "50"))
                decalage = int(params.get("decalage", "0"))
            except ValueError:
                return self._repondre(422, {"detail": "limite et decalage doivent être des entiers"})
            if not 1 <= limite <= 500 or decalage < 0:
                return self._repondre(422, {"detail": "limite entre 1 et 500, decalage >= 0"})
            inconnus = [s for s in _liste(params.get("statut", "")) if s not in STATUTS]
            inconnus += [p for p in _liste(params.get("priorite", "")) if p not in PRIORITES]
            if inconnus:
                return self._repondre(422, {"detail": f"valeur inconnue : {', '.join(inconnus)}"})
            tickets = filtrer(params)
            page = tickets[decalage : decalage + limite]
            return self._repondre(
                200, {"total": len(tickets), "limite": limite, "decalage": decalage, "tickets": page}
            )
        return self._repondre(404, {"detail": "introuvable"})

    def log_message(self, format, *args):  # journal court sur la sortie standard
        print(f"{self.address_string()} {format % args}", flush=True)


if __name__ == "__main__":
    print("Service de tickets simulé : écoute sur le port 8000", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8000), Gestionnaire).serve_forever()
