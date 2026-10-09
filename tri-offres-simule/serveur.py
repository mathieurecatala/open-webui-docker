"""Service simulé reprenant le contrat de l'API tri-offres (mathieurecatala/tri-offres-api).

Pourquoi simulé : le vrai service a besoin de sa propre base et d'une collecte sur Internet ;
pour une démonstration reproductible (et la CI), on sert un jeu d'offres fixe, avec des dates
calculées par rapport au démarrage pour que « cette semaine » ait toujours un sens.

Contrat repris :
  GET /health
  GET /offres?entreprise=&gardee=&texte=&active=true&limite=50&decalage=0
      -> {"total", "limite", "decalage", "offres": [OffreSortie, ...]}
"""

import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

MAINTENANT = datetime.now(timezone.utc)


def _offre(id_, entreprise, titre, lieu, jours, gardee=True, active=True, raison=None):
    vue = (MAINTENANT - timedelta(days=jours)).isoformat()
    return {
        "id": id_,
        "entreprise": entreprise,
        "ats": "simule",
        "titre": titre,
        "lieu": lieu,
        "url": f"https://exemple.invalid/offres/{id_}",
        "salaire": "",
        "gardee": gardee,
        "raison_rejet": raison,
        "active": active,
        "vue_premiere_fois": vue,
        "vue_derniere_fois": MAINTENANT.isoformat(),
    }


# Jeu d'offres fictif (entreprises inventées).
OFFRES = [
    _offre(1, "Nuage Clair", "Ingénieur DevOps Docker / Kubernetes", "Télétravail (France)", 1),
    _offre(2, "Atelier Data", "Développeur Python - Docker, FastAPI", "Paris - télétravail partiel", 3),
    _offre(3, "Rivière SI", "Administrateur systèmes Linux et Docker", "Lyon", 2),
    _offre(4, "Nuage Clair", "Consultant Cloud Azure", "Full remote", 4),
    _offre(5, "Atelier Data", "Ingénieur plateforme Docker", "Remote", 20),
    _offre(6, "Pixel & Co", "Développeur front React", "Télétravail", 2),
    _offre(7, "Rivière SI", "SRE Docker Swarm", "Télétravail", 1, gardee=False, raison="mot exclu : Swarm"),
    _offre(8, "Pixel & Co", "Ingénieur MLOps (Docker, Ollama)", "100% télétravail", 5, active=False),
]


def _booleen(valeur):
    return valeur.lower() in ("true", "1", "oui")


def filtrer(params):
    """Applique les mêmes filtres que GET /offres de tri-offres."""
    active = _booleen(params.get("active", "true"))
    resultat = [o for o in OFFRES if o["active"] == active]
    if "entreprise" in params:
        resultat = [o for o in resultat if o["entreprise"] == params["entreprise"]]
    if "gardee" in params:
        gardee = _booleen(params["gardee"])
        resultat = [o for o in resultat if o["gardee"] == gardee]
    if params.get("texte"):
        texte = params["texte"].lower()
        resultat = [o for o in resultat if texte in o["titre"].lower() or texte in o["lieu"].lower()]
    # Tri : plus récentes d'abord, puis id décroissant.
    resultat.sort(key=lambda o: (o["vue_premiere_fois"], o["id"]), reverse=True)
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
        if url.path == "/offres":
            try:
                limite = int(params.get("limite", "50"))
                decalage = int(params.get("decalage", "0"))
            except ValueError:
                return self._repondre(422, {"detail": "limite et decalage doivent être des entiers"})
            if not 1 <= limite <= 500 or decalage < 0:
                return self._repondre(422, {"detail": "limite entre 1 et 500, decalage >= 0"})
            offres = filtrer(params)
            page = offres[decalage : decalage + limite]
            return self._repondre(
                200, {"total": len(offres), "limite": limite, "decalage": decalage, "offres": page}
            )
        return self._repondre(404, {"detail": "introuvable"})

    def log_message(self, format, *args):  # journal court sur la sortie standard
        print(f"{self.address_string()} {format % args}", flush=True)


if __name__ == "__main__":
    print("tri-offres simulé : écoute sur le port 8000", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8000), Gestionnaire).serve_forever()
