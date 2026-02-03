# Guide Utilisateur - Plan de Salle Albert Brussels

## Workflow Complet

### 1. Créer le Plan de Base (Une fois)

**Navigation**: FloorPlan → Plan de base

**Actions**:
1. Ajuster dimensions salle (glisser coins)
2. Placer murs (fixtures rectangulaires)
3. Placer colonnes (fixtures rondes)
4. Définir zones interdites (bouton rouge)
5. Placer tables:
   - **Tables fixes** (vertes): Tables agençables 4 pax, combinables jusqu'à 28 pax
   - **Tables rectangulaires** (bleues): 6-8 pax avec rallonge
   - **Tables rondes** (orange): 10 pax, dernier recours
6. Définir zones spécialisées:
   - **Zone R** (bleu): Forcer tables rondes uniquement
   - **Zone T** (vert): Forcer tables rectangulaires uniquement
7. **Sauvegarder** le plan

**Raccourcis**:
- Molette souris: Zoom
- Glisser: Déplacer objets
- Clic droit: Menu contextuel
- Double-clic: Verrouiller/déverrouiller

---

### 2. Créer Instance de Service

**Navigation**: FloorPlan → Instances

**Pour chaque service** (date + midi/dîner):
1. **Créer nouvelle instance** via API ou interface
2. Sélectionner instance dans liste
3. Instance copie automatiquement le plan de base

---

### 3. Importer PDF Réservations

**Via API**:
```bash
curl -X POST http://localhost:8000/api/floorplan/import-pdf \
  -F "file=@reservations.pdf" \
  -F "service_date=2026-02-05" \
  -F "service_label=lunch"
```

**Format PDF attendu** (Albert Brussels):
- Colonnes: Heure | Pax | Client | Table | Statut | Date | Source
- Ligne par réservation
- Nom client suivi téléphone

**Résultat**:
- Réservations parsées et stockées dans instance
- Prêt pour auto-attribution

---

### 4. Auto-Attribuer Tables

**Action**: POST `/api/floorplan/instances/{id}/auto-assign`

**Algorithme appliqué**:
1. Tables fixes best-fit
2. Tables rect single (avec extension)
3. Combo 2 tables rect
4. Pack tables fixes (grands groupes)
5. Pack tables rect
6. Pack tables rondes
7. Table ronde single (marqué "dernier recours")
8. Création dynamique si nécessaire

**Vérifier**:
- Nombre de tables assignées dans logs
- Tables non assignées (warnings)
- Nouvelles tables créées si besoin

---

### 5. Ajustements Manuels

**Dans interface**:
1. Sélectionner instance
2. Déplacer tables si besoin
3. Modifier assignations manuellement
4. **Sauvegarder** l'instance

---

### 6. Numéroter Tables

**Action**: POST `/api/floorplan/instances/{id}/number-tables`

**Numérotation appliquée**:
- Tables fixes: 1, 2, 3... 20
- Tables rectangulaires: T1, T2, T3... 20
- Tables rondes: R1, R2, R3... 20
- Ordre: top-left counting DOWN (colonnes)

---

### 7. Exporter PDF

**Option 1 - PDF Annoté**:
```bash
POST /api/floorplan/instances/{id}/export-annotated
```
**Contenu**:
- PDF original avec numéros tables remplis
- Plan de salle avec assignations
- Liste des tables

**Option 2 - PDF Complet**:
```bash
GET /api/floorplan/instances/{id}/export-pdf
```
**Contenu**:
- Liste service avec tables
- Plan de salle numéroté
- Liste complète des tables

---

## Cas d'Usage Avancés

### Grands Groupes (>10 personnes)

L'algorithme va:
1. Essayer pack tables fixes (jusqu'à 28 pax)
2. Essayer pack tables rect avec extensions
3. Créer tables dynamiques si nécessaire

**Configuration optimale**:
- Placer tables fixes agençables proches
- Définir zone flexible pour créations dynamiques

### Service Complet (>capacité plan)

**Stratégies**:
1. L'algo crée tables dynamiques automatiquement
2. Vérifier espace disponible avant service
3. Ajuster plan de base si récurrent
4. Utiliser zones R/T pour contrôler types

### Rotation Tables (2 services)

**Limitation actuelle**: Pas de détection conflits horaires

**Workaround**:
1. Créer 2 instances séparées (lunch/dinner)
2. Vérifier manuellement overlaps
3. Ajuster horaires si conflit

---

## Dépannage

### "Aucune réservation trouvée dans le PDF"

**Causes**:
- Format PDF différent d'Albert Brussels
- Colonnes mal alignées
- Pas de ligne avec format HH:MM

**Solution**:
1. Vérifier format PDF (colonnes)
2. Consulter logs backend (lignes debug)
3. Adapter parser si format change

### "Instance not found"

**Causes**:
- Instance supprimée
- Mauvais ID

**Solution**:
1. Lister instances: GET `/api/floorplan/instances`
2. Recréer instance si nécessaire

### Tables se chevauchent après auto-assign

**Causes**:
- Plan de base trop petit
- Trop de réservations

**Solution**:
1. Agrandir salle dans plan de base
2. Vérifier zones interdites (pas trop grandes)
3. Définir zones flexibles pour créations

### Canvas ne charge pas

**Causes**:
- Endpoint /templates inexistant (avant correctif)
- Erreur réseau

**Solution**:
1. Vérifier console navigateur (erreurs)
2. Vérifier backend actif
3. Version corrigée utilise /base

---

## Limites Connues

1. **Pas de conflits horaires**: Rotation manuelle
2. **Greedy algorithm**: Pas d'optimisation globale
3. **Pas de statistiques**: Taux occupation à calculer manuellement
4. **Canvas 2D uniquement**: Pas de 3D/VR
5. **Mono-utilisateur**: Pas de collaboration temps réel

---

## Support

**Logs utiles**:
- Backend: stdout (Railway logs)
- Frontend: Console navigateur
- Debug mode: Header `X-Salle-Debug: 1`

**Fichiers clés**:
- `ANALYSE_ARCHITECTURE.md`: Architecture complète
- `TESTS_RECOMMANDES.md`: Tests validation
- `requirements.txt`: Dépendances Python
