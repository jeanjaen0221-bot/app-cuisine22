#!/usr/bin/env python3
"""
Test local de l'auto-assign pour vérifier la création dynamique de tables
Simule exactement la situation: 30 réservations, 11 tables existantes
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from backend.routers.floorplan import _auto_assign, _find_spot_for_table
from datetime import time as dtime
from types import SimpleNamespace

# Plan de test réaliste: 11 tables comme dans ton cas
plan_data = {
    "room": {"width": 1600, "height": 1000, "grid": 50},
    "tables": [
        # 8 tables fixes (4 pax chacune)
        {"id": "f1", "kind": "fixed", "x": 50, "y": 50, "w": 80, "h": 80, "capacity": 4, "locked": False},
        {"id": "f2", "kind": "fixed", "x": 50, "y": 150, "w": 80, "h": 80, "capacity": 4, "locked": False},
        {"id": "f3", "kind": "fixed", "x": 50, "y": 250, "w": 80, "h": 80, "capacity": 4, "locked": False},
        {"id": "f4", "kind": "fixed", "x": 50, "y": 350, "w": 80, "h": 80, "capacity": 4, "locked": False},
        {"id": "f5", "kind": "fixed", "x": 150, "y": 50, "w": 80, "h": 80, "capacity": 4, "locked": False},
        {"id": "f6", "kind": "fixed", "x": 150, "y": 150, "w": 80, "h": 80, "capacity": 4, "locked": False},
        {"id": "f7", "kind": "fixed", "x": 150, "y": 250, "w": 80, "h": 80, "capacity": 4, "locked": False},
        {"id": "f8", "kind": "fixed", "x": 150, "y": 350, "w": 80, "h": 80, "capacity": 4, "locked": False},
        # 2 tables rect (6 pax)
        {"id": "r1", "kind": "rect", "x": 250, "y": 50, "w": 120, "h": 60, "capacity": 6, "locked": False},
        {"id": "r2", "kind": "rect", "x": 250, "y": 150, "w": 120, "h": 60, "capacity": 6, "locked": False},
        # 1 table ronde (10 pax)
        {"id": "rnd1", "kind": "round", "x": 450, "y": 150, "r": 50, "capacity": 10, "locked": False},
    ],
    "walls": [],
    "columns": [],
    "fixtures": [],
    "no_go": [],
    "round_only_zones": [],
    "rect_only_zones": [],
    "max_dynamic_tables": {"rect": 10, "round": 5}  # Stock disponible
}

# 30 réservations réalistes (différentes tailles)
reservations = [
    SimpleNamespace(id=f"r{i}", client_name=f"Client {i}", pax=pax, arrival_time=dtime(11 + i//6, (i % 6) * 10))
    for i, pax in enumerate([
        2, 2, 2, 3, 3, 4, 4, 4, 4, 4,  # 10 petites (2-4 pax)
        6, 6, 6, 6, 8, 8,              # 6 moyennes (6-8 pax)
        10, 10, 12, 12,                # 4 grandes (10-12 pax)
        14, 14, 15, 15,                # 4 très grandes (14-15 pax)
        1, 1, 2, 3, 5, 7               # 6 variées
    ])
]

print("=" * 80)
print("🧪 TEST AUTO-ASSIGN AVEC CRÉATION DYNAMIQUE DE TABLES")
print("=" * 80)

print(f"\n📊 État AVANT auto-assign:")
print(f"  Tables existantes: {len(plan_data['tables'])}")
for t in plan_data['tables']:
    print(f"    - {t['id']}: {t['kind']} {t['capacity']} pax @ ({t['x']}, {t['y']})")

print(f"\n📋 Réservations à placer: {len(reservations)}")
for r in reservations:
    print(f"  - {r.client_name}: {r.pax} pax @ {r.arrival_time}")

print(f"\n🔧 Test _find_spot_for_table...")
spot_rect = _find_spot_for_table(plan_data, "rect", w=120, h=60)
print(f"  Spot pour table rect: {spot_rect}")

spot_round = _find_spot_for_table(plan_data, "round", r=50)
print(f"  Spot pour table round: {spot_round}")

print(f"\n⚙️  Exécution auto-assign...")
assignments = _auto_assign(plan_data, reservations)

print(f"\n📊 État APRÈS auto-assign:")
print(f"  Tables totales: {len(plan_data['tables'])}")
tables_created = len(plan_data['tables']) - 2
print(f"  Tables créées dynamiquement: {tables_created}")

print(f"\n📋 Nouvelles tables créées:")
for t in plan_data['tables'][2:]:  # Skip les 2 premières (existantes)
    print(f"  - {t['id']}: {t['kind']} {t.get('capacity', 0)} pax @ ({t.get('x', 0)}, {t.get('y', 0)})")

print(f"\n✅ Assignations:")
print(f"  Tables assignées: {len(assignments.get('tables', {}))}")

# Vérifier si tables réutilisées (BUG!)
table_usage = {}
for table_id, assignment in assignments.get('tables', {}).items():
    res_id = assignment.get('res_id')
    if table_id in table_usage:
        print(f"  ❌ BUG! Table {table_id} RÉUTILISÉE: {table_usage[table_id]} ET {res_id}")
    else:
        table_usage[table_id] = res_id
    print(f"    - Table {table_id}: {assignment.get('name')} ({assignment.get('pax')} pax) [res={res_id}]")

# Vérifier réservations non assignées
assigned_res_ids = {a.get('res_id') for a in assignments.get('tables', {}).values()}
unassigned = [r for r in reservations if str(r.id) not in assigned_res_ids]
if unassigned:
    print(f"\n❌ {len(unassigned)} réservations NON ASSIGNÉES:")
    for r in unassigned[:5]:  # Montrer les 5 premières
        print(f"    - {r.client_name}: {r.pax} pax")
else:
    print(f"\n✅ Toutes les réservations assignées!")

print(f"\n📈 Résumé:")
print(f"  Réservations: {len(reservations)}")
print(f"  Tables avant: 2")
print(f"  Tables après: {len(plan_data['tables'])}")
print(f"  Tables créées: {tables_created}")
print(f"  Assignations: {len(assignments.get('tables', {}))}")

if tables_created > 0:
    print(f"\n✅ SUCCESS: {tables_created} nouvelle(s) table(s) créée(s) dynamiquement!")
else:
    print(f"\n❌ PROBLEM: Aucune table créée malgré {len(reservations)} réservations et seulement 2 tables fixes!")

print("\n" + "=" * 80)
