# Analyse complète du site actuel et plan de refonte

Date : 22 octobre 2026
Périmètre : tout le dépôt `app-cuisine22` (backend FastAPI, frontend React, PDF, API GPT, pont MCP ChatGPT, déploiement).
Objectif de la refonte : un outil centré sur **les clients, les fiches cuisine/salle, les devis et les factures**, que **ChatGPT peut piloter** en respectant des règles strictes.

Document compagnon : [`REGLES_CHATGPT.md`](./REGLES_CHATGPT.md) (règles et contrat d'outils pour ChatGPT).

---

## Sommaire

1. [Résumé](#1-résumé)
2. [Ce que fait le site aujourd'hui](#2-ce-que-fait-le-site-aujourdhui)
3. [Architecture technique actuelle](#3-architecture-technique-actuelle)
4. [Modèle de données actuel](#4-modèle-de-données-actuel)
5. [Les fiches : règles métier existantes](#5-les-fiches--règles-métier-existantes)
6. [La facturation actuelle](#6-la-facturation-actuelle)
7. [L'accès ChatGPT actuel](#7-laccès-chatgpt-actuel)
8. [Problèmes constatés](#8-problèmes-constatés)
9. [Ce qu'il faut garder, jeter, refaire](#9-ce-quil-faut-garder-jeter-refaire)
10. [Cible : la nouvelle application](#10-cible--la-nouvelle-application)
11. [Cible : l'accès ChatGPT](#11-cible--laccès-chatgpt)
12. [Plan de réalisation](#12-plan-de-réalisation)
13. [Questions à trancher avant de coder](#13-questions-à-trancher-avant-de-coder)

---

## 1. Résumé

- Le site est une application **FastAPI + React** déployée sur **Railway** (PostgreSQL), pour le Restaurant Albert (Bruxelles). Elle a grandi par ajouts : fiches cuisine, plan de salle, Rooftop, plaintes, commandes de boissons, fournisseurs, facturation, notes, comptes utilisateurs, et deux accès pour ChatGPT.
- **Il n'existe pas de notion de « client »** : le nom du client est un texte libre sur chaque réservation. Les coordonnées de facturation sont recopiées pour chaque réservation.
- **La « facture » n'en est pas une** : c'est une *feuille de facturation interne* sans prix, sans TVA, sans total et sans numéro (le champ « N° facture » est imprimé vide). Elle ne peut pas être envoyée à un client.
- **ChatGPT a déjà deux portes d'entrée** : une Action de Custom GPT (`/api/gpt`, clé API statique) et un serveur **MCP** (`/mcp`, OAuth) pour les connecteurs ChatGPT. Les règles du formulaire ont été recopiées côté serveur, ce qui est la bonne approche, mais elles sont dupliquées entre le React et Python et commencent à diverger (un test échoue déjà).
- Environ 22 000 lignes. Près de la moitié concerne le **plan de salle** (`floorplan.py`, `FloorCanvas.tsx`, `FloorPlanPage.tsx`), sans rapport avec les fiches et factures.
- **Recommandation** : repartir d'un nouveau modèle de données centré sur `Client → Événement (fiche) → Devis/Facture`, avec **une seule couche de règles métier côté serveur**, utilisée à la fois par le site et par ChatGPT (via MCP). Garder le savoir-faire existant (listes de valeurs, alias, rendu PDF des notes, Gmail en brouillon seulement), abandonner le reste ou le mettre de côté.

---

## 2. Ce que fait le site aujourd'hui

Menu latéral (`app/frontend/src/pages/App.tsx`), chaque section est protégée par une permission :

| Section | URL | Permission | Rôle |
|---|---|---|---|
| Fiches | `/` | `reservations` | Liste des réservations à venir, rappels « plats manquants », création/édition de fiche, PDF |
| Passées | `/past` | `reservations` | Historique paginé |
| Rooftop | `/rooftop` | `rooftop` | Planning hebdomadaire des réservations Rooftop (société, contact, paiement, occasion) |
| Plaintes | `/incidents` | `incidents` | Rapports d'incident + remplissage par IA (OpenAI/Groq) + PDF |
| Salle | `/salle` | `floorplan` | Plan de salle, import du PDF de réservations Zenchef, placement automatique, PDF annoté |
| Base de plats | `/menu` | `menu` | Catalogue des plats (nom, type entrée/plat/dessert, actif) — **sans prix** |
| Facturation | `/facturation` | `billing` | Coordonnées de facturation par réservation, suppléments, bibliothèque de suppléments |
| Commande / Achats | `/commande`, `/achats` | `orders` | Boissons, stock min/max, réassort, bons de commande, export CSV |
| Fournisseurs | `/fournisseurs` | `suppliers` | Fournisseurs et prix d'achat des boissons |
| Paramètres | `/settings` | `settings` | Jeton Zenchef, allergènes et icônes |
| Utilisateurs | `/users` | admin | Comptes, rôles, permissions |
| Notes (widget) | partout | `dashboard` | Post-it partagés |

Intégrations externes :
- **Zenchef** : synchronisation des réservations de plus de 10 personnes (`routers/zenchef.py`).
- **Gmail** (`info@albert.brussels`) : lecture, recherche et **brouillons uniquement** (`gmail_service.py`, `routers/gmail_oauth.py`).
- **OpenAI / Groq** : uniquement pour remplir les rapports d'incident (`routers/incidents.py`).
- **ChatGPT** : API Action (`gpt_api.py`) et MCP (`mcp_bridge.py`).

---

## 3. Architecture technique actuelle

```
Navigateur (React 18 + Vite + Tailwind, JWT en localStorage)
        │  /api/*  (Bearer JWT)
        ▼
FastAPI (app/backend/main.py)
 ├─ middleware d'auth + table de permissions par préfixe d'URL
 ├─ routers/*            (API du site)
 ├─ /api/gpt  → gpt_api.py      (sous-app, clé API statique, OpenAPI dédié)
 ├─ /mcp      → mcp_bridge.py   (MCP Streamable HTTP + OAuth 2.1/PKCE maison)
 ├─ pdf_service.py (ReportLab) → fichiers dans generated_pdfs/ ou /tmp
 └─ SPA fallback (sert app/frontend/dist)
        │
        ▼
PostgreSQL (Railway) / SQLite (local) via SQLModel
 + migrations "maison" exécutées à chaque démarrage (database.py)
```

Points notables :
- **Auth du site** : PBKDF2-SHA256 (600 000 itérations), JWT HS256 de 8 h, rôles `admin`/`member` + permissions CSV. Le premier compte créé via `/api/auth/setup` est admin.
- **Contrôle d'accès** : `API_PERMISSION_RULES` dans `main.py` ; une route non listée est refusée aux membres (bon choix « fermé par défaut »).
- **Migrations** : pas d'Alembic. `database.py` (870 lignes) ajoute les colonnes manquantes à chaque démarrage, et `run_startup_migrations()` **supprime les doublons de réservations** à chaque démarrage en production.
- **Déploiement** : `nixpacks.toml` (Railway) + deux `Dockerfile` + deux `Procfile` + deux `requirements.txt` qui doivent rester synchronisés à la main.
- **Tests** : 41 tests backend (`app/backend/tests`) ; aucun test frontend. Exécution le 22/10/2026 : **40 réussis, 1 échoué** (`test_empty_fiche_is_rejected`, voir §8).
- **Variables d'environnement utilisées** : `DATABASE_URL`/`PG*`, `JWT_SECRET`, `AUTH_TOKEN_TTL_HOURS`, `CORS_ORIGINS`, `TZ`, `PUBLIC_BASE_URL`, `GPT_API_KEY_HASH`, `MCP_ACCESS_TOKEN_TTL_SECONDS`, `MCP_REFRESH_TOKEN_TTL_SECONDS`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `OPENAI_*`, `GROQ_*`, `AI_PROVIDER`, `PDF_DIR`, `FINAL_STAMP_PATH`.

---

## 4. Modèle de données actuel

Défini dans `app/backend/models.py`.

| Table | Contenu | Remarques |
|---|---|---|
| `reservation` | client_name, pax, service_date, arrival_time, drink_formula, menu_formula, notes, status (draft/confirmed/printed), final_version, on_invoice, allergens (CSV), is_rooftop, company, contact, payment_method, special_requests, occasion | Unicité sur (date, heure, nom, pax). **Le client n'est qu'un texte.** |
| `reservationitem` | type (entrée/plat/dessert/supplément), name, quantity, comment | Nom recopié, **pas de lien vers le catalogue, pas de prix** |
| `menuitem` | name, type, active | Catalogue sans prix ni TVA ni allergènes |
| `billinginfo` | 1:1 avec la réservation : société, adresse, CP, ville, pays, TVA, réf. PO, email, tél., conditions, notes | **Recopié à chaque réservation**, pas de fiche client réutilisable |
| `supplementpreset` | name, default_quantity | Sans prix |
| `invoicesupplement` | description, quantity | **Table morte** : les suppléments sont en réalité stockés dans `reservationitem` |
| `reservationreminder` | snooze / mute des rappels | |
| `allergen` | clé, libellé, icône (octets) | Icônes aussi en fichiers |
| `user` | email, hash, rôle, permissions | |
| `setting` | clé/valeur (Zenchef, clients OAuth MCP) | |
| `gmailtoken` | refresh token Gmail | En clair dans la base |
| `note` | post-it | |
| `incidentreport` | rapports de plainte | |
| `drink`, `drinkstock`, `drinkvendor`, `supplier`, `purchaseorder`, `purchaseorderitem` | achats boissons | Seul endroit avec des prix (en centimes) |
| `floorplanbase`, `floorplaninstance` | plan de salle (JSON) | |
| `processedrequest` | idempotence Zenchef | |

---

## 5. Les fiches : règles métier existantes

Ces règles sont **le vrai capital du projet** : elles doivent être reprises telles quelles (ou validées) dans la nouvelle version. Elles vivent aujourd'hui à deux endroits : le formulaire React (`ReservationForm.tsx`) et la couche GPT (`gpt_api.py`).

Champs obligatoires : nom du client, nombre de couverts (1 à 500), date de service, heure d'arrivée.

Listes fermées :
- **Formule boissons** : `sans alcool` (défaut), `avec alcool`, `sans alcool + cava`, `avec alcool + cava`, `sans alcool + champ`, `avec alcool + champ`, `à la carte`, `sans Formule`.
- **Formule repas** : vide, `1 service`, `2 services`, `3 services`, `À la carte`, `Brunch`.
- **Types de ligne** : `entrée`, `plat`, `dessert`, `supplément`.
- **Allergènes** (14) : gluten, crustaces, oeufs, poisson, arachides, soja, lait, fruits_a_coque, celeri, moutarde, sesame, sulfites, lupin, mollusques (+ ceux ajoutés dans Paramètres).
- **Heures proposées** : 12:00, 12:30, 13:00, 13:30, 19:30, 20:00.

Règles :
1. **Les plats prévalent sur la formule** : s'il y a au moins une entrée/plat/dessert, la formule repas est vidée.
2. **Total par type ≤ couverts** : la somme des quantités d'entrées (resp. plats, desserts) ne dépasse pas `pax`.
3. **Brunch = buffet** : aucune entrée/plat/dessert, seulement des suppléments (Privatisation, Champagne, Planche apéro…).
4. **Il faut au moins un plat ou une formule** (règle du formulaire) — mais la couche GPT accepte maintenant une fiche vide en brouillon (contradiction, voir §8).
5. **Noms de plats** : repris avec l'orthographe du catalogue quand ils y existent ; hors catalogue autorisé.
6. **Suppléments préservés** : une mise à jour des plats sans suppléments conserve les suppléments existants (ils sont gérés depuis la facturation).
7. **Statuts** : `draft` (Brouillon) → `confirmed` (Confirmée) → `printed` (Imprimée). Tampon **« Version finale »** imprimé sur le PDF. ChatGPT ne doit toucher ni au statut ni au tampon.
8. **Toute modification remet à zéro** la date du dernier export PDF (sert à repérer les fiches à réimprimer).
9. **Rappels** : une fiche dans les 5 prochains jours sans plat ni formule déclenche un rappel (reportable ou masquable).
10. **Notes** : balisage maison `**gras**`, `_italique_`, `[color=x]…[/color]`, lignes `- ` en puces.

PDF de fiche (`pdf_service.py`) :
- Version **salle** : en-tête, couverts, formule, plats, suppléments, formule boissons (badge coloré selon la formule), allergènes avec icônes, notes.
- Version **cuisine** : même contenu sans boissons ni notes, décalée de 5 cm vers le bas, **dupliquée s'il y a des desserts** (une page pour le passe pâtisserie).
- Par défaut : salle + cuisine (+ cuisine bis) dans un seul PDF, et la feuille de facturation ajoutée à la fin si elle existe.
- PDF du jour : toutes les fiches d'une date.

---

## 6. La facturation actuelle

- Saisie des coordonnées de facturation **par réservation** (société, adresse, TVA, réf. PO, email, conditions « Paiement à 30 jours », pays « Belgique » par défaut).
- Créer une facturation coche automatiquement « Sur facture ».
- Le PDF s'intitule **« FEUILLE DE FACTURATION (INTERNE) »** et contient : coordonnées, date, heure, pax, formule repas (déduite des plats si vide), formule boissons, liste des suppléments **avec quantités seulement**, conditions de paiement, notes.
- **Absents** : prix unitaires, montants, taux de TVA, totaux HTVA/TVA/TVAC, numéro de facture, date d'échéance, coordonnées et n° TVA du restaurant, IBAN, communication structurée, acompte, avoirs, suivi des paiements.

Conclusion : la facturation réelle se fait **ailleurs** (logiciel comptable ou à la main). Le site produit un bon de préparation pour la comptabilité, pas une facture.

---

## 7. L'accès ChatGPT actuel

### 7.1 Action de Custom GPT — `/api/gpt`
- Sous-application FastAPI avec son propre schéma OpenAPI (`/api/gpt/openapi.json`), à importer dans un Custom GPT.
- Authentification : **une seule clé statique** (hash SHA-256 dans `GPT_API_KEY_HASH`, générée par `scripts/generate_gpt_api_key.py`). Pas d'utilisateur identifié, pas de droits par action.
- Routes : lister/rechercher, lire, créer, modifier (PATCH), ajouter/retirer un plat, dupliquer, **supprimer**, PDF fiche, lire/créer la facturation, PDF facture, recherche catalogue, Gmail (recherche, fil, message, brouillon).
- Bonnes idées à garder : listes de valeurs en `enum`, **normalisation des variantes** (« 3 Services », « 19h30 », « 17/09/2026 », « lactose » → `lait`, « Main course » → `plat`), messages d'erreur 422 qui listent les valeurs permises, création toujours en brouillon.

### 7.2 Serveur MCP — `/mcp`
- Pour les **connecteurs ChatGPT** (et tout client MCP). OAuth 2.1 + PKCE, enregistrement dynamique des clients (stocké dans `setting`), page de connexion avec le compte du site, **réservé aux administrateurs**.
- 16 outils : `fiches_rechercher`, `fiche_lire`, `fiche_creer`, `fiche_modifier`, `fiche_item_ajouter`, `fiche_item_retirer`, `fiche_dupliquer`, `fiche_supprimer`, `menu_rechercher`, `facturation_lire`, `facturation_mettre_a_jour`, `gmail_rechercher`, `gmail_messages_client`, `gmail_lire_fil`, `gmail_lire_message`, `gmail_creer_brouillon`.
- Les outils réutilisent les fonctions de `gpt_api.py` (bonne idée : une seule logique).

### 7.3 Instructions
`GPT_INSTRUCTIONS.md` contient des règles correctes mais courtes, à coller dans le Custom GPT. Le serveur MCP n'envoie que 2 lignes d'instructions.

---

## 8. Problèmes constatés

Classés par gravité. Fichier et ligne indiqués quand c'est utile.

### 8.1 Critiques (données, sécurité, argent)
1. **Pas de vraie facture** (§6) : pas de prix, TVA, total, numérotation. Bloquant pour l'objectif « factures ».
2. **Pas d'entité client** : coordonnées ressaisies à chaque fois, aucun historique par client, doublons et fautes de frappe inévitables.
3. **Suppression des doublons à chaque démarrage** (`database.py`, `run_startup_migrations`) : en production, deux réservations identiques (même nom, date, heure, pax) sont effacées silencieusement à chaque redéploiement, sans tenir compte des lignes/facturation liées.
4. **ChatGPT peut supprimer des fiches** (`fiche_supprimer`, `DELETE /api/gpt/fiches/{id}`) sans garde-fou serveur : la confirmation ne repose que sur la consigne donnée au modèle.
5. **Clé API GPT unique et toute-puissante** : impossible de savoir qui a fait quoi, impossible de limiter à la lecture, révocation = changer la clé pour tout le monde.
6. **Aucun journal d'audit** : aucune trace de qui (humain ou ChatGPT) a créé/modifié/supprimé une fiche.
7. **Flux OAuth Gmail sans paramètre `state`** (`routers/gmail_oauth.py`) : `/start` et `/callback` sont publics ; n'importe qui peut relancer le flux et remplacer le compte Gmail relié (risque de détournement de la boîte utilisée par ChatGPT).
8. **Jeton Gmail stocké en clair** dans la table `gmailtoken`.

### 8.2 Importants (bugs, incohérences)
9. **Règle « au moins un plat ou une formule » incohérente** : le formulaire l'exige, la doc OpenAPI de `POST /fiches` l'annonce, mais le code GPT l'a retirée dans le dernier commit (`gpt_api.py:388-392`) → le test `test_empty_fiche_is_rejected` échoue.
10. **Texte entre `<` et `>` perdu dans les PDF** : les noms de client, de plats et les commentaires ne sont pas échappés avant ReportLab (`pdf_service.py`, fonctions `section`). Vérifié : « Dupont & Fils <SA> » s'imprime « Dupont & Fils », « Steak <saignant> » s'imprime « Steak ». Un caractère mal placé peut aussi faire planter la génération.
11. **Noms de fichiers PDF non nettoyés** : le nom du client (avec `&`, `<`, `/`, accents…) est mis tel quel dans le nom du fichier.
12. **Fonction PDF morte et cassée** : `generate_reservation_pdf()` utilise une variable `billing` inexistante (plante si appelée ; elle est importée mais jamais utilisée).
13. **Duplication incomplète** : `duplicate_reservation` ne recopie ni société, contact, occasion, demandes spéciales, Rooftop, ni « Sur facture ».
14. **Règles en double** : formulaire React et `gpt_api.py` ont chacun leur copie des listes et règles ; l'API interne (`/api/reservations`) accepte n'importe quelle valeur (formule libre, allergène inconnu, date vide → aujourd'hui, heure vide → 00:00, nom vide → « Client »).
15. **Zenchef** écrit `drink_formula="Sans alcool"` (majuscule), valeur hors de la liste du formulaire.
16. **Rappels calculés en UTC** (`reminders.py`) alors que « à venir/passées » utilise `TZ` (Europe/Paris) : décalage possible en soirée.
17. **MCP** : les outils d'ajout/retrait de plat, de facturation et de lecture ne passent pas par `_tool_write_result` → ChatGPT reçoit une erreur générique au lieu du message utile. Pas d'outil MCP pour obtenir le PDF de fiche ou de facture.
18. **États OAuth MCP en mémoire** (`_pending`, `_codes`) : perdus au redémarrage et incompatibles avec plusieurs workers.
19. **Performances** : `GET /api/reservations` charge **toutes** les réservations puis fait une requête par réservation pour les lignes (N+1). La page Facturation l'appelle à chaque ouverture.
20. **PDF générés sur disque** (`generated_pdfs/` ou `/tmp`) : éphémères sur Railway, jamais nettoyés, et une facture n'est jamais figée (elle est recalculée à chaque téléchargement).

### 8.3 Dette technique
21. Pas d'Alembic : 870 lignes de migrations « maison » exécutées à chaque démarrage.
22. `pdf_service.py` : le même bloc (plats, boissons, allergènes, notes) est copié 6 fois.
23. Doublons de configuration : 2 `requirements.txt`, 2 `Dockerfile`, 2 `Procfile`, `vite.config.js` et `.ts`, fichiers `tsbuildinfo` versionnés, scripts de test à la racine (`test_pdf_parser.py`…).
24. JWT dans `localStorage` (exposé en cas de XSS), pas de limitation des tentatives de connexion, `/docs` et `/openapi.json` du site publics.
25. Logs `print()` partout, dont le contenu des requêtes de création.
26. Code mort : table `invoicesupplement`, `generate_reservation_pdf`, `listFloorBases`.

---

## 9. Ce qu'il faut garder, jeter, refaire

| Élément | Décision | Pourquoi |
|---|---|---|
| Listes de valeurs, alias, normalisation (`gpt_api.py`) | **Garder** et déplacer dans un module « règles » unique | Testé, éprouvé avec ChatGPT |
| Règles des fiches (§5) | **Garder** après validation (§13) | C'est le métier |
| Rendu des notes (`format_notes_markup`) et tests | **Garder** | Fonctionne, testé |
| Mise en page PDF salle/cuisine (contenu, badge boissons, icônes allergènes, page dessert) | **Garder le contenu**, réécrire le code (1 seul gabarit) | Connu de l'équipe en cuisine |
| Gmail lecture + brouillons uniquement | **Garder** (corriger `state`, chiffrer le jeton) | Bon niveau de sécurité |
| MCP + OAuth | **Garder le principe**, réécrire proprement | C'est la bonne porte pour ChatGPT |
| Action Custom GPT à clé statique | **Remplacer** par MCP (ou garder en lecture seule) | Pas d'identité, pas de droits |
| Auth du site, rôles/permissions | **Garder** l'idée, simplifier les rôles | |
| Facturation actuelle | **Refaire** | Ne produit pas de facture |
| `billinginfo` par réservation | **Remplacer** par une fiche Client | |
| Plan de salle, Rooftop, plaintes, boissons/achats/fournisseurs, notes | **Hors périmètre** de la refonte : à décider (§13) | Sans lien avec fiches/factures |
| Migrations maison, suppression auto des doublons | **Jeter** → Alembic | Risque de perte de données |

---

## 10. Cible : la nouvelle application

### 10.1 Principe directeur
**Une seule source de vérité pour les règles, côté serveur.** Le site (formulaires) et ChatGPT (outils MCP) appellent la même couche « services » ; aucune règle ne vit uniquement dans le React ou uniquement dans une consigne donnée à ChatGPT.

```
            Site React                      ChatGPT (connecteur MCP)
                │                                     │
           API REST /api                      Serveur MCP /mcp
                └──────────────┬──────────────────────┘
                               ▼
              Services métier (règles, validation, numérotation, TVA)
                               ▼
                 Dépôt de données (PostgreSQL + Alembic)
                               ▼
              Journal d'audit (qui, quoi, quand, via site/ChatGPT)
```

### 10.2 Modèle de données proposé

**Client** (`client`)
- type : `particulier` | `entreprise`
- nom / raison sociale, prénom et nom du contact
- email, téléphone, langue (fr/nl/en)
- adresse de facturation (rue, n°, boîte, CP, ville, pays), n° TVA (validé, format BE0123456789), identifiant Peppol si entreprise
- conditions de paiement par défaut, notes internes, allergies/préférences récurrentes
- dates de création/modification, archivé oui/non

**Événement / Fiche** (`fiche`) — remplace `reservation`
- client (lien obligatoire), contact sur place
- date, heure d'arrivée, couverts, espace (salle, Rooftop, privatisation…)
- formule boissons, formule repas (mêmes listes qu'aujourd'hui)
- allergènes (liste de clés, plus de CSV), notes salle, notes cuisine (séparées)
- statut : `brouillon` → `option` → `confirmée` → `finale` → `réalisée` | `annulée`
- version (incrémentée à chaque modification après « finale ») et date du dernier PDF imprimé

**Ligne de fiche** (`fiche_ligne`)
- type : entrée / plat / dessert / supplément / boisson / location
- **lien vers le catalogue** (optionnel pour du hors-catalogue), libellé figé, quantité, commentaire
- prix unitaire HTVA et taux de TVA **copiés au moment de l'ajout** (le prix d'un devis ne change pas si le catalogue change)

**Catalogue** (`produit`) — remplace `menuitem` et `supplementpreset`
- libellé, type, prix HTVA, taux de TVA, allergènes contenus, actif
- formules (`1/2/3 services`, brunch, formules boissons) comme produits à prix par personne

**Devis** (`devis`) et **Facture** (`facture`)
- numéro **séquentiel sans trou** par année (ex. `F-2026-0001`), attribué à l'émission seulement
- client (coordonnées **figées** à l'émission), fiche liée, dates d'émission, de prestation, d'échéance
- lignes figées, totaux HTVA par taux, TVA par taux, total TVAC, acompte déduit
- statut facture : `brouillon` → `émise` → `envoyée` → `payée partiellement` → `payée` ; une facture émise **ne se modifie plus** : on fait une **note de crédit** (`avoir`)
- communication structurée belge (+++123/4567/89012+++), PDF stocké (pas recalculé)

**Paiement** (`paiement`) : facture, date, montant, moyen (virement, carte, espèces, lien), référence.

**Journal d'audit** (`audit`) : utilisateur, canal (`site` | `chatgpt`), action, objet, avant/après, date.

**Utilisateur** : comme aujourd'hui, avec rôles simplifiés (voir 11.3).

### 10.3 Facturation : exigences (Belgique) — à valider avec le comptable
- Mentions obligatoires : date, numéro unique et séquentiel, identité et n° TVA du restaurant et du client assujetti, date de la prestation, description et quantités, prix unitaire HTVA, base HTVA par taux, taux et montant de TVA, total.
- Taux usuels en restauration (à confirmer) : **12 %** sur la nourriture servie sur place, **21 %** sur les boissons ; location de salle / privatisation selon le cas.
- **Facturation électronique B2B** : depuis le 1ᵉʳ janvier 2026, les factures entre entreprises belges assujetties doivent être échangées en format structuré via **Peppol**. Prévoir l'export UBL/Peppol (ou l'envoi via le logiciel comptable) pour les clients entreprises.
- Les montants sont calculés en **centimes entiers** côté serveur ; ChatGPT ne calcule jamais un total lui-même.

### 10.4 PDF
- Un seul moteur de gabarits (ReportLab avec composants partagés, ou HTML → PDF avec WeasyPrint) : **fiche salle**, **fiche cuisine** (+ page dessert), **devis**, **facture**, **note de crédit**, **récapitulatif du jour**.
- Tout texte utilisateur échappé (corrige le bug §8 n° 10).
- PDF de devis/facture **stockés** à l'émission (objet stockage S3/R2 ou base), jamais régénérés différemment.

### 10.5 Écrans du site
1. **Tableau de bord** : fiches des 7 prochains jours, rappels (plats manquants, fiches non finalisées, factures en retard).
2. **Clients** : recherche, fiche client avec historique des événements, devis, factures, paiements.
3. **Fiches** : liste/agenda, formulaire (mêmes règles qu'aujourd'hui, validées par le serveur), boutons PDF salle/cuisine.
4. **Devis & factures** : créer depuis une fiche, émettre, envoyer (brouillon Gmail), enregistrer un paiement, note de crédit.
5. **Catalogue** : produits, prix, TVA, allergènes, formules.
6. **Paramètres** : identité du restaurant (nom, adresse, TVA, IBAN, logo), numérotation, allergènes, utilisateurs, connexion ChatGPT, connexion Gmail.
7. **Journal** : qui a fait quoi (y compris ChatGPT).

### 10.6 Choix techniques recommandés
- Garder **FastAPI + SQLModel/SQLAlchemy + PostgreSQL + React/Vite/Tailwind** (l'équipe connaît, Railway marche).
- **Alembic** pour les migrations ; plus aucune modification de schéma au démarrage.
- Un seul `Dockerfile`, un seul `requirements.txt` (ou `pyproject.toml`), CI GitHub Actions (tests + build).
- Découpage backend : `domain/` (règles pures, testées), `services/`, `api/` (REST site), `mcp/` (outils ChatGPT), `pdf/`, `integrations/` (Gmail, Zenchef).
- Session du site en cookie `HttpOnly` + `SameSite`, limitation des tentatives de connexion.
- Logs structurés sans données personnelles.

---

## 11. Cible : l'accès ChatGPT

### 11.1 Canal
- **Serveur MCP unique** (`/mcp`, Streamable HTTP), branché dans ChatGPT comme **connecteur** (mode développeur / application). C'est le canal recommandé : identité de l'utilisateur, OAuth, outils typés.
- L'Action de Custom GPT à clé statique est **supprimée**, ou réduite à la **lecture seule** si un Custom GPT doit rester disponible.

### 11.2 Authentification
- OAuth 2.1 + PKCE avec le compte du site (comme aujourd'hui), mais : codes et états stockés en base (pas en mémoire), jetons révocables (liste en base), durée courte + refresh, page de consentement qui affiche les droits accordés.
- Chaque appel d'outil est exécuté **au nom de l'utilisateur connecté** et soumis à **ses** permissions.

### 11.3 Droits (scopes) proposés
| Scope | Permet |
|---|---|
| `fiches:lire` | rechercher/lire clients, fiches, catalogue |
| `fiches:ecrire` | créer/modifier clients et fiches en brouillon/option |
| `factures:lire` | lire devis, factures, paiements |
| `factures:preparer` | créer/modifier des **brouillons** de devis et de factures |
| `gmail:lire`, `gmail:brouillon` | lecture et brouillons Gmail |

**Jamais accordé à ChatGPT** : émettre une facture (numéro définitif), créer une note de crédit, enregistrer un paiement, supprimer quoi que ce soit, passer une fiche en « finale », modifier les prix du catalogue, envoyer un email. Ces actions restent des clics humains dans le site.

### 11.4 Garde-fous côté serveur (pas seulement dans les consignes)
1. Même validation que le site (module de règles unique).
2. **Annulation plutôt que suppression** : ChatGPT peut proposer d'annuler une fiche (statut `annulée`), jamais la supprimer.
3. **Confirmation en deux temps** pour les actions sensibles : l'outil renvoie un *aperçu* + un `jeton_confirmation` ; l'action n'est appliquée qu'avec ce jeton dans un second appel, après accord explicite de l'utilisateur.
4. **Verrou de version** : chaque modification envoie la `version` lue ; si quelqu'un a modifié entre-temps, refus (409) et relecture.
5. **Idempotence** : les créations acceptent une `cle_idempotence` pour éviter les doublons si ChatGPT réessaie.
6. Fiche `finale` ou `réalisée` : modifications refusées à ChatGPT.
7. **Audit** de chaque appel (canal `chatgpt`, utilisateur, paramètres, résultat).
8. Erreurs toujours renvoyées sous une forme lisible : `{ok: false, erreur: {code, message, valeurs_permises}}`.
9. Annotations MCP sur chaque outil (`readOnlyHint`, `destructiveHint`) pour que ChatGPT demande confirmation.

### 11.5 Outils MCP proposés
Lecture : `clients_rechercher`, `client_lire`, `fiches_rechercher`, `fiche_lire`, `catalogue_rechercher`, `references_lister` (formules, types, allergènes, statuts), `devis_lire`, `factures_rechercher`, `facture_lire`, `fiche_pdf_lien`, `facture_pdf_lien`.
Écriture : `client_creer`, `client_modifier`, `fiche_creer`, `fiche_modifier`, `fiche_ligne_ajouter`, `fiche_ligne_retirer`, `fiche_dupliquer`, `fiche_annuler` (avec confirmation), `devis_preparer`, `facture_preparer` (brouillon uniquement).
Gmail : `gmail_rechercher`, `gmail_lire_fil`, `gmail_creer_brouillon` (joindre le PDF d'un devis/facture).

Le détail (paramètres, règles, réponses) et les consignes à donner à ChatGPT sont dans [`REGLES_CHATGPT.md`](./REGLES_CHATGPT.md).

---

## 12. Plan de réalisation

| Étape | Contenu | Résultat |
|---|---|---|
| 0. Décisions | Répondre aux questions §13 ; valider les règles §5 et les taux de TVA avec le comptable | Spécification figée |
| 1. Socle | Nouveau squelette backend (domain/services/api/mcp), Alembic, auth, audit, CI, un seul Dockerfile | Projet vide qui se déploie |
| 2. Clients + catalogue | Modèles, API, écrans, import des clients depuis les `billinginfo` existants, prix/TVA | Fiche client réutilisable |
| 3. Fiches | Reprise des règles §5 dans `domain/`, écrans, PDF salle/cuisine, migration des réservations existantes | Parité avec l'actuel |
| 4. Devis & factures | Numérotation, TVA, PDF, notes de crédit, paiements, export Peppol/comptable | Vraies factures |
| 5. ChatGPT | Serveur MCP avec scopes, confirmation, audit, consignes (`REGLES_CHATGPT.md`), tests de scénarios | ChatGPT opérationnel et encadré |
| 6. Gmail | Reprise lecture + brouillons, pièce jointe PDF, correction `state`, jeton chiffré | Envoi de devis/factures en brouillon |
| 7. Bascule | Migration des données de production, période de double fonctionnement, arrêt de l'ancien | Ancien site retiré |

Migration des données existantes :
- `billinginfo` → `client` (dédoublonnage par n° TVA puis par nom de société normalisé), `reservation.client_name/company/contact` → rattachement au client.
- `reservation` + `reservationitem` → `fiche` + `fiche_ligne` (prix vides pour l'historique).
- `menuitem` + `supplementpreset` → `produit` (prix à compléter).
- Pas de reprise des « feuilles de facturation » comme factures (elles n'ont pas de numéro ni de montant).

---

## 13. Questions à trancher avant de coder

1. **Périmètre** : que deviennent le plan de salle, le Rooftop, les plaintes, les commandes de boissons/fournisseurs et les notes ? (supprimés, gardés tels quels dans l'ancien site, ou intégrés plus tard)
2. **Facturation** : le site doit-il **émettre les factures officielles** (numérotation légale, Peppol), ou seulement préparer des devis/pro forma que le comptable reprend dans un autre logiciel (lequel ?) ?
3. **Prix** : quels prix par formule et par personne ? Prix TVAC ou HTVA dans le catalogue ? Taux de TVA à appliquer à la privatisation / location ?
4. **Acomptes** : demande-t-on des acomptes (pourcentage, échéance) ?
5. **Statuts de fiche** : garder Brouillon/Confirmée/Imprimée, ou passer à Brouillon/Option/Confirmée/Finale/Réalisée/Annulée ?
6. **Règle « au moins un plat ou une formule »** : obligatoire dès la création, ou seulement pour passer en « confirmée » ? (aujourd'hui le site et ChatGPT ne sont pas d'accord)
7. **ChatGPT** : qui l'utilise (admins seulement, ou aussi le personnel) ? Doit-il pouvoir préparer des factures, ou uniquement des fiches et des devis ?
8. **Langues** : fiches et factures en FR seulement, ou aussi NL/EN pour les clients ?
9. **Zenchef** : garder la synchronisation des groupes > 10 personnes ? Créer automatiquement le client ?
10. **Hébergement** : rester sur Railway ? Où stocker les PDF de factures (obligation de conservation 7 ans en Belgique — à confirmer) ?
