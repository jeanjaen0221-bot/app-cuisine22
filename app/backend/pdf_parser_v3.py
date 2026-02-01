"""
Robust PDF parser for Albert Brussels - Version 3
Extracts ALL reservation blocks, not just the first one.
"""

import re
import uuid
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, time as dtime
from pdfminer.high_level import extract_text
import io


class ReservationParserV3:
    """Parse Albert Brussels PDF with multiple reservation blocks."""
    
    RE_TIME = re.compile(r"^\d{1,2}:\d{2}$")
    RE_PAX = re.compile(r"^\d{1,2}$")
    RE_PHONE = re.compile(r"Téléphone:|^\+\d{2}|^0\d{1,2}\s|^\d{4}$")
    RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")
    
    NOISE_VALUES = {
        "Commentaire du client",
        "Confirmé", "Annulé", "En attente",
        "Pending", "Confirmed", "Cancelled",
        "-", "Web", "Google", "Phone", "Téléphone", "Email",
    }
    
    def __init__(self, service_date: date, service_label: Optional[str] = None, debug: bool = False):
        self.service_date = service_date
        self.service_label = service_label
        self.debug = debug
        self.default_time = dtime(12, 30) if (service_label or "").lower() == "lunch" else dtime(19, 0)
    
    def parse_pdf(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """Parse PDF and extract all reservations."""
        text = extract_text(io.BytesIO(pdf_bytes))
        lines = [ln.strip() for l in text.splitlines() if (ln := l.strip())]
        
        if self.debug:
            print(f"[DEBUG] Total lines: {len(lines)}")
        
        # Find where reservation data starts
        data_start = self._find_data_start(lines)
        if data_start is None:
            return []
        
        if self.debug:
            print(f"[DEBUG] Data starts at line {data_start}")
        
        # Find all time entry indices in the data section
        time_indices = self._find_time_blocks(lines, data_start)
        
        if self.debug:
            print(f"[DEBUG] Found {len(time_indices)} time entries")
        
        # Extract one reservation per time entry
        all_reservations = []
        for time_idx in time_indices:
            reservations = self._extract_block(lines, time_idx)
            all_reservations.extend(reservations)
        
        if self.debug:
            print(f"[DEBUG] Total: {len(all_reservations)} reservations extracted")
        
        if self.debug:
            print(f"\n[DEBUG] Total: {len(all_reservations)} reservations")
        
        return all_reservations
    
    def _find_data_start(self, lines: List[str]) -> Optional[int]:
        """Find where reservation data starts (after 'Source' header)."""
        for i, ln in enumerate(lines):
            if ln == "Source":
                # Find first time after Source
                for j in range(i+1, min(i+20, len(lines))):
                    if self.RE_TIME.match(lines[j]):
                        return j
        return None
    
    def _find_time_blocks(self, lines: List[str], start_idx: int) -> List[int]:
        """
        Find ALL time entry indices (not blocks, individual times).
        Each time entry is a potential reservation.
        """
        time_indices = []
        for i in range(start_idx, len(lines)):
            if self.RE_TIME.match(lines[i]):
                time_indices.append(i)
        return time_indices
    
    def _extract_block(self, lines: List[str], time_idx: int) -> List[Dict[str, Any]]:
        """
        Extract ONE reservation starting at time_idx.
        
        Structure (line-by-line):
        - Line N: Time (HH:MM)
        - Line N+1 to N+10: Search for pax (1-30)
        - After pax: Search for name (skip noise)
        """
        time_val = lines[time_idx]
        
        # Search for pax in next 10 lines
        pax_val = None
        pax_idx = None
        for j in range(time_idx + 1, min(time_idx + 10, len(lines))):
            if self.RE_PAX.match(lines[j]):
                try:
                    val = int(lines[j])
                    if 1 <= val <= 30:
                        pax_val = val
                        pax_idx = j
                        break
                except ValueError:
                    pass
        
        if not pax_val:
            return []
        
        # Search for name after pax (skip noise)
        name_val = None
        for j in range(pax_idx + 1, min(pax_idx + 10, len(lines))):
            ln = lines[j]
            
            # Skip noise
            if (ln in self.NOISE_VALUES or
                self.RE_PHONE.search(ln) or
                self.RE_DATE.match(ln) or
                len(ln) < 2):
                continue
            
            # This is a name
            name_val = self._clean_name(ln)
            break
        
        if not name_val:
            return []
        
        # Create reservation
        res_id = self._generate_id(time_idx, name_val, pax_val, time_val)
        reservation = {
            "id": res_id,
            "client_name": name_val,
            "pax": pax_val,
            "service_date": self.service_date.isoformat(),
            "arrival_time": time_val,
            "drink_formula": "",
            "notes": "",
            "status": "confirmed",
            "final_version": False,
            "on_invoice": False,
            "allergens": "",
            "items": [],
        }
        
        return [reservation]
    
    def _generate_id(self, idx: int, name: str, pax: int, time: str) -> str:
        """Generate deterministic ID for reservation."""
        import hashlib
        import uuid
        content = f"{idx}_{name}_{pax}_{time}"
        hash_val = hashlib.md5(content.encode()).hexdigest()
        return str(uuid.UUID(hash_val))
    
    def _clean_name(self, raw: str) -> str:
        """Clean client name."""
        name = raw
        
        # Remove status
        for sep in ["Confirmé", "Annulé", "En attente", "Pending", "Confirmed", "Cancelled"]:
            if sep in name:
                name = name.split(sep)[0]
                break
        
        # Remove "Table"
        if "Table" in name:
            name = name.split("Table")[0]
        
        # Remove dates and times
        name = re.sub(r"\d{4}-\d{2}-\d{2}", "", name)
        name = re.sub(r"\d{2}/\d{2}/\d{4}", "", name)
        name = re.sub(r"\d{2}:\d{2}", "", name)
        
        # Remove phones
        name = re.sub(r"\+\d{2,}[\d\s()-]+", "", name)
        name = re.sub(r"\b0\d[\d\s()-]{7,}", "", name)
        
        # Remove sources
        for src in ["Web", "Google", "Phone", "Téléphone", "Email"]:
            name = name.replace(src, "")
        
        # Clean whitespace
        name = name.strip(" -,|")
        name = re.sub(r"\s+", " ", name)
        name = re.sub(r"\s+\d{1,3}$", "", name)
        
        return name.strip()
    
    def _match_reservations(self, times: List[str], pax_values: List[int], names: List[str]) -> List[Dict[str, Any]]:
        """Match times, pax, names into reservations."""
        reservations = []
        count = min(len(times), len(pax_values), len(names))
        
        for i in range(count):
            time_str = times[i]
            pax = pax_values[i]
            client_name = names[i]
            
            # Parse time
            try:
                hh, mm = time_str.split(":")
                arrival_time = dtime(int(hh), int(mm))
            except Exception:
                arrival_time = self.default_time
            
            # Generate deterministic ID
            content = f"{len(reservations)}_{client_name}_{pax}_{arrival_time.hour:02d}:{arrival_time.minute:02d}"
            hash_val = hashlib.md5(content.encode()).hexdigest()
            res_id = str(uuid.UUID(hash_val))
            
            reservation = {
                "id": res_id,
                "client_name": client_name,
                "pax": pax,
                "service_date": self.service_date.isoformat(),
                "arrival_time": f"{arrival_time.hour:02d}:{arrival_time.minute:02d}",
                "drink_formula": "",
                "notes": "",
                "status": "confirmed",
                "final_version": False,
                "on_invoice": False,
                "allergens": "",
                "items": [],
            }
            
            reservations.append(reservation)
        
        return reservations


def parse_reservation_pdf_v3(
    pdf_bytes: bytes,
    service_date: date,
    service_label: Optional[str] = None,
    debug: bool = False
) -> Dict[str, Any]:
    """Parse reservation PDF v3 - extracts all blocks."""
    parser = ReservationParserV3(service_date, service_label, debug)
    reservations = parser.parse_pdf(pdf_bytes)
    
    return {
        "reservations": reservations,
        "stats": {
            "total_parsed": len(reservations),
            "service_date": service_date.isoformat(),
            "service_label": service_label or "unknown",
        },
    }
