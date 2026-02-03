#!/usr/bin/env python3
"""
Test local de l'auto-assign pour vérifier la création dynamique de tables
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from backend.routers.floorplan import _auto_assign, _find_spot_for_table
from datetime import time as dtime
from types import SimpleNamespace

# Plan de test simple
plan_data = {
    "room": {"width": 1200, "height": 800, "grid": 50},
    "tables": [
        {"id": "t1", "kind": "fixed", "x": 100, "y": 100, "w": 80, "h": 80, "capacity": 4, "locked": False},
        {"id": "t2", "kind": "fixed", "x": 200, "y": 100, "w": 80, "h": 80, "capacity": 4, "locked": False},
    ],
    "walls": [],
    "columns": [],
    "fixtures": [],
    "no_go": [],
    "round_only_zones": [],
    "rect_only_zones": []
}

# Réservations de test (beaucoup plus que les 2 tables existantes)
reservations = [
    SimpleNamespace(id="r1", client_name="Client 1", pax=4, arrival_time=dtime(11, 0)),
    SimpleNamespace(id="r2", client_name="Client 2", pax=6, arrival_time=dtime(11, 15)),
    SimpleNamespace(id="r3", client_name="Client 3", pax=8, arrival_time=dtime(11, 30)),
    SimpleNamespace(id="r4", client_name="Client 4", pax=10, arrival_time=dtime(11, 45)),
    SimpleNamespace(id="r5", client_name="Client 5", pax=12, arrival_time=dtime(12, 0)),
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
for table_id, assignment in assignments.get('tables', {}).items():
    print(f"    - Table {table_id}: {assignment.get('name')} ({assignment.get('pax')} pax)")

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
