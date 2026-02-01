#!/usr/bin/env python3
"""
PDF Parser V4 - ROBUST
Handles both coherent and incoherent time-pax-name structures
"""

from typing import List, Dict, Any, Optional
from datetime import date as Date
import re
import hashlib
import uuid


class ReservationParserV4:
    """Parse reservation PDF with robust block detection."""
    
    def __init__(self, service_date: Date, service_label: str, debug: bool = False):
        self.service_date = service_date
        self.service_label = service_label
        self.debug = debug
        
        # Patterns
        self.RE_TIME = re.compile(r"^\d{1,2}:\d{2}$")
        self.RE_PAX = re.compile(r"^\d{1,2}$")
        self.RE_PHONE = re.compile(r"Téléphone:|^\+\d{2}|^0\d{1,2}\s|\d{4}$")
        self.RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")
        
        self.NOISE_VALUES = {
            "Commentaire du client", "Confirmé", "Annulé", "-", "Web", "Google", 
            "Phone", "En attente", "Pending", "Confirmed", "Cancelled", "Source",
            "Table", "Statut", "Date", "Création", "Heure", "Pax", "Client"
        }
    
    def parse_pdf(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """Parse PDF and extract reservations."""
        from pdfminer.high_level import extract_text
        from io import BytesIO
        
        text = extract_text(BytesIO(pdf_bytes))
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        
        if self.debug:
            print(f"[DEBUG] Total lines: {len(lines)}")
        
        # Find data start
        data_start = self._find_data_start(lines)
        if data_start is None:
            return []
        
        if self.debug:
            print(f"[DEBUG] Data starts at line {data_start}")
        
        # Parse blocks
        reservations = self._parse_blocks(lines, data_start)
        
        if self.debug:
            print(f"[DEBUG] Total: {len(reservations)} reservations, {sum(r['pax'] for r in reservations)} covers")
        
        return reservations
    
    def _find_data_start(self, lines: List[str]) -> Optional[int]:
        """Find where reservation data starts (after 'Source' header)."""
        for i, ln in enumerate(lines):
            if ln == "Source":
                # Find first time after Source
                for j in range(i+1, min(i+20, len(lines))):
                    if self.RE_TIME.match(lines[j]):
                        return j
        return None
    
    def _parse_blocks(self, lines: List[str], start_idx: int) -> List[Dict[str, Any]]:
        """
        Parse all reservation blocks.
        
        Algorithm:
        1. Detect groups of consecutive identical times
        2. Extract N pax values after times
        3. Extract up to N names after pax (may be less)
        4. Create reservations intelligently
        """
        reservations = []
        i = start_idx
        block_num = 0
        
        while i < len(lines):
            if self.RE_TIME.match(lines[i]):
                block_num += 1
                
                # Step 1: Collect consecutive identical times
                time_val = lines[i]
                time_indices = [i]
                j = i + 1
                while j < len(lines) and lines[j] == time_val:
                    time_indices.append(j)
                    j += 1
                
                time_count = len(time_indices)
                
                if self.debug:
                    print(f"\n[Block {block_num}] {time_count}× {time_val} (lines {i}-{j-1})")
                
                # Step 2: Extract ALL consecutive pax values (not limited to time_count)
                # This handles cases like: 1 time with 5 pax = 5 reservations at same time
                pax_values = []
                while j < len(lines):
                    if self.RE_PAX.match(lines[j]):
                        try:
                            val = int(lines[j])
                            if 1 <= val <= 30:
                                pax_values.append(val)
                                j += 1
                            else:
                                break
                        except ValueError:
                            break
                    else:
                        break  # Stop at first non-pax line
                
                if not pax_values:
                    if self.debug:
                        print(f"  ⚠️  No pax found, skipping")
                    i = j
                    continue
                
                if self.debug:
                    print(f"  PAX: {pax_values} (total: {sum(pax_values)})")
                
                # Step 3: Extract names (try to get time_count names, but may get less)
                names = []
                noise_count = 0
                max_noise = 30  # Allow more noise between names
                
                while len(names) < time_count and j < len(lines) and noise_count < max_noise:
                    ln = lines[j]
                    
                    # Skip noise
                    if self._is_noise(ln):
                        noise_count += 1
                        j += 1
                        continue
                    
                    # Stop if we hit another time (next block)
                    if self.RE_TIME.match(ln):
                        break
                    
                    # This is a potential name
                    if len(ln) >= 2:
                        cleaned = self._clean_name(ln)
                        if cleaned:
                            names.append(cleaned)
                            noise_count = 0  # Reset noise counter
                    
                    j += 1
                
                if self.debug:
                    print(f"  NAMES: {names[:3]}{'...' if len(names) > 3 else ''} ({len(names)} total)")
                
                # Step 4: Create reservations
                # Strategy: Match pax with names as much as possible
                
                # Special case: 1 unique time with multiple pax = multiple reservations at same time
                if time_count == 1 and len(pax_values) > 1:
                    # Create 1 reservation per pax (multiple reservations at same time)
                    for idx, pax in enumerate(pax_values):
                        name = names[idx] if idx < len(names) else f"Client {block_num}-{idx+1}"
                        res = self._create_reservation(time_val, pax, name, block_num, idx)
                        reservations.append(res)
                        if self.debug:
                            print(f"    ✅ Res {idx+1}: {name} ({pax} pax)")
                
                elif len(names) == len(pax_values):
                    # Perfect match: 1 name per pax
                    for idx, (pax, name) in enumerate(zip(pax_values, names)):
                        res = self._create_reservation(time_val, pax, name, block_num, idx)
                        reservations.append(res)
                        if self.debug:
                            print(f"    ✅ Res {idx+1}: {name} ({pax} pax)")
                
                elif len(names) == 1 and len(pax_values) > 1 and time_count > 1:
                    # One name for multiple pax AND multiple times: likely a group reservation
                    # Create ONE reservation with total pax
                    total_pax = sum(pax_values)
                    res = self._create_reservation(time_val, total_pax, names[0], block_num, 0)
                    reservations.append(res)
                    if self.debug:
                        print(f"    ✅ Group: {names[0]} ({total_pax} pax total)")
                
                elif len(names) < len(pax_values):
                    # More pax than names: match what we can, group the rest
                    for idx, name in enumerate(names):
                        pax = pax_values[idx] if idx < len(pax_values) else 2
                        res = self._create_reservation(time_val, pax, name, block_num, idx)
                        reservations.append(res)
                        if self.debug:
                            print(f"    ✅ Res {idx+1}: {name} ({pax} pax)")
                    
                    # Remaining pax without names
                    if len(names) < len(pax_values):
                        remaining_pax = sum(pax_values[len(names):])
                        if remaining_pax > 0:
                            res = self._create_reservation(time_val, remaining_pax, 
                                                          f"Groupe {block_num}", block_num, len(names))
                            reservations.append(res)
                            if self.debug:
                                print(f"    ⚠️  Remaining: Groupe {block_num} ({remaining_pax} pax)")
                
                else:
                    # More names than pax: match what we can
                    for idx, pax in enumerate(pax_values):
                        name = names[idx] if idx < len(names) else f"Client {block_num}-{idx+1}"
                        res = self._create_reservation(time_val, pax, name, block_num, idx)
                        reservations.append(res)
                        if self.debug:
                            print(f"    ✅ Res {idx+1}: {name} ({pax} pax)")
                
                i = j
            else:
                i += 1
        
        return reservations
    
    def _is_noise(self, ln: str) -> bool:
        """Check if line is noise."""
        return (ln in self.NOISE_VALUES or
                self.RE_PHONE.search(ln) is not None or
                self.RE_DATE.match(ln) is not None or
                len(ln) < 2)
    
    def _clean_name(self, raw: str) -> str:
        """Clean client name."""
        name = raw.strip()
        
        # Remove status keywords
        for sep in ["Confirmé", "Annulé", "En attente", "Pending", "Confirmed", "Cancelled"]:
            if sep in name:
                name = name.split(sep)[0].strip()
        
        # Remove phone fragments
        name = re.sub(r'\d{4}', '', name).strip()
        
        # Remove special chars
        name = re.sub(r'[_\-]{2,}', ' ', name).strip()
        
        return name if len(name) >= 2 else ""
    
    def _create_reservation(self, time: str, pax: int, name: str, block: int, idx: int) -> Dict[str, Any]:
        """Create reservation dict."""
        res_id = self._generate_id(block, idx, name, pax, time)
        
        return {
            "id": res_id,
            "client_name": name,
            "pax": pax,
            "service_date": self.service_date.isoformat(),
            "arrival_time": time,
            "drink_formula": "",
            "notes": "",
            "status": "confirmed",
            "final_version": False,
            "on_invoice": False,
            "allergens": "",
            "items": [],
        }
    
    def _generate_id(self, block: int, idx: int, name: str, pax: int, time: str) -> str:
        """Generate deterministic ID."""
        content = f"{block}_{idx}_{name}_{pax}_{time}"
        hash_val = hashlib.md5(content.encode()).hexdigest()
        return str(uuid.UUID(hash_val))


def parse_reservation_pdf_v4(
    pdf_bytes: bytes,
    service_date: Date,
    service_label: str,
    debug: bool = False
) -> Dict[str, Any]:
    """
    Parse reservation PDF (V4 - Robust).
    
    Returns:
        {
            "reservations": List[Dict],
            "stats": {"total_parsed": int, "total_covers": int}
        }
    """
    parser = ReservationParserV4(service_date, service_label, debug)
    reservations = parser.parse_pdf(pdf_bytes)
    
    return {
        "reservations": reservations,
        "stats": {
            "total_parsed": len(reservations),
            "total_covers": sum(r["pax"] for r in reservations)
        }
    }
