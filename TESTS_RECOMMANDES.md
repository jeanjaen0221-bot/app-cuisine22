# Tests Recommandés - Système Plan de Salle

## Tests Critiques Post-Correctifs

### 1. Import PDF
```bash
# Test avec PDF format Albert Brussels
curl -X POST http://localhost:8000/api/floorplan/import-pdf \
  -F "file=@reservation.pdf" \
  -F "service_date=2026-02-05" \
  -F "service_label=lunch"

# Vérifier réponse: {"parsed": [...], "message": "Parsed N reservations..."}
# Si échec: vérifier logs pour format PDF
```

### 2. Auto-Assign
```bash
# Créer instance
curl -X POST http://localhost:8000/api/floorplan/instances \
  -H "Content-Type: application/json" \
  -d '{"service_date": "2026-02-05", "service_label": "lunch"}'

# Auto-assign (après import PDF)
curl -X POST http://localhost:8000/api/floorplan/instances/{id}/auto-assign

# Vérifier: assignments.tables doit être rempli
```

### 3. Export PDF Annoté
```bash
# Avec pypdf installé
curl -X POST http://localhost:8000/api/floorplan/instances/{id}/export-annotated \
  -F "file=@original.pdf" \
  -F "start_y_mm=95.0" \
  -F "row_h_mm=13.5" \
  -F "table_x_mm=137.0" \
  --output annotated.pdf
```

### 4. Frontend Plan de Base
```bash
# Ouvrir http://localhost:5173/floorplan
# Vérifier:
# - Plan de base charge (pas d'erreur console)
# - Bouton "Sauvegarder" fonctionne
# - Pas de référence à /templates
```

## Tests Validation

### 5. Validation Plan Invalid
```python
# Test dimensions room invalides
response = requests.put('http://localhost:8000/api/floorplan/base', json={
    "data": {
        "room": {"width": 50, "height": 50}  # < 100
    }
})
# Doit retourner 400: "Invalid room: dimensions must be >= 100"
```

### 6. Validation Assignments Invalid
```python
# Test assignment sans champ requis
response = requests.put(f'http://localhost:8000/api/floorplan/instances/{id}', json={
    "assignments": {
        "tables": {
            "table1": {"name": "Dupont"}  # manque res_id, pax
        }
    }
})
# Doit retourner 400: "Invalid assignment for table table1: missing 'res_id'"
```

## Tests Collision

### 7. Table Overlapping
```javascript
// Dans FloorCanvas, glisser table sur autre table
// Vérifier:
// - Bordure rouge pendant drag
// - Table revient position valide au drop
// - Console: pas d'erreur
```

### 8. Zones Spécialisées
```javascript
// Créer zone R (bleue)
// Auto-assign avec réservations
// Vérifier: tables créées dynamiquement dans zone R sont rondes
```

## Cas Limites

### 9. PDF Vide
```bash
# Import PDF sans réservations
# Doit retourner 400: "Aucune réservation trouvée dans le PDF..."
# Logs: afficher lignes debug pour diagnostic
```

### 10. Trop de Réservations
```bash
# Plan avec 5 tables, 20 réservations
# Auto-assign doit:
# - Créer tables dynamiques
# - Logger "N reservations NOT assigned" si pas de place
```

## Performance

### 11. Import PDF Large
```bash
# PDF avec 100+ réservations
# Temps < 5s
# Pas de timeout
```

### 12. Canvas avec 50+ Tables
```javascript
// Plan avec beaucoup de tables
// Zoom/pan fluide
// Pas de lag
```

## Régression

### 13. Numérotation
```bash
# Créer plan avec:
# - 3 tables fixed
# - 2 tables rect
# - 1 table round

# POST /api/floorplan/base/number-tables
# Vérifier labels:
# - Fixed: 1, 2, 3
# - Rect: T1, T2
# - Round: R1
```

### 14. Menu Contextuel
```javascript
// Clic droit sur:
// - Zone R → "Supprimer la zone R"
// - Table → "Verrouiller/Déverrouiller"
// - Fixture → "Supprimer l'objet"
// Menu s'affiche sans crash
```

## Checklist Production

- [ ] requirements.txt installé (pip install -r requirements.txt)
- [ ] pdfminer.six et pypdf présents
- [ ] Frontend build sans erreurs (npm run build)
- [ ] Base de données initialisée
- [ ] Migrations appliquées
- [ ] Import PDF fonctionne
- [ ] Auto-assign fonctionne
- [ ] Export PDF fonctionne
- [ ] Validation bloque données invalides
- [ ] Logs structurés visibles
- [ ] Aucune erreur console frontend
