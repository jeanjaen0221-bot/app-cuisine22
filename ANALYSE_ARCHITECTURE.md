# ANALYSE COMPLÈTE DE L'ARCHITECTURE - Restaurant Albert Brussels

## Date d'analyse
10 août 2026 — révision complète après audit et correctifs.

> Cette révision remplace l'analyse du 3 février 2026, dont la section « Problèmes
> identifiés » était devenue entièrement obsolète (dépendances signalées comme
> manquantes qui étaient présentes, endpoint `/templates` qui n'est plus appelé,
> fonction morte déjà supprimée). Voir §6 pour l'état réel.

---

## 1. CONTEXTE MÉTIER

### Restaurant Albert Brussels
- **Type**: Restaurant avec service de brunch/déjeuner et dîner, plus un espace Rooftop
- **Problématique**: Gestion optimale du plan de salle pour maximiser l'occupation
- **Contraintes**:
  - Tables fixes agençables (4 pax chacune, stock de chaises limité — 28 par défaut)
  - Tables rectangulaires (6 pax de base, extensibles à 8 avec rallonge)
  - Tables rondes (10 pax, dernier recours car moins pratiques)
  - PDF de réservations reçu dans un format tabulaire fixe

L'application couvre aujourd'hui bien plus que le plan de salle : fiches cuisine,
facturation, plaintes clients, commandes boissons, fournisseurs et gestion des comptes.

---

## 2. ARCHITECTURE TECHNIQUE

### 2.1 Stack Technologique

**Backend (Python 3.11+)**
- FastAPI 0.115.2 / uvicorn 0.30.6
- SQLModel 0.0.22 / SQLAlchemy 2.0.36 / Pydantic 2.9.2
- PyJWT 2.10.1 (jetons de session)
- ReportLab 4.2.5 (génération PDF)
- pdfplumber 0.11.4 (extraction de tableaux PDF — **et non pdfminer**)
- pypdf 3.17.4 (fusion / annotation de PDF existants)
- Pillow 10.4.0 (normalisation des icônes allergènes)
- PostgreSQL (production) / SQLite (dev)

**Frontend (React + TypeScript)**
- React 18.3.1 / React Router DOM 6.26.2
- Axios 1.7.7, Lucide React 0.441.0
- TailwindCSS 3.4.14 + `styles.css` (~3 100 lignes de CSS applicatif)
- Vite 7.1.12, TypeScript 5.6 (mode `strict`)

**Déploiement**
- Railway (PostgreSQL) via `nixpacks.toml`, ou Docker via le `Dockerfile` racine
- Le `Dockerfile` racine construit le frontend puis sert le tout depuis FastAPI
- Migrations idempotentes appliquées automatiquement au démarrage

> ⚠️ Il existe **deux** fichiers de dépendances (`requirements.txt` à la racine et
> `app/backend/requirements.txt`) et **deux** `Procfile`/`Dockerfile`. Ils doivent
> rester synchronisés : une désynchronisation avait fait disparaître PyJWT du
> fichier racine, ce qui faisait planter au démarrage tout déploiement basé dessus.

### 2.2 Volumétrie du code

| Fichier | Lignes |
|---|---|
| `backend/routers/floorplan.py` | 2 323 |
| `backend/pdf_service.py` | 1 274 |
| `backend/database.py` | 872 |
| `backend/models.py` | 689 |
| `backend/routers/reservations.py` | 587 |
| `frontend/src/components/FloorCanvas.tsx` | 1 796 |
| `frontend/src/components/ReservationForm.tsx` | 1 291 |
| `frontend/src/pages/FloorPlanPage.tsx` | 789 |

`floorplan.py` et `FloorCanvas.tsx` concentrent l'essentiel de la complexité et
mériteraient d'être découpés (voir §7).

### 2.3 Structure Base de Données

**Authentification & accès**
1. `user` — `id`, `email` (unique), `password_hash`, `role`, `permissions` (CSV), `created_at`, `last_login_at`

