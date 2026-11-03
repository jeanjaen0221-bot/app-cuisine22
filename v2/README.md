# Restaurant Albert — version 2

Nouvelle version de l'outil, **séparée de l'ancienne** (`app/`, qui reste en service tant que la v2 n'est pas mise en production).
Cahier des charges : [`docs/REFONTE_ANALYSE.md`](../docs/REFONTE_ANALYSE.md) et [`docs/REGLES_CHATGPT.md`](../docs/REGLES_CHATGPT.md).

## Ce que fait la v2

Parcours : **Client → Fiche → Devis TVA comprise → transmis à la compta** (qui l'envoie au client) **→ événement → Bon pour facturation → transmis à la compta** (qui facture).

| Écran | Rôle |
|---|---|
| Tableau de bord | Fiches des 7 jours, fiches à compléter, devis à mettre à jour, devis sans réponse, bons à faire, prix manquants |
| Fiches | Liste par jour (filtres espace salle / City / Rooftop, statut), formulaire, PDF salle / cuisine / complet, PDF du jour |
| Clients | Une fiche par client, réutilisée ; détection des doublons (« Dupont SA » = « dupont s.a. ») ; contrôle du n° TVA belge |
| Devis | Calculé depuis la fiche aux prix du menu Prix ; brouillon → validé → transmis → envoyé → accepté / refusé ; nouvelle version si le client change d'avis |
| Bons pour facturation | Couverts réels, extras, écart avec le devis ; transmis à la compta, marqué « facturé » |
| Espace compta | « À envoyer », « En attente de réponse », « À facturer », historique (rôle `compta`) |
| Prix | Tout ce qui se vend, TVA comprise, avec le filtre « Prix manquants » et un compteur rouge |
| Formules | Formules repas et boissons : ce qu'on choisit sur une fiche ; le prix vient du menu Prix |
| Salle | Plan de base (tables, zones, réglages) et plan de chaque service : fiches du jour + PDF de réservations, placement automatique ou à la main, PDF du service et PDF annoté ; la table apparaît sur la fiche |
| Plaintes | Rapport rattaché au client et à la fiche, gravité, brouillon (ChatGPT) → ouverte → traitée, PDF |
| Notes | Post-it de l'équipe sur le tableau de bord (auteur, épinglage) |
| Achats | Boissons (stock min/max, colisage), fournisseurs et prix d'achat, réassort → un bon de commande par fournisseur, PDF/CSV, suivi envoyé → reçu ; import d'une carte (texte, CSV, PDF) |
| ChatGPT | Adresse du connecteur, connexions actives, bouton « Couper » |
| Journal | Qui a fait quoi, sur le site ou par ChatGPT (admin) |
| Utilisateurs / Paramètres | Rôles admin / équipe / compta, droits « prix » et « chatgpt » ; coordonnées du restaurant, validité des devis ; synchronisation Zenchef ; liaison Gmail |

Décisions appliquées : pas de facture dans l'outil, la compta envoie elle-même, **tous les prix TVA comprise**, ni remise ni acompte,
trois privatisations (Semi-privatisation, Privatisation complète, Privatisation City 600 €), City est un espace à part,
Sharing et Brunch sans plats listés, « À la carte » = prix de chaque plat.

Catalogue de départ (créé au premier démarrage, jamais écrasé ensuite) : 1 service 28 €, 2 services 32 €, 3 services 40 €,
Sharing 32 €, Brunch 36 €, formule avec alcool 20 €, sans alcool 10 €, coupe de cava 6 €, coupe de champagne 11 €,
Privatisation City 600 €. **À compléter dans le menu Prix** : planche apéro (prix TVA comprise), semi-privatisation,
privatisation complète, et le prix de chaque plat de la carte pour « À la carte ».

## Organisation du code

```
v2/
├── backend/
│   ├── albert/
│   │   ├── domain/      règles pures : saisies tolérantes, règles des fiches, calcul des devis (testées)
│   │   ├── services/    clients, fiches, devis, bons, catalogue, comptes — avec journal et contrôles d'accès
│   │   ├── api/         API du site (/api), session en cookie HttpOnly, en-tête anti-CSRF X-Albert
│   │   ├── mcp/         connecteur ChatGPT (/mcp) : OAuth en base, droits par connexion, consignes
│   │   ├── pdf/         fiche salle/cuisine, devis, bon (texte échappé)
│   │   ├── salle/       plan de salle : géométrie, placement automatique, PDF (repris de l'ancienne version)
│   │   └── main.py
│   ├── alembic/         migrations de la base (alembic upgrade head)
│   └── tests/           75 tests : règles, parcours complet, droits, ChatGPT de bout en bout
├── frontend/            site React (Vite, TypeScript)
└── Dockerfile
```

Les **mêmes services** servent le site et ChatGPT : une règle n'existe qu'à un seul endroit.

## Lancer en local

```bash
# Serveur
cd v2/backend
pip install -r requirements-dev.txt
export SECRET_KEY=dev-un-secret-long-pour-le-developpement DATABASE_URL=sqlite:///./albert_v2.db COOKIE_SECURE=0
alembic upgrade head
uvicorn albert.main:app --reload --port 8000

# Site (autre terminal) : http://localhost:5173
cd v2/frontend
npm install
npm run dev
```

Au premier accès, le site demande de créer le compte administrateur.

Tests : `cd v2/backend && python -m pytest` · Vérification du site : `cd v2/frontend && npm run build`.

## Mettre en production (Railway)

1. Créer un **nouveau service** (et une **nouvelle base PostgreSQL**) : ne pas réutiliser ceux de l'ancienne version.
2. Dossier racine du service : `v2` (le `Dockerfile` s'y trouve).
3. Variables : voir [`.env.example`](./.env.example) — `APP_ENV=production`, `DATABASE_URL`, `SECRET_KEY`,
   `PUBLIC_BASE_URL` (adresse https du service).
4. Au démarrage, le conteneur applique les migrations puis lance le serveur. Un seul processus.

## Connecter ChatGPT

1. Dans **Utilisateurs**, donner le droit « Connecter ChatGPT » au compte concerné (les admins l'ont déjà).
2. Dans ChatGPT, ajouter un connecteur personnalisé (serveur MCP distant) avec l'adresse `https://<votre-domaine>/mcp`,
   authentification OAuth.
3. ChatGPT ouvre la page de connexion du restaurant : se connecter et cocher les droits accordés
   (`lecture`, `fiches:ecrire`, `devis:preparer`, `plaintes:preparer`, `achats:preparer`, `gmail:lire`).
4. Les consignes données à ChatGPT sont dans `backend/albert/mcp/consignes.txt` (envoyées automatiquement par le connecteur).

ChatGPT ne peut **jamais** : valider ou transmettre un devis ou un bon, toucher aux prix ou aux formules, supprimer quoi que ce soit,
changer le statut d'une fiche (sauf annulation en deux temps, avec confirmation), écrire au client. Ces refus sont appliqués
par le serveur, pas seulement par les consignes. Chaque action de ChatGPT apparaît dans le journal et l'historique de la fiche.

## Pas encore dans la v2

La reprise des données de l'ancienne version (clients, fiches, plats, plaintes, boissons…) : prévue juste avant la bascule.
