# ANALYSE COMPLÈTE DE L'ARCHITECTURE - Restaurant Albert Brussels

## Date d'analyse
3 février 2026 - 23:25

---

## 1. CONTEXTE MÉTIER

### Restaurant Albert Brussels
- **Type**: Restaurant avec service de brunch/déjeuner et dîner
- **Problématique**: Gestion optimale du plan de salle pour maximiser l'occupation
- **Contraintes**:
  - Tables fixes agençables (4 pax chacune, combinables jusqu'à 28 pax)
  - Tables rectangulaires (6 pax de base, extensibles à 8 avec rallonge)
  - Tables rondes (10 pax, dernier recours car moins pratiques)
  - PDF de réservations reçu dans un format fixe spécifique

---

## 2. ARCHITECTURE TECHNIQUE

### 2.1 Stack Technologique

**Backend (Python)**
- FastAPI 0.115.2
- SQLModel 0.0.22 / SQLAlchemy 2.0.36
- Pydantic 2.9.2
- ReportLab 4.2.5 (génération PDF)
- pdfminer.six (extraction texte PDF) - **MANQUANT dans requirements.txt**
- pypdf (manipulation PDF) - **MANQUANT dans requirements.txt**
- PostgreSQL (production) / SQLite (dev)

**Frontend (React + TypeScript)**
- React 18.3.1
- React Router DOM 6.26.2
- Axios 1.7.7
- Lucide React 0.441.0 (icônes)
- TailwindCSS 3.4.14
- Vite 7.1.12

**Déploiement**
- Railway (production PostgreSQL)
- Procfile pour uvicorn
- Support multi-environnement (SQLite/PostgreSQL)

### 2.2 Structure Base de Données

**Tables principales**:
1. `floorplanbase` - Plans maîtres (templates)
   - `id`, `name`, `data` (JSON), `created_at`, `updated_at`
   
2. `floorplaninstance` - Instances de service spécifiques
   - `id`, `service_date`, `service_label` (lunch/dinner)
   - `template_id` (FK vers floorplanbase)
   - `data` (JSON - plan modifié pour ce service)
   - `assignments` (JSON - attribution table→réservation)
   - `reservations` (JSON - réservations parsées du PDF)
   - Contrainte UNIQUE sur (service_date, service_label)

3. `reservation` - Réservations principales (système distinct)
   - `id`, `client_name`, `pax`, `service_date`, `arrival_time`
   - `drink_formula`, `notes`, `status`, `allergens`
   - `final_version`, `on_invoice`, `last_pdf_exported_at`
   - Contrainte UNIQUE sur (service_date, arrival_time, client_name, pax)

**Note importante**: Le système floorplan est **complètement indépendant** de la table reservation principale. Les réservations pour le plan de salle sont stockées dans `floorplaninstance.reservations` (JSON).

---

## 3. LOGIQUE MÉTIER DÉTAILLÉE

### 3.1 Workflow Complet

```
1. CRÉATION PLAN DE BASE
   - Définir dimensions salle (room.width, room.height, room.grid)
   - Placer murs (walls), colonnes (columns)
   - Définir zones interdites (no_go)
   - Ajouter fixtures/décorations
   - Placer tables fixes, rectangulaires, rondes
   - Définir zones spécialisées:
     * round_only_zones (tables rondes uniquement)
     * rect_only_zones (tables rectangulaires uniquement)

2. IMPORT PDF RÉSERVATIONS
   - Parser le PDF avec format Albert Brussels spécifique
   - Extraire: heure, pax, nom client
   - Nettoyer les données (téléphones, statuts, sources)
   - Générer IDs déterministes (MD5 basé sur contenu)
   - Stocker dans floorplaninstance.reservations

3. AUTO-ATTRIBUTION DES TABLES
   - Trier réservations par pax DESC, arrival_time ASC
   - Pour chaque réservation, essayer dans l'ordre:
     a) Table fixe single (best-fit)
     b) Table rect single (6-8 pax avec extension)
     c) Combo 2 tables rect
     d) Pack tables fixes (pour groupes 28 pax)
     e) Pack tables rect (multi-tables)
     f) Pack tables rondes
     g) Table ronde single (dernier recours, flaggé last_resort)
     h) Création dynamique de nouvelles tables
   - Stocker dans floorplaninstance.assignments

4. NUMÉROTATION
   - Tables fixes: 1, 2, 3... 20
   - Tables rect: T1, T2, T3... T20
   - Tables rondes: R1, R2, R3... R20
   - Ordre: column-major (x asc, y desc) = top-left, count DOWN

5. EXPORT PDF
   - PDF annoté: PDF original + numéros tables + plan + listes
   - PDF complet: liste service + plan numéroté + liste tables
```

### 3.2 Algorithme Auto-Assign (Détaillé)

**Fonction**: `_auto_assign(plan_data, reservations)`

**Étapes**:
1. Partitionner tables: fixed, rects, rounds
2. Créer pools disponibles (dictionnaires par ID)
3. Trier réservations: pax DESC, arrival_time ASC (grosses tables d'abord)
4. Pour chaque réservation:
   ```python
   # Priorité 1: Table fixe best-fit
   if fixed_table with capacity >= pax:
       assign(fixed_table)
   
   # Priorité 2: Table rect single avec extension
   elif rect_table where (cap + 2 up to 8) >= pax:
       assign(rect_table)
   
   # Priorité 3: Combo 2 tables rect
   elif 2_rect_tables where sum(cap_extended) >= pax:
       assign(both_tables)
   
   # Priorité 4: Pack multiple fixed tables
   elif pack_fixed_tables(greedy) >= pax:
       assign(all_tables_in_pack)
   
   # Priorité 5: Pack multiple rect tables
   elif pack_rect_tables(greedy, allow_ext) >= pax:
       assign(all_tables_in_pack)
   
   # Priorité 6: Pack multiple round tables
   elif pack_round_tables(greedy) >= pax:
       assign(all_tables_in_pack)
   
   # Priorité 7: Table ronde single (last_resort=True)
   elif round_table with capacity >= pax:
       assign(round_table, last_resort=True)
   
   # Priorité 8: Création dynamique
   else:
       while remaining_pax > 0:
           spot = find_spot_for_table(plan, "rect", 120x60)
           if spot:
               create_table(rect, 6_pax, at_spot)
               assign(new_table)
               remaining_pax -= 6
           else:
               spot = find_spot_for_table(plan, "round", r=50)
               if spot:
                   create_table(round, 10_pax, at_spot)
                   assign(new_table)
                   remaining_pax -= 10
               else:
                   break  # Pas de place, laisse non assigné
   ```

**Gestion des zones spécialisées**:
- `_find_spot_for_table()` vérifie si position dans round_only_zone ou rect_only_zone
- Si dans zone R: crée uniquement tables rondes
- Si dans zone T: crée uniquement tables rect
- Sinon: logique normale

### 3.3 Parsing PDF

**Format attendu (Albert Brussels)**:
```
albert brussels | Standard | 31/01/2026
Brunch - Nombre total de couverts: 134
Grille horaires: 11:00, 11:15, 11:30...

Heure    Pax    Client              Table    Statut      Date Création    Source
11:00    2      DUPONT Jean         [VIDE]   Confirmé    2026-01-27 11:26 Web
                +32 123 456 789
```

**Logique de parsing** (`import-pdf` endpoint):
1. Extraire texte avec pdfminer.six
2. Séparer en lignes
3. Ignorer patterns d'en-tête (Nombre de couverts, albert brussels, etc.)
4. Pour chaque ligne HH:MM:
   - Chercher pax dans les 5 lignes suivantes (chiffre 1-30)
   - Chercher nom dans les 5 lignes après pax
   - Nettoyer nom (retirer téléphones, statuts, dates)
   - Générer ID déterministe MD5
5. Stocker dans instance.reservations

---

## 4. FRONTEND - FLOORCANVAS

### 4.1 Composant Principal

**FloorCanvas.tsx** (1303 lignes)
- Canvas HTML5 avec interaction souris complète
- Zoom/pan avec molette
- Drag & drop pour déplacer objets
- Redimensionnement par handles
- Menu contextuel (clic droit)
- Modes de dessin (zones interdites, zones R, zones T)

**États gérés**:
- `draggingId`, `fixtureDraggingId`, `noGoDraggingId`, etc.
- `resizeHandle`, `fixtureResize`, `noGoResize`, etc.
- `draftNoGo`, `draftRoundZone`, `draftRectZone`
- `contextMenu`, `hoveredItem`
- `scale`, `offset` (viewport)

**Détection collision**:
- Tables vs murs
- Tables vs colonnes
- Tables vs fixtures
- Tables vs no-go zones
- Tables vs autres tables
- Revert automatique si position invalide

**Curseurs adaptatifs**:
- `nwse-resize`, `ew-resize`, `ns-resize` sur handles
- `context-menu` sur objets (indique clic droit disponible)
- `crosshair` en mode dessin
- `move` pendant drag

### 4.2 Menu Contextuel

**Détection prioritaire**:
1. Zones R/T (round_only_zones, rect_only_zones)
2. Zones interdites (no_go)
3. Fixtures
4. Tables

**Actions disponibles**:
- Zone R: "Supprimer la zone R"
- Zone T: "Supprimer la zone T"
- Zone interdite: "Supprimer la zone interdite"
- Fixture: "Supprimer l'objet"
- Table: "Verrouiller/Déverrouiller" + "Supprimer la table"

**Rendu**: Portal React pour éviter overflow:hidden du canvas

---

## 5. POINTS FORTS DU CODE EXISTANT

### 5.1 Architecture
✅ Séparation claire backend/frontend
✅ Type safety avec TypeScript + Pydantic
✅ Indépendance système floorplan (pas de conflit avec réservations principales)
✅ IDs déterministes pour cohérence PDF import/export
✅ Migrations idempotentes (PostgreSQL + SQLite)

### 5.2 Logique Métier
✅ Algorithme auto-assign complet et priorisé
✅ Gestion extension tables rect (+2 pax max 8)
✅ Pack multi-tables pour grands groupes
✅ Création dynamique si nécessaire
✅ Zones spécialisées pour contrôle type tables
✅ Flags last_resort pour tables rondes

### 5.3 UX/UI
✅ Canvas interactif avec feedback visuel
✅ Zoom/pan fluide
✅ Menu contextuel intuitif
✅ Modes de dessin exclusifs
✅ Collision detection temps réel
✅ Curseurs adaptatifs

### 5.4 Production-Ready
✅ Logging structuré avec corrélation IDs
✅ Debug mode avec buffer en mémoire
✅ Support Railway (PostgreSQL)
✅ Gestion erreurs propre
✅ Migrations automatiques

---

## 6. PROBLÈMES IDENTIFIÉS

### 6.1 CRITIQUE - Dépendances Manquantes

**requirements.txt** ne liste PAS:
- `pdfminer.six` - Utilisé dans `/api/floorplan/import-pdf`
- `pypdf` - Utilisé dans `/api/floorplan/instances/{id}/export-annotated`

**Impact**: L'import PDF et l'export annoté vont crasher en production.

**Ligne 1317** (floorplan.py):
```python
try:
    from pdfminer.high_level import extract_text
except Exception:
    raise HTTPException(500, "pdfminer.six non installé côté serveur")
```

**Ligne 284** (floorplan.py):
```python
try:
    from pypdf import PdfReader, PdfWriter, PdfMerger
except Exception:
    PdfReader = None  # type: ignore
```

### 6.2 MAJEUR - Incohérence Numérotation

**Mémoire système** dit:
- Tables rectangulaires: T1, T2, T3...
- Tables rondes: R1, R2, R3...

**Code réel** (ligne 8 floorplan.py):
```python
# Rect tables: T1..TN
# Round tables: R1..RN
```

**Mémoire d1a7c55c** dit:
- Fixed/rect: 1..20
- Round: T1..T20  ← ERREUR

**Correction**: La mémoire est incorrecte. Le code fait:
- Fixed: 1, 2, 3... 20
- Rect: T1, T2, T3... 20
- Round: R1, R2, R3... 20

### 6.3 MOYEN - Logique find_free_position_for_table

**Ligne 660-692** (floorplan.py):
Fonction `find_free_position_for_table()` définie mais **jamais utilisée**.
Elle contient aussi un appel à `tableCollides()` inexistant (ligne 686).

Cette fonction semble être une version abandonnée de `_find_spot_for_table()`.

### 6.4 MOYEN - Endpoint /templates inexistant

**FloorPlanPage.tsx** appelle:
```typescript
const res = await api.get('/api/floorplan/templates')
```

**Backend** n'a PAS ce endpoint. Routes disponibles:
- `/api/floorplan/base` (GET/PUT)
- `/api/floorplan/instances` (GET/POST)
- `/api/floorplan/instances/{id}` (GET/PUT)

**Impact**: Le frontend va crasher au chargement de FloorPlanPage.

### 6.5 MINEUR - Survol Désactivé

**FloorCanvas.tsx ligne 929**:
```typescript
// DÉSACTIVÉ TEMPORAIREMENT: Le survol cause une boucle infinie de sauvegardes
// TODO: Implémenter avec useMemo ou useCallback pour éviter les re-renders
```

Le feedback visuel au survol est désactivé pour éviter une boucle de re-renders.

### 6.6 MINEUR - Gestion Rotations Horaires

L'algorithme ne gère PAS les rotations de tables (turn-over).
Si deux réservations sont sur la même table à des heures différentes, pas de détection.

**Exemple**: 
- 12:00 - Dupont - 4 pax - Table 5
- 14:00 - Martin - 4 pax - Table 5

L'algo va placer les deux sur Table 5 sans conflit détecté.

---

## 7. FONCTIONNALITÉS MANQUANTES

### 7.1 Gestion Conflit Horaires
- Pas de détection overlaps temporels
- Pas de durée estimée par réservation
- Pas de slots horaires définis

### 7.2 Statistiques & Analytics
- Pas de taux d'occupation
- Pas de KPIs (couverts/table, rotation moyenne)
- Pas d'historique performances

### 7.3 Optimisation Algorithme
- Pas de backtracking si solution meilleure existe
- Greedy simple (pas d'exploration alternatives)
- Pas de score de qualité d'attribution

### 7.4 Export Avancé
- Pas d'export Excel
- Pas d'impression directe
- Pas de templates PDF personnalisables

### 7.5 Multi-Utilisateurs
- Pas de gestion permissions
- Pas de collaboration temps réel
- Pas d'audit trail

---

## 8. CHOIX TECHNIQUES À VALIDER

### 8.1 Pourquoi JSON pour data/assignments?
- Flexibilité schéma (pas de migrations fréquentes)
- Performance OK pour volumes restaurant
- Query simple si besoin: PostgreSQL JSONB indexable

**Alternative**: Tables normalisées (floor_table, floor_wall, etc.)
**Verdict**: Choix actuel valide pour ce use-case

### 8.2 Pourquoi Canvas HTML5 vs SVG?
- Performance meilleure pour interactions temps réel
- Contrôle pixel-perfect
- Plus simple pour collision detection

**Alternative**: SVG + React components
**Verdict**: Choix actuel optimal

### 8.3 Pourquoi ReportLab vs autres?
- Pure Python (pas de deps système)
- Mature et stable
- Contrôle total du rendu

**Alternative**: WeasyPrint, pdfkit
**Verdict**: Choix correct

---

## 9. PLAN D'ACTION PROPOSÉ

### Phase 1: CORRECTIFS CRITIQUES (1-2h)
1. Ajouter dépendances manquantes à requirements.txt
2. Corriger/créer endpoint /api/floorplan/templates (ou adapter frontend)
3. Supprimer fonction morte find_free_position_for_table
4. Corriger mémoire système numérotation

### Phase 2: ROBUSTESSE (2-3h)
1. Ajouter gestion erreurs import PDF (logs détaillés)
2. Ajouter validation assignments avant save
3. Ajouter tests capacité plan (max tables, bounds checks)
4. Améliorer messages d'erreur utilisateur

### Phase 3: AMÉLIORATIONS UX (2-3h)
1. Réactiver survol avec useMemo/useCallback
2. Ajouter preview avant auto-assign
3. Ajouter undo/redo sur canvas
4. Améliorer feedback visuel collisions

### Phase 4: FONCTIONNALITÉS (3-5h)
1. Détection conflits horaires (optionnel avec toggle)
2. Statistiques basiques (occupancy rate)
3. Export Excel réservations assignées
4. Templates de plans (quick start)

### Phase 5: OPTIMISATION (2-3h)
1. Algorithme auto-assign v2 avec scoring
2. Cache calculs coûteux (collision maps)
3. Batch operations pour perf
4. Lazy loading instances anciennes

---

## 10. CONCLUSION

### État Actuel
Le projet est **fonctionnel et structuré proprement**, avec:
- Architecture solide et maintenable
- Logique métier complète
- UX interactive et intuitive
- Code relativement propre

### Problèmes Bloquants
- **Dépendances manquantes** empêchent import/export PDF
- **Endpoint manquant** casse interface plans

### Potentiel d'Amélioration
- Gestion conflits horaires
- Optimisation algorithme
- Analytics/reporting
- Multi-utilisateurs

### Recommandation
**Priorité 1**: Corriger les bugs critiques (Phase 1)
**Priorité 2**: Robustesse et tests (Phase 2)
**Priorité 3**: UX et features (Phases 3-4)

Le code est déjà production-ready pour un usage mono-utilisateur avec les correctifs de Phase 1.

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
    id, kind: 'fixed'|'rect'|'round',
    x, y, w?, h?, r?,
    capacity?, locked?, label?
  }]
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
    },
    "table_id_2": { ... }
  }
}
```

### C. Commandes Utiles
```bash
# Dev backend
cd app
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Dev frontend
cd app/frontend
npm run dev

# Build prod
cd app/frontend
npm run build

# Railway deploy
git push origin main
```