**Réservations & cuisine**
2. `reservation` — `client_name`, `pax`, `service_date`, `arrival_time`, `drink_formula`,
   `menu_formula`, `notes`, `status`, `allergens`, `final_version`, `on_invoice`,
   `last_pdf_exported_at`, plus les champs Rooftop (`is_rooftop`, `company`, `contact`,
   `payment_method`, `special_requests`, `occasion`)
   - UNIQUE (`service_date`, `arrival_time`, `client_name`, `pax`)
   - CHECK `pax >= 1`, index (`service_date`, `arrival_time`)
3. `reservationitem` — lignes de la fiche (`type` = entrée/plat/dessert/**supplément**, `name`, `quantity`, `comment`)
4. `reservationreminder` — état snooze/mute des rappels « plats manquants »
5. `menuitem` — base de plats réutilisables

**Facturation**
6. `billinginfo` — 1:1 avec la réservation (PK = `reservation_id`)
7. `supplementpreset` — bibliothèque de suppléments réutilisables
8. `invoicesupplement` — **table héritée**, vidée au démarrage vers `reservationitem`

**Boissons & achats**
9. `drink`, `drinkstock`, `drinkvendor`, `supplier`, `purchaseorder`, `purchaseorderitem`

**Plan de salle**
10. `floorplanbase` — plan maître (`data` JSON)
11. `floorplaninstance` — instance de service : `service_date`, `service_label`,
    `template_id` (FK), `data`, `assignments`, `reservations` (JSON)
    - UNIQUE (`service_date`, `service_label`)

**Divers**
12. `incidentreport`, `note`, `allergen` (avec `icon_bytes`), `setting`, `processedrequest`

**Note importante**: le système floorplan reste **indépendant** de la table
`reservation`. L'import PDF ne crée jamais de réservation ; les données parsées
vivent dans `floorplaninstance.reservations`.

---

## 3. AUTHENTIFICATION & CONTRÔLE D'ACCÈS

Ajouté après l'analyse initiale, ce module n'y figurait pas.

### 3.1 Mécanisme
- Mots de passe : PBKDF2-HMAC-SHA256, **600 000 itérations**, sel de 16 octets,
  comparaison en temps constant. Minimum 12 caractères.
- Sessions : JWT HS256, TTL 8 h (`AUTH_TOKEN_TTL_HOURS`), signé avec `JWT_SECRET`.
- Premier démarrage : `/api/auth/status` signale `setup_required`, et `/api/auth/setup`
  crée le compte propriétaire (refusé si un compte existe déjà).

> ⚠️ **`JWT_SECRET` est obligatoire en production.** À défaut, un secret aléatoire
> est généré par processus : les sessions sautent à chaque redémarrage et échouent
> de façon erratique avec plusieurs workers uvicorn. Un avertissement est désormais
> affiché au démarrage.

### 3.2 Autorisation
Un middleware HTTP protège **toute** route `/api/` sauf `/api/auth/*`, qui est géré
par le routeur lui-même (`setup`/`login` publics, `require_admin` sur la gestion des
comptes). Les comptes `admin` passent partout ; les comptes `member` doivent posséder
l'une des permissions acceptées par la règle qui couvre la requête.

Les règles sont une **liste ordonnée** de `(motif d'URL, permissions acceptées,
méthodes couvertes)` — `API_PERMISSION_RULES` dans `main.py`. La première règle dont
le motif **et** la méthode correspondent l'emporte, donc les entrées les plus
spécifiques viennent en premier. Une URL que personne ne couvre est refusée aux
membres : une nouvelle route est fermée par défaut, jamais ouverte par oubli.

| Permission | Périmètre |
|---|---|
| `dashboard` | `/api/notes` (widget de notes) |
| `reservations` | `/api/reservations`, `/api/reminders`, lecture des suppléments |
| `rooftop` | `/api/reservations/rooftop` |
| `floorplan` | `/api/floorplan` |
| `menu` | `/api/menu-items` |
| `orders` | `/api/drinks`, `/api/purchase-orders` |
| `suppliers` | `/api/suppliers` |
| `billing` | `/api/supplement-presets`, `/api/reservations/{id}/{billing,supplements,invoice-pdf}`, plus la **lecture seule** de la liste des réservations |
| `incidents` | `/api/incidents` |
| `settings` | `/api/zenchef`, `/api/allergens` |
| `users` | réservé aux admins (`require_admin`) |

Deux recouvrements sont volontaires, parce que l'interface les impose :

- **`billing` lit `/api/reservations`** (en `GET` seulement) : la page Facturation
  liste les réservations pour choisir laquelle facturer. Les écritures sur les fiches
  lui restent interdites.
- **`reservations` lit `/api/supplement-presets` et les suppléments** : `BillingPanel`
  est embarqué dans l'écran de fiche autant que dans la page Facturation. L'édition de
  la bibliothèque de presets reste réservée à `billing`.

> ⚠️ Attention en ajoutant un routeur : **la permission se déduit de l'URL, pas du
> nom du fichier.** Le routeur `facturation.py` publie ses routes sous
> `/api/supplement-presets` et `/api/reservations/…`, et non sous `/api/facturation`.
> C'est précisément ce décalage qui avait rendu la permission `billing` totalement
> inopérante (voir §6.1).

Côté frontend, **chaque route React applique le même contrôle** que la barre
latérale : masquer un lien de navigation n'est pas un contrôle d'accès, puisque
l'URL reste saisissable. Une page « Accès refusé » est affichée sinon.

---

## 4. LOGIQUE MÉTIER — PLAN DE SALLE

### 4.1 Workflow Complet

```
1. CRÉATION PLAN DE BASE
   - Dimensions salle (room.width, room.height, room.grid)
   - Murs (walls), colonnes (columns), zones interdites (no_go)
   - Fixtures / décorations
   - Tables fixes, rectangulaires, rondes
   - Zones spécialisées: round_only_zones (R), rect_only_zones (T)
   - Réglages: fixed_chair_stock, max_dynamic_tables, large_table_config

2. IMPORT PDF RÉSERVATIONS
   - Extraction des tableaux avec pdfplumber (extract_tables)
   - Détection des colonnes heure / pax / nom par position
   - Nettoyage des noms (téléphones, statuts, sources)
   - IDs déterministes (MD5 du contenu) pour la stabilité import/export
   - Stockage dans floorplaninstance.reservations

3. AUTO-ATTRIBUTION DES TABLES
   - Calcul du taux de charge → choix du mode de placement
   - Pré-passe des petits groupes sur la zone fixe
   - Placement par priorités (voir 4.2)
   - Création dynamique de tables si nécessaire
   - Stockage dans floorplaninstance.assignments + liste d'alertes

4. NUMÉROTATION
   - Tables fixes : 1, 2, 3… N
   - Tables rectangulaires : T1, T2, T3… TN
   - Tables rondes : R1, R2, R3… RN
   - Canapés : C1… CN — Mange-debout : D1… DN
   - Ordre : column-major (x croissant, y décroissant)

5. EXPORT PDF
   - PDF annoté : PDF original + numéros de table (pypdf)
   - PDF complet : liste service + plan numéroté + liste des tables (ReportLab)
```

### 4.2 Algorithme Auto-Assign

**Fonction**: `_auto_assign(plan_data, reservations)` (`floorplan.py`)

L'algorithme a nettement dépassé le simple « glouton à 8 priorités » décrit dans
l'analyse initiale. Il est désormais **sensible à la charge du service**.

**Mode de placement** — calculé à partir du ratio couverts / capacité approximative :

| `load_ratio` | Mode | Comportement |
|---|---|---|
| < 0,55 | `aerer` | Écarte les convives : privilégie les tables plus grandes, autorise 2 rectangles collés pour 9–14 pax |
| 0,55 – 0,75 | `normal` | Best-fit classique |
| > 0,75 | `optimiser` | Minimise le gaspillage de places |

**Paramètres du plan** (avec valeurs par défaut) :
- `fixed_chair_stock` = 28 — plafond de chaises sur la zone fixe
- `max_dynamic_tables` = `{rect: 10, round: 5}` — plafond de créations dynamiques
- `large_table_config.pax_threshold_right` = 10 — au-delà, grande table dans la zone T
- `large_table_config.pax_threshold_vertical` = 20 — au-delà, table en portrait
- `large_table_config.vertical_span_max` = 7 — nombre max de segments verticaux

**Ordre de traitement** :
1. **Pré-passe** : tous les groupes de 1–4 pax remplissent d'abord la zone fixe,
   dans la limite de `fixed_chair_stock`.
2. Le reste est trié par `pax` décroissant puis `arrival_time` croissant.
3. Pour chaque réservation :
   - **Grands groupes** (> seuils) → création anticipée d'une grande table
     dynamique dans la zone T (horizontale, ou verticale au-delà du seuil portrait)
   - **Table fixe** best-fit (≤ 4 pax, si le stock de chaises le permet)
   - **Paire de rectangles collés** (mode `aerer`, 9–14 pax)
   - **Rectangle simple** best-fit, extension +2 jusqu'à 8 en dernier recours ;
     les rectangles surdimensionnés sont écartés pour les petits groupes
   - **Grande rect dynamique** (repli)
   - **Places debout**, puis **table ronde** (marquée `last_resort`), puis **sofa**
   - Les groupes ≤ 4 ne débordent hors de la zone fixe que si celle-ci est saturée
4. Chaque échec ou compromis alimente une liste `alerts` renvoyée à l'interface.

**Gestion des zones spécialisées** : `_find_spot_for_table()` vérifie si la position
tombe dans une `round_only_zone` (R) ou une `rect_only_zone` (T) et restreint le
type de table créée en conséquence.

### 4.3 Deux invariants à respecter dans `floorplan.py`

Ces deux règles ne sont pas évidentes à la lecture et leur violation ne produit
aucune erreur — seulement un comportement faux. Les deux ont été enfreintes.

**a) Toute mutation d'une colonne JSON doit être signalée.**
`row.data = plan` ne déclenche rien côté SQLAlchemy lorsque `plan` **est** déjà
l'objet porté par l'attribut, ce qui est le cas dès qu'un helper modifie le plan
sur place. L'écriture est alors abandonnée en silence, et le `session.refresh()`
qui suit recharge la version d'avant : l'endpoint renvoie donc le plan périmé
qu'il prétend avoir mis à jour. Utiliser `_persist_json(row, "data", …)` avant
chaque `commit`.

**b) La numérotation suit le *type*, jamais l'état de verrouillage.**
Verrouiller une table la retire du pool d'auto-attribution, mais une rectangulaire
verrouillée reste une rectangulaire et doit garder une étiquette `T`. Le canvas et
le générateur PDF filtrent tous deux les étiquettes par type (`T\d+` pour une
rect, `R\d+` pour une ronde…) : si la numérotation classe la table dans une autre
famille, l'étiquette est rejetée à l'affichage et **la table apparaît sans
numéro**. `_numbering_kind()` est la source unique de vérité, partagée par la
numérotation, le rendu PDF et `_capacity_for_table()`.

### 4.4 Parsing PDF (`POST /api/floorplan/import-pdf`)

Le parsing repose sur **`pdfplumber.extract_tables()`**, et non plus sur une
extraction de texte ligne à ligne :

1. Pour chaque page, extraction des tableaux
2. Pour chaque ligne, détection positionnelle des colonnes dans les 7 premières cellules :
   - `heure` via `^\d{1,2}:\d{2}$`
   - `pax` via `^\d{1,2}$` (après l'heure)
   - `nom` : première cellule d'au moins 2 caractères contenant une majuscule
3. Validation : `1 <= pax <= 30`, nom d'au moins 2 caractères
4. Nettoyage : première ligne seulement, coupe à « Téléphone », rejet des mots-clés
   (`commentaire`, `confirmé`, `web`, `google`, en-têtes)
5. ID déterministe : `MD5(service_date_heure_pax_nom)`
6. Erreur 400 explicite si aucune réservation n'est trouvée

---

## 5. FRONTEND

### 5.1 FloorCanvas.tsx (1 796 lignes)
- Canvas HTML5, interaction souris complète, zoom/pan à la molette
- Drag & drop, redimensionnement par poignées, menu contextuel (clic droit)
- Modes de dessin : zones interdites, zones R, zones T
- Détection de collision tables ↔ murs / colonnes / fixtures / no-go / autres tables,
  avec retour automatique à la position précédente si invalide
- Curseurs adaptatifs (`nwse-resize`, `ew-resize`, `context-menu`, `crosshair`, `move`)
- Menu contextuel rendu via un Portal React pour échapper à l'`overflow:hidden`

### 5.2 Client API (`lib/api.ts`)
- Instance Axios unique, jeton injecté par intercepteur depuis `localStorage`
- Intercepteur de réponse : normalise le message d'erreur dans `error.userMessage`
- Sur 401 (hors `/api/auth/`), purge le jeton et émet `auth:expired`, que `App.tsx`
  écoute pour revenir à l'écran de connexion

### 5.3 Routage et permissions
`App.tsx` masque les liens **et** protège chaque route. Une route attrape-tout
affiche « Page introuvable ». Le widget de notes n'est monté qu'avec la permission
`dashboard`.

---

## 6. ÉTAT DES PROBLÈMES

### 6.1 bis — Plan de salle, corrigés le 10 août 2026

| Gravité | Problème | Correctif |
|---|---|---|
| **Critique** | **La numérotation des tables n'était jamais enregistrée.** Les quatre endpoints `number-tables` et `renumber-tables` (base et instance) mutaient le plan sur place puis réassignaient la même référence : SQLAlchemy ne détectait rien, `session.refresh()` restaurait la version d'avant, et l'endpoint **renvoyait le plan non numéroté**. Numéroter puis recharger perdait tout le travail. | `_persist_json()` avant chaque commit |
| **Critique** | `auto-assign` renvoyait **500** dès qu'une réservation avait une heure vide, nulle ou malformée (`ValueError: Invalid isoformat string: ''`) — cas courant sur un PDF mal parsé, qui bloquait tout le service | `_parse_arrival_time()`, tolérant, avec valeur par défaut |
| Majeur | Une rectangulaire **verrouillée** recevait un numéro de la famille « fixe » (`7`), que le canvas *et* le PDF rejetaient ensuite car ils exigent `T\d+` pour une rect : **la table s'affichait sans numéro**. Une ronde verrouillée figurait dans deux familles et consommait un numéro fixe, créant un trou dans la séquence. | `_numbering_kind()`, source unique partagée |
| Majeur | Import PDF : si aucun service ne correspondait à la date/au libellé, les réservations lues étaient **jetées** et l'API répondait quand même « importées » | 404 explicite invitant à créer le service |
| Moyen | Une rect verrouillée sans capacité explicite comptait **4 places** côté moteur alors que l'éditeur affichait **6** : la salle était silencieusement sous-remplie | `_capacity_for_table()` aligné sur `_numbering_kind()` |
| Moyen | `FloorPlanPage.tsx` était corrompu en **mojibake** sur 25 lignes : l'interface affichait « Instance rÃ©initialisÃ©e », « Tables numÃ©rotÃ©es », « Service crÃ©Ã© »… | Ré-encodage UTF-8 des 25 lignes |
| Mineur | Tri des étiquettes purement alphabétique : `T10` passait avant `T2` dans le PDF et l'écran de comparaison | `_label_sort_key()` (tri naturel) |

### 6.1 Corrigés le 10 août 2026

| Gravité | Problème | Correctif |
|---|---|---|
| Critique | `database.py` n'importait pas `select` : `ensure_supplements_migrated()` levait un `NameError` avalé par un `except: pass`. **La migration des suppléments ne s'est jamais exécutée.** | Import ajouté |
| Critique | `ALTER TABLE … DEFAULT '{}'::text` est de la syntaxe PostgreSQL, invalide en SQLite : la colonne `floorplaninstance.reservations` n'était jamais créée en dev | Syntaxe SQLite corrigée |
| Critique | `requirements.txt` racine sans PyJWT alors que `security.py` fait `import jwt` : plantage au démarrage | PyJWT ajouté |
| Majeur | Le garde-fou « total par type ≤ couverts » interceptait sa propre `HTTPException` : sur un PUT, on pouvait enregistrer 5 plats pour 1 couvert sans erreur | `except HTTPException: raise` |
| Majeur | `POST /reservations/{id}/duplicate` recopiait le nom à l'identique → violation de l'unicité (date, heure, nom, pax) → erreur 500 | Suffixe « (copie) », « (copie 2) »… |
| Majeur | `str(None)` vaut `"None"` : une note vide était stockée et **imprimée sur les fiches et PDF sous la forme du mot « None »**. Un PUT `client_name: null` renommait le client en « None ». | Coalescence avant conversion |
| Majeur | La clé d'URL des allergènes servait de nom de fichier sans validation à l'upload d'icône et à la suppression (écriture hors du dossier prévu) | `_validate_key()` sur les 3 routes |
| Majeur | **La permission `billing` ne donnait accès à rien.** Le middleware mappait le préfixe `/api/facturation`, qui n'existe sur aucune route : un compte à qui l'admin accordait « Facturation » recevait 403 sur *tous* les appels de la page. Symétriquement, `BillingPanel` embarqué dans l'écran de fiche était cassé pour les comptes `reservations`. | Table de préfixes remplacée par des règles ordonnées URL + méthode, avec permissions multiples |
| Moyen | `/health` passait une chaîne brute à `session.exec()`, refusée par SQLAlchemy 2.0 : la base était **toujours signalée en échec** | `text("SELECT 1")` |
| Moyen | Zenchef insérait dates et heures sous forme de chaînes dans des colonnes `DATE`/`TIME` | Parsing typé |
| Moyen | Les routes React n'étaient pas protégées : taper `/users` ou `/facturation` affichait la page malgré l'absence de permission | Garde sur chaque route |
| Mineur | La pastille de rappels du menu était du code mort : `setReminderCount` n'était jamais appelé | `onCountChange` branché |
| Mineur | `JWT_SECRET` absent silencieusement remplacé par un secret aléatoire | Avertissement au démarrage + `.env.example` |
| Mineur | `.env.example` ne documentait ni `JWT_SECRET`, ni `CORS_ORIGINS`, ni `TZ`, ni `AUTH_TOKEN_TTL_HOURS` | Documentés |

### 6.2 Problèmes signalés en février qui n'existent pas / plus

- **pdfminer.six et pypdf manquants** : le code utilise `pdfplumber` (présent dans les
  requirements) et `pypdf` y figure également. Aucun blocage.
- **Endpoint `/api/floorplan/templates` manquant** : le frontend ne l'appelle plus.
- **`find_free_position_for_table()` morte** : la fonction a été supprimée.
- **Survol désactivé dans FloorCanvas** : le TODO et le code inactif ont disparu.
- **Absence de gestion multi-utilisateurs** : un module complet de comptes, rôles et
  permissions existe désormais (§3).

### 6.3 Points ouverts connus

- **Pas de détection de rotation horaire.** `arrival_time` ne sert qu'au tri
  (`floorplan.py`, tri par `-pax` puis `arrival_time`). Deux réservations à 12:00 et
  14:00 peuvent recevoir la même table sans qu'aucun conflit ne soit signalé.
- **`except Exception: pass` massif dans `database.py`.** Chaque helper de migration
  avale ses erreurs. C'est ce motif qui a masqué deux bugs critiques pendant des mois.
  Les échecs devraient au minimum être journalisés.
- **Aucune suite de tests automatisés.** Les `test_*.py` à la racine sont des scripts
  d'exploration manuels, pas des tests exécutables par un runner.
- **Pas de limitation de débit sur `/api/auth/login`**, qui reste exposé au bourrage
  d'identifiants malgré le coût élevé de PBKDF2.
- **`list_reservations` charge toutes les lignes** puis filtre en Python. Acceptable
  au volume actuel, à revoir si l'historique grossit.
- **Les permissions restent couplées aux URL, pas aux routeurs.** Le nouveau système
  de règles est explicite et testé, mais rien n'empêche mécaniquement une future route
  d'être ajoutée hors de toute règle. Le défaut est fermé (403), donc l'erreur se voit
  vite — c'est exactement l'inverse qui s'était produit avec `billing`, où la règle
  existait mais ne correspondait à aucune URL réelle, sans aucun signal.
- **Duplication de configuration de déploiement** : deux `requirements.txt`, deux
  `Procfile`, deux `Dockerfile`.
- **Le dossier `plant/` est une copie morte** du plan de salle (`floorplan.py` y fait
  71 Ko contre 112 Ko dans `app/`, `FloorCanvas.tsx` 53 Ko contre 72 Ko). Il ne reçoit
  aucun correctif et risque d'être édité par erreur. À supprimer ou à archiver hors
  du dépôt.
- **`floorplan.py` définit ses fonctions avant ses imports** (les `import` sont ligne
  ~460, les premières fonctions ligne 5). Cela ne fonctionne que grâce à
  `from __future__ import annotations` et au fait que les corps ne s'exécutent qu'à
  l'appel. C'est fragile et déroutant à la lecture.

---

## 7. FONCTIONNALITÉS MANQUANTES

### 7.1 Gestion des conflits horaires
- Pas de détection de chevauchement temporel
- Pas de durée estimée par réservation, pas de créneaux définis

### 7.2 Statistiques & analytics
- Pas de taux d'occupation, pas de KPI (couverts/table, rotation moyenne)
- Pas d'historique de performance

### 7.3 Optimisation de l'algorithme
- Glouton sans backtracking : aucune exploration d'alternatives
- Pas de score de qualité global d'une attribution

### 7.4 Export avancé
- Pas d'export Excel, pas d'impression directe
- Pas de modèles PDF personnalisables

### 7.5 Collaboration
- Le multi-comptes existe, mais pas la **collaboration temps réel** ni l'**audit trail**
  (qui a modifié quoi, et quand)

### 7.6 Qualité
- Découpage de `floorplan.py` (2 323 lignes) et `FloorCanvas.tsx` (1 796 lignes)
- Mise en place d'une vraie suite de tests (pytest + Vitest)

---

## 8. CHOIX TECHNIQUES

### 8.1 JSON pour `data` / `assignments`
Souplesse de schéma, performances suffisantes au volume d'un restaurant, et JSONB
indexable côté PostgreSQL. **Verdict : adapté.**

### 8.2 Canvas HTML5 plutôt que SVG
Meilleures performances en interaction continue, contrôle au pixel, détection de
collision plus simple. **Verdict : optimal.**

### 8.3 ReportLab
Pur Python, sans dépendance système, mature. Complété par `pypdf` pour annoter un
PDF existant et `pdfplumber` pour le lire. **Verdict : cohérent.**

### 8.4 PBKDF2 plutôt qu'Argon2 / bcrypt
600 000 itérations SHA-256 via la bibliothèque standard, sans dépendance native —
un vrai avantage au déploiement. Le coût est visible (~450 ms par connexion),
ce qui est le comportement attendu. **Verdict : acceptable.**

---

## 9. PLAN D'ACTION

### Phase 1 — Fiabilité (fait)
Correctifs des §6.1 et §6.1 bis, vérifiés par trois campagnes de tests exécutées
contre une base jetable — **105 contrôles, tous au vert** :
- **44 contrôles généraux** — santé, authentification, CRUD réservations, garde-fous
  de quantités, duplication, traversée de chemin sur les allergènes, génération PDF ;
- **20 contrôles de permissions** — un membre `billing` peut facturer sans pouvoir
  modifier les fiches, un membre `reservations` garde son écran de fiche complet
  (panneau de facturation inclus) sans accéder à la page Facturation, un membre
  `rooftop` reste cantonné au Rooftop ;
- **41 contrôles du plan de salle** — persistance de la numérotation et du
  renumérotage manuel, familles d'étiquettes, tri naturel, capacités par défaut,
  auto-attribution avec couverture vérifiée réservation par réservation, tolérance
  aux heures absentes, `compare`, `reset`, exports PDF, et **la chaîne d'import
  complète depuis un vrai PDF généré pour le test** (parsing → stockage →
  auto-attribution).

Le frontend n'a **pas** été recompilé : Node.js n'est pas installé sur la machine
d'audit, donc `npm run build` reste à exécuter.

### Phase 2 — Filet de sécurité (prioritaire)
1. Versionner ces deux campagnes sous forme de suite pytest (elles n'existent
   aujourd'hui que comme scripts d'audit jetables)
2. Journaliser les échecs de migration au lieu de les avaler
3. Ajouter une limitation de débit sur `/api/auth/login`
4. Fusionner les fichiers de dépendances et de déploiement dupliqués
5. Lancer `npm run build` pour valider le typage du frontend

### Phase 3 — UX
1. Aperçu avant auto-assign
2. Undo/redo sur le canvas
3. Meilleur retour visuel sur les collisions
4. Exposer les `alerts` de l'auto-assign dans l'interface

### Phase 4 — Fonctionnalités
1. Détection des conflits horaires (activable)
2. Statistiques d'occupation
3. Export Excel des réservations attribuées
4. Audit trail des modifications

### Phase 5 — Optimisation
1. Auto-assign v2 avec scoring global
2. Cache des calculs de collision
3. Chargement paresseux des instances anciennes

---

## 10. CONCLUSION

### État actuel
Le projet est **fonctionnel et proprement structuré** : séparation backend/frontend
nette, typage fort des deux côtés, logique métier riche, interface interactive
aboutie, et désormais un contrôle d'accès cohérent de bout en bout.

### Risque principal
Ce n'est plus une dépendance manquante, mais la **défaillance silencieuse**, sous deux
formes distinctes :

1. **Les erreurs avalées.** Le motif `except Exception: pass` a masqué une migration
   jamais exécutée, une colonne jamais créée et une validation contournable — pendant
   des mois, sans le moindre signal.
2. **La configuration qui ne correspond à rien.** La règle de permission
   `/api/facturation` était syntaxiquement correcte, lisible, et ne pointait vers
   aucune URL existante : la permission « Facturation » ne donnait accès à rien, et
   rien dans le code ne pouvait le signaler.

Le point commun : dans les deux cas, le système *paraissait* configuré correctement.
Seule une vérification par exécution réelle les a révélés.

### Recommandation
**Priorité 1** : filet de sécurité (Phase 2) — tests automatisés et journalisation
des échecs, pour que la prochaine régression se voie.
**Priorité 2** : conflits horaires (§7.1), seul vrai manque métier.
**Priorité 3** : UX et analytics.

Le code est prêt pour la production en usage multi-utilisateurs, à condition de
définir `JWT_SECRET`.

---

## ANNEXES

### A. Format FloorPlanData (JSON)
```typescript
{
  room: { width: 1200, height: 800, grid: 50 },
  walls: [{id, x, y, w, h}],
  columns: [{id, x, y, r}],
  no_go: [{id, x, y, w, h}],
  round_only_zones: [{id, x, y, w, h}],
  rect_only_zones: [{id, x, y, w, h}],
  fixtures: [{id, x, y, w?, h?, r?, shape?, label?, locked?}],
  tables: [{
    id, kind: 'fixed'|'rect'|'round'|'sofa'|'standing',
    x, y, w?, h?, r?,
    capacity?, locked?, label?
  }],
  fixed_chair_stock?: 28,
  max_dynamic_tables?: { rect?: 10, round?: 5 },
  large_table_config?: {
    pax_threshold_right?: 10,
    pax_threshold_vertical?: 20,
    vertical_span_max?: 7
  }
}
```

### B. Format AssignmentMap (JSON)
```typescript
{
  tables: {
    "table_id_1": {
      res_id: "reservation_uuid",
      name: "DUPONT",
      pax: 4,
      last_resort?: true
    }
  }
}
```

### C. Variables d'environnement
| Variable | Rôle | Défaut |
|---|---|---|
| `DATABASE_URL` | Connexion base (ou `PGHOST`/`PGDATABASE`/`PGUSER`/`PGPASSWORD`/`PGPORT`) | `sqlite:///./data.db` |
| `JWT_SECRET` | **Obligatoire en production**, signature des jetons | aléatoire par processus |
| `AUTH_TOKEN_TTL_HOURS` | Durée de vie des sessions | `8` |
| `CORS_ORIGINS` | Origines navigateur autorisées (séparées par des virgules) | `http://localhost:5173` |
| `TZ` | Fuseau pour « à venir » / « passées » | `Europe/Paris` |
| `AI_PROVIDER` | `openai` ou `groq` (remplissage assisté des plaintes) | `openai` |
| `OPENAI_API_KEY` / `GROQ_API_KEY` | Clé du fournisseur choisi | — |
| `PORT` | Port d'écoute (Railway / Docker) | `8080` |

### D. Commandes utiles
```bash
# Dev backend
cd app
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Dev frontend
cd app/frontend
npm run dev

# Build prod (typecheck + bundle)
cd app/frontend
npm run build

# Image Docker complète (frontend + backend)
docker build -t albert-app .
```
