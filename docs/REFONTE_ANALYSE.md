# Analyse complète du site actuel et plan de refonte

Date : 22 octobre 2026 — révision 2 (décisions de périmètre intégrées)
Périmètre analysé : tout le dépôt `app-cuisine22` (backend FastAPI, frontend React, PDF, API GPT, pont MCP ChatGPT, déploiement).

Objectif de la refonte : un outil centré sur **les clients, les fiches cuisine/salle et les devis**, que **ChatGPT peut piloter** en respectant des règles strictes.

Document compagnon : [`REGLES_CHATGPT.md`](./REGLES_CHATGPT.md) (règles et contrat d'outils pour ChatGPT).

---

## Décisions prises

| # | Décision | Conséquence |
|---|---|---|
| D1 | **L'outil prépare les devis, il ne fait pas les factures.** | Pas de numérotation légale de facture, pas de notes de crédit, pas de suivi des paiements, pas de Peppol. |
| D2 | **La comptabilité envoie elle-même** les devis et les factures aux clients. | L'outil ne parle jamais directement au client : il **transmet** à la comptabilité (devis prêt, puis bon pour facturation après l'événement). |
| D3 | **On ne gère pas la TVA : tous les prix sont TVA comprise (TVAC).** | Le catalogue, les devis et les récapitulatifs ne contiennent que des montants TVAC. Aucun taux, aucune ventilation HTVA/TVA. La ventilation éventuelle est faite par la comptabilité. |
| D4 | **Pas de remise, pas d'acompte.** | Aucune ligne de remise, aucun acompte sur les devis ni sur les bons pour facturation. Le prix est celui du catalogue. |
| D5 | **La compta a son propre compte dans l'outil** (option A). | Rôle `compta` avec deux listes : « À envoyer » (devis) et « À facturer » (bons pour facturation). Aucun email n'est envoyé par l'outil. |
| D6 | **On garde tous les modules** (plan de salle, Rooftop, plaintes, commandes de boissons, fournisseurs, notes) et on les améliore. | Ils font partie de la nouvelle version, branchés sur les mêmes clients et fiches (§13.4). |
| D7 | **Grille de prix fournie** (§12.3), formules boissons « + coupe » confirmées. | Le catalogue initial est connu ; « À la carte » = prix de chaque plat de la carte. |
| D8 | **Deux menus pour gérer les prix soi-même** : « Prix » et « Formules » (§13.5). | Les prix manquants et les formules se complètent dans l'outil, sans développeur. ChatGPT ne peut pas y toucher. |

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
10. [Cible : le parcours complet](#10-cible--le-parcours-complet)
11. [Cible : modèle de données](#11-cible--modèle-de-données)
12. [Cible : devis et transmission à la comptabilité](#12-cible--devis-et-transmission-à-la-comptabilité)
13. [Cible : écrans, PDF, technique](#13-cible--écrans-pdf-technique)
14. [Cible : l'accès ChatGPT](#14-cible--laccès-chatgpt)
15. [Plan de réalisation](#15-plan-de-réalisation)
16. [Questions encore ouvertes](#16-questions-encore-ouvertes)

---

## 1. Résumé

- Le site est une application **FastAPI + React** déployée sur **Railway** (PostgreSQL), pour le Restaurant Albert (Bruxelles). Elle a grandi par ajouts : fiches cuisine, plan de salle, Rooftop, plaintes, commandes de boissons, fournisseurs, facturation, notes, comptes utilisateurs, et deux accès pour ChatGPT.
- **Il n'existe pas de notion de « client »** : le nom du client est un texte libre sur chaque réservation, et les coordonnées de facturation sont recopiées pour chaque réservation.
- **Il n'existe aucun prix** dans la partie fiches : ni dans le catalogue de plats, ni sur les lignes, ni sur le PDF « facturation ». Impossible aujourd'hui de produire un devis chiffré.
- **ChatGPT a déjà deux portes d'entrée** : une Action de Custom GPT (`/api/gpt`, clé API statique) et un serveur **MCP** (`/mcp`, OAuth). Les règles du formulaire ont été recopiées côté serveur (bonne approche), mais elles sont dupliquées entre React et Python et divergent déjà (un test échoue).
- Environ 22 000 lignes, dont près de la moitié pour le **plan de salle**, sans rapport avec les fiches et devis.
- **Recommandation** : repartir d'un modèle centré sur `Client → Fiche → Devis → Bon pour facturation`, avec **des prix TVAC**, **une seule couche de règles côté serveur** utilisée à la fois par le site et par ChatGPT (via MCP), et une **transmission claire à la comptabilité** à deux moments : devis prêt à envoyer, puis bon pour facturation après l'événement.

---

## 2. Ce que fait le site aujourd'hui

Menu latéral (`app/frontend/src/pages/App.tsx`), chaque section est protégée par une permission :

| Section | URL | Permission | Rôle |
|---|---|---|---|
| Fiches | `/` | `reservations` | Liste des réservations à venir, rappels « plats manquants », création/édition de fiche, PDF |
| Passées | `/past` | `reservations` | Historique paginé |
| Rooftop | `/rooftop` | `rooftop` | Planning hebdomadaire des réservations Rooftop (société, contact, paiement, occasion) |
| Plaintes | `/incidents` | `incidents` | Rapports d'incident + remplissage par IA (OpenAI/Groq) + PDF |
| Salle | `/salle` | `floorplan` | Plan de salle, import du PDF de réservations, placement automatique, PDF annoté |
| Base de plats | `/menu` | `menu` | Catalogue des plats (nom, type, actif) — **sans prix** |
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
- **Auth du site** : PBKDF2-SHA256 (600 000 itérations), JWT HS256 de 8 h, rôles `admin`/`member` + permissions CSV.
- **Contrôle d'accès** : `API_PERMISSION_RULES` dans `main.py` ; une route non listée est refusée aux membres (bon choix « fermé par défaut »).
- **Migrations** : pas d'Alembic. `database.py` (870 lignes) ajoute les colonnes manquantes à chaque démarrage, et `run_startup_migrations()` **supprime les doublons de réservations** à chaque démarrage en production.
- **Déploiement** : `nixpacks.toml` (Railway) + deux `Dockerfile` + deux `Procfile` + deux `requirements.txt` à synchroniser à la main.
- **Tests** : 41 tests backend, aucun test frontend. Exécution le 22/10/2026 : **40 réussis, 1 échoué** (`test_empty_fiche_is_rejected`, voir §8).
- **Variables d'environnement** : `DATABASE_URL`/`PG*`, `JWT_SECRET`, `AUTH_TOKEN_TTL_HOURS`, `CORS_ORIGINS`, `TZ`, `PUBLIC_BASE_URL`, `GPT_API_KEY_HASH`, `MCP_*_TTL_SECONDS`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `OPENAI_*`, `GROQ_*`, `AI_PROVIDER`, `PDF_DIR`, `FINAL_STAMP_PATH`.

---

## 4. Modèle de données actuel

Défini dans `app/backend/models.py`.

| Table | Contenu | Remarques |
|---|---|---|
| `reservation` | client_name, pax, service_date, arrival_time, drink_formula, menu_formula, notes, status (draft/confirmed/printed), final_version, on_invoice, allergens (CSV), is_rooftop, company, contact, payment_method, special_requests, occasion | Unicité sur (date, heure, nom, pax). **Le client n'est qu'un texte.** |
| `reservationitem` | type (entrée/plat/dessert/supplément), name, quantity, comment | Nom recopié, **pas de lien vers le catalogue, pas de prix** |
| `menuitem` | name, type, active | Catalogue **sans prix** ni allergènes |
| `billinginfo` | 1:1 avec la réservation : société, adresse, CP, ville, pays, n° TVA, réf. PO, email, tél., conditions, notes | **Recopié à chaque réservation** |
| `supplementpreset` | name, default_quantity | Sans prix |
| `invoicesupplement` | description, quantity | **Table morte** (les suppléments sont dans `reservationitem`) |
| `reservationreminder` | snooze / mute des rappels | |
| `allergen` | clé, libellé, icône | Icônes aussi en fichiers |
| `user` | email, hash, rôle, permissions | |
| `setting` | clé/valeur (Zenchef, clients OAuth MCP) | |
| `gmailtoken` | refresh token Gmail | **En clair** |
| `note`, `incidentreport` | post-it, plaintes | |
| `drink`, `drinkstock`, `drinkvendor`, `supplier`, `purchaseorder`, `purchaseorderitem` | achats boissons | Seul endroit avec des prix (d'achat) |
| `floorplanbase`, `floorplaninstance` | plan de salle (JSON) | |
| `processedrequest` | idempotence Zenchef | |

---

## 5. Les fiches : règles métier existantes

Ces règles sont **le vrai capital du projet**. Elles vivent aujourd'hui à deux endroits : le formulaire React (`ReservationForm.tsx`) et la couche GPT (`gpt_api.py`).

Champs obligatoires : nom du client, couverts (1 à 500), date de service, heure d'arrivée.

Listes fermées :
- **Formule boissons** : `sans alcool` (défaut), `avec alcool`, `sans alcool + cava`, `avec alcool + cava`, `sans alcool + champ`, `avec alcool + champ`, `à la carte`, `sans Formule`.
- **Formule repas** : vide, `1 service`, `2 services`, `3 services`, `À la carte`, `Brunch`.
- **Types de ligne** : `entrée`, `plat`, `dessert`, `supplément`.
- **Allergènes** (14) : gluten, crustaces, oeufs, poisson, arachides, soja, lait, fruits_a_coque, celeri, moutarde, sesame, sulfites, lupin, mollusques (+ ceux ajoutés dans Paramètres).
- **Heures proposées** : 12:00, 12:30, 13:00, 13:30, 19:30, 20:00.

Règles :
1. **Les plats prévalent sur la formule** : s'il y a au moins une entrée/plat/dessert, la formule repas est vidée.
2. **Total par type ≤ couverts**.
3. **Brunch = buffet** : aucune entrée/plat/dessert, seulement des suppléments (Privatisation, Champagne, Planche apéro…).
4. **Au moins un plat ou une formule** (exigé par le formulaire — la couche GPT ne l'exige plus, contradiction §8).
5. **Noms de plats** repris avec l'orthographe du catalogue ; hors catalogue autorisé.
6. **Suppléments préservés** lors d'une mise à jour des plats sans suppléments.
7. **Statuts** : `draft` → `confirmed` → `printed` ; tampon **« Version finale »** sur le PDF. ChatGPT ne touche ni au statut ni au tampon.
8. **Toute modification remet à zéro** la date du dernier PDF (repère les fiches à réimprimer).
9. **Rappels** : fiche dans les 5 jours sans plat ni formule → rappel (reportable/masquable).
10. **Notes** : `**gras**`, `_italique_`, `[color=x]…[/color]`, lignes `- ` en puces.

PDF de fiche (`pdf_service.py`) :
- **Salle** : en-tête, couverts, formule, plats, suppléments, formule boissons (badge coloré), allergènes avec icônes, notes.
- **Cuisine** : sans boissons ni notes, décalée de 5 cm, **dupliquée s'il y a des desserts** (page pour la pâtisserie).
- Par défaut : salle + cuisine (+ cuisine bis), et la feuille de facturation ajoutée à la fin si elle existe.
- PDF du jour : toutes les fiches d'une date.

---

## 6. La facturation actuelle

- Coordonnées de facturation saisies **par réservation** (société, adresse, n° TVA, réf. PO, email, conditions « Paiement à 30 jours », pays « Belgique »).
- Le PDF s'intitule **« FEUILLE DE FACTURATION (INTERNE) »** : coordonnées, date, heure, pax, formule repas, formule boissons, suppléments **avec quantités seulement**, conditions, notes.
- **Absents** : tout prix, tout montant, tout total.

C'est déjà, dans l'esprit, un **document de transmission à la comptabilité** — ce qui correspond à la décision D2. Il lui manque l'essentiel : **les prix TVAC et le total**, un lien avec un **devis**, et la distinction entre *ce qui a été proposé* (devis) et *ce qui a été réellement servi* (bon pour facturation).

---

## 7. L'accès ChatGPT actuel

### 7.1 Action de Custom GPT — `/api/gpt`
- Sous-application FastAPI avec son propre schéma OpenAPI (`/api/gpt/openapi.json`).
- Authentification : **une seule clé statique** (hash dans `GPT_API_KEY_HASH`). Pas d'utilisateur identifié, pas de droits par action.
- Routes : lister/rechercher, lire, créer, modifier, ajouter/retirer un plat, dupliquer, **supprimer**, PDF fiche, facturation, PDF facturation, catalogue, Gmail (recherche, fil, message, brouillon).
- Bonnes idées à garder : listes de valeurs en `enum`, **normalisation des variantes** (« 3 Services », « 19h30 », « 17/09/2026 », « lactose » → `lait`), erreurs 422 qui listent les valeurs permises, création toujours en brouillon.

### 7.2 Serveur MCP — `/mcp`
- Pour les **connecteurs ChatGPT**. OAuth 2.1 + PKCE, enregistrement dynamique, connexion avec le compte du site, **réservé aux administrateurs**.
- 16 outils : `fiches_rechercher`, `fiche_lire`, `fiche_creer`, `fiche_modifier`, `fiche_item_ajouter`, `fiche_item_retirer`, `fiche_dupliquer`, `fiche_supprimer`, `menu_rechercher`, `facturation_lire`, `facturation_mettre_a_jour`, `gmail_rechercher`, `gmail_messages_client`, `gmail_lire_fil`, `gmail_lire_message`, `gmail_creer_brouillon`.
- Les outils réutilisent les fonctions de `gpt_api.py` (une seule logique : bien).

### 7.3 Instructions
`GPT_INSTRUCTIONS.md` contient des règles correctes mais courtes. Le serveur MCP n'envoie que 2 lignes d'instructions.

---

## 8. Problèmes constatés

### 8.1 Critiques (données, sécurité)
1. **Aucun prix** dans le catalogue ni sur les fiches : pas de devis possible.
2. **Pas d'entité client** : coordonnées ressaisies, aucun historique par client, doublons inévitables.
3. **Suppression des doublons à chaque démarrage** (`database.py`, `run_startup_migrations`) : deux réservations identiques sont effacées silencieusement à chaque redéploiement.
4. **ChatGPT peut supprimer des fiches** (`fiche_supprimer`, `DELETE /api/gpt/fiches/{id}`) sans garde-fou serveur.
5. **Clé API GPT unique et toute-puissante** : pas de traçabilité, pas de lecture seule, révocation globale.
6. **Aucun journal d'audit** (humain ou ChatGPT).
7. **Flux OAuth Gmail sans paramètre `state`** (`routers/gmail_oauth.py`) : n'importe qui peut relancer le flux et remplacer le compte Gmail relié.
8. **Jeton Gmail stocké en clair**.

### 8.2 Importants (bugs, incohérences)
9. **Règle « au moins un plat ou une formule » incohérente** entre le formulaire, la doc OpenAPI et le code GPT (`gpt_api.py:388-392`) → `test_empty_fiche_is_rejected` échoue.
10. **Texte entre `<` et `>` perdu dans les PDF** (pas d'échappement avant ReportLab). Vérifié : « Dupont & Fils <SA> » → « Dupont & Fils », « Steak <saignant> » → « Steak ».
11. **Noms de fichiers PDF non nettoyés** (`&`, `<`, `/`… du nom du client).
12. **Fonction PDF morte et cassée** : `generate_reservation_pdf()` utilise une variable `billing` inexistante.
13. **Duplication incomplète** : ni société, contact, occasion, demandes spéciales, Rooftop, ni « Sur facture ».
14. **Règles en double** et API interne permissive (formule libre, allergène inconnu, date vide → aujourd'hui, heure vide → 00:00, nom vide → « Client »).
15. **Zenchef** écrit `Sans alcool` (majuscule), hors liste.
16. **Rappels calculés en UTC** alors que « à venir/passées » utilise `TZ`.
17. **MCP** : plusieurs outils ne renvoient pas les erreurs lisibles ; pas d'outil pour les PDF.
18. **États OAuth MCP en mémoire** : perdus au redémarrage, incompatibles avec plusieurs workers.
19. **Performances** : `GET /api/reservations` charge tout + une requête par réservation (N+1).
20. **PDF sur disque éphémère**, jamais nettoyés, jamais figés.

### 8.3 Dette technique
21. Pas d'Alembic.
22. `pdf_service.py` : même bloc copié 6 fois.
23. Doublons de configuration (2 requirements, 2 Dockerfile, 2 Procfile, vite.config js/ts, tsbuildinfo versionnés, scripts de test à la racine).
24. JWT en `localStorage`, pas de limitation des tentatives de connexion, `/docs` publics.
25. `print()` partout, y compris des données de requêtes.
26. Code mort : `invoicesupplement`, `generate_reservation_pdf`, `listFloorBases`.

---

## 9. Ce qu'il faut garder, jeter, refaire

| Élément | Décision | Pourquoi |
|---|---|---|
| Listes de valeurs, alias, normalisation (`gpt_api.py`) | **Garder**, dans un module « règles » unique | Éprouvé avec ChatGPT |
| Règles des fiches (§5) | **Garder** (après validation §16) | C'est le métier |
| Rendu des notes + tests | **Garder** | Fonctionne |
| Contenu des PDF salle/cuisine | **Garder le contenu**, réécrire le code | Connu de la cuisine |
| Gmail lecture + brouillons | **Garder** pour lire les demandes clients (corriger `state`, chiffrer le jeton) | Utile pour remplir les fiches |
| MCP + OAuth | **Garder le principe**, réécrire | Bonne porte pour ChatGPT |
| Action Custom GPT à clé statique | **Supprimer** | Pas d'identité ni de droits |
| Auth, rôles/permissions | **Garder**, simplifier | |
| `billinginfo` par réservation | **Remplacer** par la fiche Client | |
| Feuille de facturation interne | **Remplacer** par **devis TVAC** + **bon pour facturation TVAC** | D1, D2, D3 |
| Catalogue sans prix | **Refaire** avec prix TVAC | D3 |
| Plan de salle, Rooftop, plaintes, boissons/achats, fournisseurs, notes | **Garder et améliorer** (D6, §13.4) | Utilisés au quotidien ; à rebrancher sur les clients et les fiches |
| Migrations maison, suppression auto des doublons | **Jeter** → Alembic | Risque de perte de données |

---

## 10. Cible : le parcours complet

```
 Demande du client (email, téléphone, Zenchef)
        │  ChatGPT lit l'email, propose la fiche ; l'équipe confirme
        ▼
 ① CLIENT  ── trouvé ou créé (coordonnées de facturation une seule fois)
        ▼
 ② FICHE (brouillon)  date · heure · couverts · formules · plats · allergènes · notes
        ▼
 ③ DEVIS (brouillon)  généré depuis la fiche, prix TVAC du catalogue, total TVAC
        │  l'équipe relit, ajuste, valide
        ▼
 ④ DEVIS « transmis à la compta »  ── la comptabilité l'envoie au client
        │  le client accepte (info remontée par la compta ou l'équipe)
        ▼
 ⑤ FICHE confirmée → finale → PDF salle / cuisine imprimés
        ▼
 ⑥ Événement réalisé : l'équipe saisit le réel (couverts réels, extras, boissons à la consommation)
        ▼
 ⑦ BON POUR FACTURATION (TVAC) « transmis à la compta » ── la compta facture et encaisse
```

Ce que l'outil **ne fait pas** : envoyer quoi que ce soit au client, numéroter des factures, calculer la TVA, suivre les paiements.

---

## 11. Cible : modèle de données

**Client** (`client`)
- type : `particulier` | `entreprise`
- nom / raison sociale, contact (prénom, nom), email, téléphone, langue (fr/nl/en)
- adresse de facturation (rue, n°, boîte, CP, ville, pays), n° TVA (texte, contrôle de format BE), référence de commande (PO) par défaut
- conditions de paiement par défaut, notes internes, allergies/préférences récurrentes
- archivé oui/non, dates de création/modification

**Fiche** (`fiche`) — remplace `reservation`
- client (obligatoire), contact sur place, téléphone sur place
- date, heure d'arrivée, couverts, espace (salle, City, Rooftop… *liste à valider*)
- **privatisation** : `aucune` | `semi-privatisation` | `privatisation complète` (prix au forfait, menu « Prix »)
- formule boissons, formule repas (listes actuelles + `Sharing`)
- allergènes (liste de clés), **notes salle** et **notes cuisine** séparées
- statut : `brouillon` → `confirmée` → `finale` → `réalisée` | `annulée` *(à valider)*
- `version` (verrou optimiste), date du dernier PDF imprimé

**Ligne de fiche** (`fiche_ligne`)
- type : entrée / plat / dessert / supplément
- lien catalogue (optionnel), libellé, quantité, commentaire

**Catalogue** (`produit`) — remplace `menuitem` et `supplementpreset`
- libellé, type (entrée, plat, dessert, formule repas, formule boissons, supplément, location), **prix TVAC en centimes**, unité (`par personne`, `pièce`, `forfait`, `bouteille`), allergènes contenus, actif
- les **formules** (1/2/3 services, Brunch, formules boissons) sont des produits « par personne »

**Devis** (`devis`)
- référence interne `D-2026-0001` (simple compteur, aucune contrainte légale), **version** (v1, v2… quand le client demande un changement)
- client et fiche liés ; **coordonnées du client figées** au moment de la transmission
- date de création, **date de validité**, couverts prévus
- lignes : libellé, quantité, unité, **prix unitaire TVAC figé**, total ligne TVAC
- **total TVAC**, remarques pour le client, remarques pour la compta (pas d'acompte, pas de remise : D4)
- statut : `brouillon` → `validé` → `transmis` → `accepté` | `refusé` | `remplacé` (par une nouvelle version) | `expiré`
- PDF stocké à la transmission (ne change plus ensuite)

**Bon pour facturation** (`bon_facturation`)
- lié au devis accepté et à la fiche
- **réel** : couverts réels, lignes réellement servies (reprises du devis, modifiables), extras ajoutés, boissons à la consommation
- total TVAC, écart avec le devis mis en évidence
- statut : `brouillon` → `validé` → `transmis` ; PDF stocké à la transmission

**Transmission** (`transmission`) : historique de ce qui a été envoyé à la compta (document, version, date, par qui, canal).

**Journal d'audit** (`audit`) : utilisateur, canal (`site` | `chatgpt`), action, objet, avant/après, date.

**Utilisateur** : comme aujourd'hui, plus un rôle **`compta`** (D5) qui voit seulement les devis transmis et les bons pour facturation.

---

## 12. Cible : devis et transmission à la comptabilité

### 12.1 Prix et montants (D3)
- **Tous les prix sont TVAC.** Le catalogue stocke un prix TVAC en centimes entiers.
- Total d'une ligne = quantité × prix unitaire TVAC ; total du document = somme des lignes. Calcul **uniquement côté serveur**, en centimes, sans arrondi intermédiaire.
- Aucun taux de TVA, aucune colonne HTVA, aucune ventilation : les documents portent la mention **« Prix TVA comprise »**.
- Le prix est **copié dans le devis** au moment où la ligne est ajoutée : modifier le catalogue ne change pas un devis existant.
- Une ligne peut avoir un **prix manuel** saisi par l'équipe dans le site (cas particulier, négociation) ; il est signalé « prix manuel » dans le devis et dans l'audit. ChatGPT ne peut pas en saisir.
- **Pas de remise ni d'acompte** (D4) : aucune ligne négative, aucun montant à payer d'avance.
- Si un produit est donné **hors TVA** (cas de la planche apéro, §12.3), il est converti **une seule fois** en TVAC à son entrée dans le catalogue ; tous les documents restent en TVAC.

### 12.2 Du formulaire au devis
- Générer le devis depuis la fiche :
  - **formule repas × couverts**. Si la fiche liste des plats (la formule est alors vidée, règle « les plats prévalent »), le serveur **déduit la formule** des types de plats, comme le fait déjà le PDF actuel (`_deduce_formula`) : entrée + plat + dessert → `3 services` ; entrée + plat ou plat + dessert → `2 services` ; plat seul → `1 service`. Les plats choisis servent à la cuisine, le prix vient de la formule ;
  - formule `À la carte` : **chaque plat × sa quantité × son prix de la carte** (pas de prix par personne). **Ajustement de la règle « les plats prévalent »** : elle ne vide plus que les formules `1/2/3 services` ; `À la carte` et `Sharing` restent sur la fiche à côté des plats ;
  - **formule boissons × couverts**, en deux lignes quand elle comprend une coupe (ex. « Formule avec alcool » + « Coupe de cava ») ;
  - **suppléments** × quantité (planche apéro par personne, coupes…) ;
  - **privatisation** au forfait selon le choix de la fiche : semi-privatisation ou privatisation complète de l'espace.
- Une fiche modifiée après la transmission de son devis affiche **« Devis à mettre à jour »** (écart couverts, plats, formules).
- Un devis transmis ne se modifie plus : on crée une **nouvelle version** (l'ancienne passe en `remplacé`).

### 12.3 Grille de prix initiale (D7)

Prix fournis le 22/10/2026, **TVA comprise** sauf mention contraire.

| Produit | Type | Unité | Prix TVAC |
|---|---|---|---|
| 1 service | formule repas | par personne | 28,00 € |
| 2 services | formule repas | par personne | 32,00 € |
| 3 services | formule repas | par personne | 40,00 € |
| Sharing | formule repas | par personne | 32,00 € |
| Brunch | formule repas | par personne | 36,00 € |
| À la carte | formule repas | — | prix de chaque plat de la carte (menu « Prix ») |
| Formule avec alcool | formule boissons | par personne | 20,00 € |
| Formule sans alcool | formule boissons | par personne | 10,00 € |
| Coupe de cava | supplément / complément de formule | par personne | 6,00 € |
| Coupe de champagne | supplément / complément de formule | par personne | 11,00 € |
| Privatisation City — 600 € donné sans préciser : semi ou complète ? | location | forfait | 600,00 € |
| Semi-privatisation (par espace) | location | forfait | à compléter dans le menu « Prix » |
| Privatisation complète (par espace) | location | forfait | à compléter dans le menu « Prix » |
| Planche apéro | supplément | par personne | donné 3,85 € HTVA → **prix TVAC à saisir** dans le menu « Prix » |

Formules boissons de la fiche → lignes du devis (**confirmé**) :

| Formule boissons (fiche) | Lignes du devis | Total par personne |
|---|---|---|
| `sans alcool` | Formule sans alcool | 10,00 € |
| `avec alcool` | Formule avec alcool | 20,00 € |
| `sans alcool + cava` | Formule sans alcool + Coupe de cava | 16,00 € |
| `avec alcool + cava` | Formule avec alcool + Coupe de cava | 26,00 € |
| `sans alcool + champ` | Formule sans alcool + Coupe de champagne | 21,00 € |
| `avec alcool + champ` | Formule avec alcool + Coupe de champagne | 31,00 € |
| `à la carte` | aucune ligne au devis ; consommations au bon pour facturation | — |
| `sans Formule` | aucune ligne | — |

Exemple : 20 couverts, 3 services, formule `avec alcool + cava`, privatisation City
= 20 × 40,00 + 20 × 20,00 + 20 × 6,00 + 600,00 = **1 920,00 € TVA comprise**.

À compléter dans le menu « Prix » (§13.5) : prix de chaque plat de la carte (pour « À la carte »), planche apéro en TVAC, privatisation des autres espaces, autres suppléments de la bibliothèque actuelle. Tant qu'un prix manque, le devis reste en brouillon avec l'alerte « prix manquant ».

### 12.4 Transmission à la comptabilité (D2)
Deux documents seulement partent vers la compta :
1. **Devis transmis** → la compta l'envoie au client.
2. **Bon pour facturation** après l'événement → la compta établit la facture.

Canal de transmission (D5) : la compta a un **compte « compta »** dans l'outil. Elle voit la liste « À envoyer » (devis) et « À facturer » (bons), télécharge les PDF, et marque « envoyé au client » ou « facturé ». Aucun email n'est envoyé par l'outil.

Contenu de chaque transmission : PDF, coordonnées de facturation du client, n° TVA et référence PO éventuels, conditions de paiement, remarques pour la compta.

### 12.5 Statuts côté compta
- Devis : `transmis` → `envoyé au client` (par la compta) → `accepté` / `refusé`.
- Bon pour facturation : `transmis` → `facturé` (la compta peut noter son n° de facture, pour retrouver le lien).

---

## 13. Cible : écrans, PDF, technique

### 13.1 Écrans
1. **Tableau de bord** : fiches des 7 prochains jours ; rappels (plats manquants, devis à mettre à jour, devis sans réponse, événements passés sans bon pour facturation).
2. **Clients** : recherche, fiche client avec historique des fiches, devis et bons.
3. **Fiches** : liste/agenda, formulaire (règles validées par le serveur), PDF salle/cuisine/jour.
4. **Devis** : générer depuis une fiche, ajuster, valider, transmettre, nouvelle version.
5. **Bons pour facturation** : saisir le réel après l'événement, valider, transmettre.
6. **Espace compta** : « À envoyer », « À facturer », historique.
7. **Prix** et **Formules** : deux menus pour compléter et modifier les prix et les formules soi-même (§13.5).
8. **Paramètres** : identité du restaurant (nom, adresse, logo, coordonnées compta), mentions par défaut des devis, validité par défaut, allergènes, utilisateurs, connexions ChatGPT et Gmail.
9. **Journal** : qui a fait quoi (y compris ChatGPT).
10. **Modules conservés** (§13.4) : Salle, Rooftop, Plaintes, Commandes/Achats, Fournisseurs, Notes.

### 13.2 PDF
Un seul moteur de gabarits avec composants partagés (ReportLab réorganisé, ou HTML → PDF avec WeasyPrint) :
- **Fiche salle**, **fiche cuisine** (+ page dessert), **récapitulatif du jour** : contenu actuel conservé.
- **Devis** : logo, coordonnées du restaurant, client, référence et version, date et validité, détail de l'événement (date, heure, couverts), lignes (libellé, quantité, prix unitaire TVAC, total), **total TVAC**, « Prix TVA comprise », remarques, conditions.
- **Bon pour facturation** : mêmes informations + réel servi + écart avec le devis + référence du devis.
- Tout texte utilisateur échappé (corrige §8 n° 10) ; noms de fichiers nettoyés (§8 n° 11).
- PDF de devis et de bons **stockés** à la transmission (stockage objet ou base).

### 13.3 Technique
- Garder **FastAPI + SQLAlchemy/SQLModel + PostgreSQL + React/Vite/Tailwind** sur Railway.
- **Alembic** ; plus aucune modification de schéma au démarrage.
- Un seul `Dockerfile`, un seul fichier de dépendances, CI GitHub Actions (tests + build).
- Découpage : `domain/` (règles pures et calculs, testés), `services/`, `api/` (REST du site), `mcp/` (ChatGPT), `pdf/`, `integrations/` (Gmail, Zenchef).
- Session en cookie `HttpOnly`, limitation des tentatives de connexion, logs sans données personnelles.

---

### 13.4 Modules conservés (D6)

Principe : chaque module garde ce qu'il fait aujourd'hui, mais **lit les mêmes clients et fiches** au lieu de sa propre copie, et passe par les mêmes règles, le même audit et le même moteur PDF.

**Rooftop**
- Aujourd'hui : planning hebdomadaire de réservations marquées `is_rooftop`, avec des statuts renommés (Option / Confirmée / Terminée), sans plats chargés dans la liste.
- Cible : une fiche ordinaire avec `espace = Rooftop`. Le planning hebdomadaire devient une **vue agenda filtrée** ; les fiches Rooftop ont client, devis et bon pour facturation comme les autres. Mêmes statuts que les fiches (« Option » peut rester le libellé affiché pour `brouillon`).

**Plan de salle**
- Aujourd'hui : les réservations du service sont importées d'un PDF et stockées **à part** dans le plan (JSON), sans lien avec les fiches ; placement automatique ; PDF annoté ; `floorplan.py` fait 2 368 lignes avec un journal de débogage en mémoire.
- Cible : le plan d'un service charge **les fiches du jour** (groupes) + l'import PDF/Zenchef pour les petites tables ; la table affectée à une fiche s'affiche sur la fiche salle. Le code est découpé (géométrie, placement automatique, PDF, API), le placement automatique est couvert par des tests (le script `test_auto_assign.py` existe déjà à la racine), et le journal de débogage est remplacé par des logs normaux.

**Plaintes**
- Aujourd'hui : rapport d'incident + remplissage par IA via une clé OpenAI/Groq sur le serveur ; PDF.
- Cible : rapport **rattaché au client et à la fiche** concernés ; remplissage proposé par **ChatGPT via le connecteur** (outil `plainte_preparer`, en brouillon), ce qui permet de retirer la clé OpenAI/Groq du serveur ; PDF avec texte échappé ; statut `ouverte` / `traitée`.

**Commandes de boissons, achats, fournisseurs**
- Aujourd'hui : boissons, stock min/max, calcul de réassort, bons de commande, export CSV, prix d'achat par fournisseur.
- Cible : même fonctionnement, plus un bon de commande en PDF, des statuts `brouillon` → `envoyé` → `reçu` et un historique par fournisseur. Les prix d'achat restent **séparés** des prix de vente du catalogue. ChatGPT peut **préparer** un bon de commande en brouillon (`achat_preparer`) ; l'envoi au fournisseur reste humain.

**Notes (post-it)**
- Gardées telles quelles, avec auteur et date.

**Zenchef**
- Synchronisation conservée ; une réservation importée cherche ou crée le client correspondant et prend la formule boissons exactement dans la liste (corrige `Sans alcool`, §8 n° 15).

### 13.5 Menus « Prix » et « Formules » (D8)

Deux entrées dans le menu latéral, réservées aux rôles `admin` (et `prix` si vous voulez donner ce droit à quelqu'un d'autre). Toute modification est enregistrée dans le journal (qui, quand, ancien prix → nouveau prix).

**Menu « Prix »** — tout ce qui se vend, au même endroit
- Une seule liste avec des onglets : *Formules repas*, *Formules boissons*, *Plats de la carte* (entrées, plats, desserts), *Suppléments*, *Privatisations*.
- Chaque ligne : nom, unité (`par personne`, `pièce`, `forfait`, `bouteille`), **prix TVA comprise** modifiable directement dans la liste, actif oui/non.
- Filtre **« Prix manquants »** en haut, avec un compteur rouge dans le menu latéral tant qu'il en reste (ex. « Prix 12 »). Au démarrage, il contiendra : les plats de la carte actuelle, la planche apéro, les autres privatisations, les suppléments de la bibliothèque actuelle.
- Bouton **« Ajouter »** pour un nouveau plat, supplément ou espace à privatiser.
- Saisie en euros avec virgule (`4,31`), stockée en centimes ; un prix vide = « prix manquant », un prix à 0 = gratuit (confirmé à la saisie).
- Changer un prix ne modifie **pas** les devis déjà préparés : seuls les nouveaux devis et les devis en brouillon recalculés prennent le nouveau prix.
- Un lien « Compléter le prix » apparaît sur chaque devis bloqué par un prix manquant et mène directement à la bonne ligne.

**Menu « Formules »** — ce qu'on choisit sur une fiche
- **Formules repas** : nom, prix par personne (ou « prix de la carte » pour À la carte), types de plats qu'elle couvre (ex. `2 services` = 2 types parmi entrée / plat / dessert ; `Brunch` = aucun plat, suppléments seulement), ordre d'affichage, active oui/non.
- **Formules boissons** : nom, **formule de base** (avec alcool / sans alcool / aucune) + **coupe** éventuelle (cava, champagne, aucune). Le prix par personne s'affiche automatiquement à partir du menu « Prix » (ex. avec alcool + cava = 20,00 + 6,00 = 26,00 €), il n'est pas retapé.
- Les listes déroulantes de la fiche, les règles du serveur et ce que ChatGPT lit (`references_lister`) viennent **de ce menu** : une formule ajoutée ou désactivée ici l'est partout, sans développeur.
- Une formule utilisée par des fiches existantes ne se supprime pas : on la **désactive** (elle disparaît des choix, les anciennes fiches la gardent).
- Le badge coloré des formules boissons sur la fiche salle (couleurs actuelles) se choisit ici pour les nouvelles formules.

## 14. Cible : l'accès ChatGPT

### 14.1 Canal
**Serveur MCP unique** (`/mcp`), branché dans ChatGPT comme connecteur. L'Action à clé statique est supprimée.

### 14.2 Authentification
OAuth 2.1 + PKCE avec le compte du site ; codes et états en base ; jetons révocables ; chaque appel est fait **au nom de l'utilisateur** et soumis à **ses** permissions.

### 14.3 Droits (scopes)
| Scope | Permet |
|---|---|
| `lecture` | rechercher/lire clients, fiches, catalogue, devis, bons |
| `fiches:ecrire` | créer/modifier clients et fiches (hors fiches finales) |
| `devis:preparer` | créer/modifier des devis et bons **en brouillon** |
| `gmail:lire` | lire les emails clients pour remplir les fiches |
| `plaintes:preparer` | rédiger un rapport de plainte en brouillon |
| `achats:preparer` | préparer un bon de commande fournisseur en brouillon |
| `salle:lire` | lire le plan de salle d'un service (tables affectées) |

**Jamais accordé à ChatGPT** : valider ou transmettre un devis ou un bon à la compta, saisir un prix manuel, modifier le catalogue, supprimer quoi que ce soit, passer une fiche en `finale`, envoyer un email (même un brouillon au client : c'est la compta qui écrit au client).

### 14.4 Garde-fous côté serveur
1. Même validation que le site (module de règles unique).
2. Annulation plutôt que suppression, en deux temps (aperçu + jeton de confirmation).
3. Verrou de version (409 si la fiche a changé entre-temps).
4. Clé d'idempotence sur les créations.
5. Fiches `finale`/`réalisée`/`annulée` et devis non brouillon : non modifiables par ChatGPT.
6. Montants toujours calculés et renvoyés par le serveur.
7. Audit de chaque appel.
8. Erreurs lisibles : `{ok: false, erreur: {code, message, valeurs_permises}}`.
9. Annotations MCP (`readOnlyHint`, `destructiveHint`).

Détail des outils et consignes : [`REGLES_CHATGPT.md`](./REGLES_CHATGPT.md).

---

## 15. Plan de réalisation

| Étape | Contenu | Résultat |
|---|---|---|
| 0. Décisions | Répondre aux questions §16 ; valider les règles §5 ; compléter la grille de prix §12.3 | Spécification figée |
| 1. Socle | Nouveau squelette, Alembic, auth, audit, CI, un seul Dockerfile | Projet vide qui se déploie |
| 2. Clients + catalogue | Modèles, écrans, import des clients depuis `billinginfo`, saisie des prix TVAC | Clients réutilisables, catalogue chiffré |
| 3. Fiches | Règles §5 dans `domain/`, écrans, PDF salle/cuisine/jour, migration des réservations | Parité avec l'actuel |
| 4. Devis | Génération depuis la fiche, versions, PDF, validation, transmission | Devis TVAC prêts pour la compta |
| 5. Bons pour facturation | Saisie du réel, écart avec le devis, PDF, transmission ; espace compta | Boucle complète jusqu'à la compta |
| 5 bis. Modules conservés | Rooftop dans les fiches, plan de salle branché sur les fiches, plaintes, achats, notes, Zenchef (§13.4) | Tous les modules dans la nouvelle version |
| 6. ChatGPT | Serveur MCP (scopes, confirmations, audit), consignes, tests de scénarios | ChatGPT opérationnel et encadré |
| 7. Bascule | Migration des données de production, double fonctionnement, arrêt de l'ancien | Ancien site retiré |

Migration des données existantes :
- `billinginfo` → `client` (dédoublonnage par n° TVA, puis par nom de société normalisé) ; `reservation.client_name/company/contact` → rattachement au client.
- `reservation` + `reservationitem` → `fiche` + `fiche_ligne`.
- `menuitem` + `supplementpreset` → `produit`, avec la grille §12.3 (prix manquants à compléter avant la mise en service des devis).
- Réservations Rooftop → `fiche` avec `espace = Rooftop` ; plans de salle, plaintes, boissons, fournisseurs, bons de commande et notes repris tels quels.
- Les anciennes feuilles de facturation ne sont pas reprises comme devis (pas de montants).

---

## 16. Questions encore ouvertes

Réglées : ~~émission des factures~~ (D1), ~~envoi aux clients~~ (D2), ~~TVA~~ (D3), ~~remises et acomptes~~ (D4), ~~canal de transmission à la compta~~ (D5), ~~périmètre~~ (D6), ~~grille de prix~~ (D7), ~~gestion des prix et formules~~ (D8).

1. **Sharing** : les plats à partager sont-ils listés sur la fiche (formule gardée à côté des plats, comme À la carte) ?
2. **Privatisation** : deux formules, semi-privatisation et privatisation complète. Les 600 € de « City » correspondent à laquelle ? « City » est-il un espace (et lesquels d'autre : Rooftop, salle…) ?
3. **Prix manuels** : en plus du menu « Prix », l'équipe peut-elle changer le prix d'une seule ligne sur un devis précis (cas particulier), ou jamais ?
4. **Validité d'un devis** : combien de jours par défaut ?
5. **Acceptation du devis** : qui l'indique dans l'outil (la compta ou l'équipe) ?
6. **Statuts de fiche** : garder Brouillon/Confirmée/Imprimée, ou passer à Brouillon/Confirmée/Finale/Réalisée/Annulée ?
7. **Règle « au moins un plat ou une formule »** : dès la création, ou seulement pour confirmer ?
8. **ChatGPT** : utilisé par les admins seulement, ou aussi par le personnel ? Peut-il préparer des devis, ou seulement des fiches ?
9. **Langues** des devis : FR seulement, ou aussi NL/EN ?
10. **Zenchef** : garder le seuil actuel (groupes de plus de 10 personnes) pour l’import automatique ?
