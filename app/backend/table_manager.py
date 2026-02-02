"""
Table Manager - Auto-assign reservations to tables
Creates dynamic tables (rect6) as needed
"""

import uuid
import logging
from typing import Dict, List, Any, Tuple
from datetime import time as dtime

logger = logging.getLogger("app.table_manager")


def create_base_plan() -> Dict[str, Any]:
    """Create base floor plan with 11 fixed tables (4 pax each)."""
    tables = []
    
    # 11 tables fixes (4 pax chacune) - disposition en colonnes
    # Colonne gauche: 4 tables
    for i in range(4):
        tables.append({
            "id": str(uuid.uuid4()),
            "kind": "fixed",
            "x": 50,
            "y": 50 + (i * 100),
            "w": 80,
            "h": 80,
            "capacity": 4,
            "locked": True,
            "label": str(i + 1)
        })
    
    # Colonne milieu: 4 tables
    for i in range(4):
        tables.append({
            "id": str(uuid.uuid4()),
            "kind": "fixed",
            "x": 200,
            "y": 50 + (i * 100),
            "w": 80,
            "h": 80,
            "capacity": 4,
            "locked": True,
            "label": str(i + 5)
        })
    
    # Colonne droite: 3 tables
    for i in range(3):
        tables.append({
            "id": str(uuid.uuid4()),
            "kind": "fixed",
            "x": 350,
            "y": 50 + (i * 100),
            "w": 80,
            "h": 80,
            "capacity": 4,
            "locked": True,
            "label": str(i + 9)
        })
    
    return {
        "room": {"width": 1000, "height": 600},
        "tables": tables
    }


def auto_assign_tables(plan_data: Dict[str, Any], reservations: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Auto-assign reservations to tables.
    Creates rect6 tables dynamically as needed.
    
    Returns: (updated_plan_data, assignments)
    """
    logger.info(f"Auto-assign: {len(reservations)} reservations")
    
    # Sort reservations by pax descending (First-Fit Decreasing)
    sorted_res = sorted(reservations, key=lambda r: (-r['pax'], r['arrival_time']))
    
    # Available tables
    tables = plan_data.get("tables", [])
    avail_fixed = {t["id"]: t for t in tables if t.get("kind") == "fixed"}
    avail_rect = {t["id"]: t for t in tables if t.get("kind") == "rect"}
    
    assignments = {}
    created_tables = []
    
    for res in sorted_res:
        pax = res['pax']
        res_id = res['id']
        name = res['client_name']
        
        assigned = False
        
        # 1) Small groups (1-4 pax): Use fixed tables
        if pax <= 4 and avail_fixed:
            # Find best-fit fixed table
            best = None
            for tid, t in avail_fixed.items():
                if t.get("capacity", 4) >= pax:
                    best = tid
                    break
            
            if best:
                assignments[best] = {
                    "res_id": res_id,
                    "name": name.upper(),
                    "pax": pax
                }
                del avail_fixed[best]
                assigned = True
                logger.debug(f"Assigned {name} ({pax} pax) to fixed table {best}")
        
        if assigned:
            continue
        
        # 2) Medium groups (5-8 pax): Use existing rect table
        if pax <= 8 and avail_rect:
            best = None
            for tid, t in avail_rect.items():
                cap = t.get("capacity", 6)
                cap_ext = min(8, cap + 2)
                if cap_ext >= pax:
                    best = tid
                    break
            
            if best:
                assignments[best] = {
                    "res_id": res_id,
                    "name": name.upper(),
                    "pax": pax
                }
                del avail_rect[best]
                assigned = True
                logger.debug(f"Assigned {name} ({pax} pax) to rect table {best}")
        
        if assigned:
            continue
        
        # 3) Large groups (9+ pax): CREATE rect6 tables
        num_tables_needed = (pax + 7) // 8  # 8 pax max per table with extension
        
        # Find spot for new tables (zone centrale blanche)
        base_x = 500
        base_y = 50 + (len(created_tables) * 80)
        
        new_tables = []
        for i in range(num_tables_needed):
            new_id = str(uuid.uuid4())
            new_table = {
                "id": new_id,
                "kind": "rect",
                "x": base_x + (i * 130),
                "y": base_y,
                "w": 120,
                "h": 60,
                "capacity": 6,
                "label": f"T{len(created_tables) + i + 1}"
            }
            new_tables.append(new_table)
            created_tables.append(new_table)
        
        # Assign pax across new tables
        remaining = pax
        for t in new_tables:
            pax_on_table = min(8, remaining)
            assignments[t["id"]] = {
                "res_id": res_id,
                "name": name.upper(),
                "pax": pax_on_table
            }
            remaining -= pax_on_table
        
        assigned = True
        logger.info(f"Created {len(new_tables)} rect6 tables for {name} ({pax} pax)")
    
    # Add created tables to plan
    plan_data["tables"].extend(created_tables)
    
    logger.info(f"Auto-assign complete: {len(assignments)} table assignments, {len(created_tables)} tables created")
    
    return plan_data, {"tables": assignments}
