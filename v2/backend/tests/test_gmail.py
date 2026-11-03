"""Gmail : liaison protégée par « state », jeton chiffré, lecture seule (Google simulé)."""
import base64

import pytest

from albert.domain.erreurs import ErreurMetier
from albert.models import ConnexionGmail
from albert.services import gmail


class Reponse:
    def __init__(self, donnees, statut=200):
        self._donnees, self.status_code = donnees, statut

    def json(self):
        return self._donnees


def faux_google(url, **kwargs):
    if url.endswith("/profile"):
        return Reponse({"emailAddress": "info@albert.brussels"})
    if "/messages/" in url:
        return Reponse({"id": "m1", "threadId": "t1", "snippet": "Bonjour, 20 personnes le 12/06",
                        "payload": {"headers": [{"name": "From", "value": "client@exemple.be"}, {"name": "Subject", "value": "Groupe"}]}})
    if url.endswith("/messages"):
        return Reponse({"messages": [{"id": "m1"}]})
    if "/threads/" in url:
        texte = base64.urlsafe_b64encode("Bonjour, nous serons 20.".encode()).decode()
        return Reponse({"messages": [{"id": "m1", "payload": {"mimeType": "text/plain", "body": {"data": texte},
                                                             "headers": [{"name": "From", "value": "client@exemple.be"}]}}]})
    return Reponse({"access_token": "acces", "refresh_token": "durable-secret", "expires_in": 3600})


@pytest.fixture()
def configure(monkeypatch):
    monkeypatch.setenv("GMAIL_CLIENT_ID", "id")
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "secret")
    gmail._cache_acces.clear()


def test_liaison_et_lecture(session, acteur_admin, configure, monkeypatch):
    url = gmail.url_liaison(session, acteur_admin)
    etat = url.split("state=")[1].split("&")[0]
    with pytest.raises(ErreurMetier):
        gmail.terminer_liaison(session, acteur_admin, "code", "etat-invente", poster=faux_google, lire=faux_google)
    gmail.terminer_liaison(session, acteur_admin, "code", etat, poster=faux_google, lire=faux_google)
    c = session.get(ConnexionGmail, 1)
    assert c.email == "info@albert.brussels" and "durable-secret" not in c.jeton_chiffre
    with pytest.raises(ErreurMetier):  # le même « state » ne sert qu'une fois
        gmail.terminer_liaison(session, acteur_admin, "code", etat, poster=faux_google, lire=faux_google)
    monkeypatch.setattr(gmail.requests, "post", faux_google)
    msgs = gmail.rechercher(session, "from:client@exemple.be", lire=faux_google)
    assert msgs[0]["objet"] == "Groupe"
    assert gmail.lire_fil(session, "t1", lire=faux_google)[0]["texte"] == "Bonjour, nous serons 20."


def test_seul_un_admin_relie(session, acteur_chatgpt, configure, http_equipe):
    with pytest.raises(ErreurMetier):
        gmail.url_liaison(session, acteur_chatgpt)
    assert http_equipe.get("/api/gmail/relier", follow_redirects=False).status_code == 403
