#!/usr/bin/env python3
"""
PDF Parser - Robust table extraction using pdfplumber
Extracts reservations from Albert Brussels PDF format
"""

from typing import List, Dict, Any
from datetime import date as Date
import re
import uuid
import hashlib


class ReservationParser:
    """Parse reservation PDF using pdfplumber for robust table extraction."""
    
    def __init__(self, service_date: Date, service_label: str, debug: bool = False):
        self.service_date = service_date
        self.service_label = service_label
        self.debug = debug
    
    def parse_pdf(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """Parse PDF and extract reservations using pdfplumber."""
        try:
            import pdfplumber
            from io import BytesIO
        except ImportError:
            raise ImportError("pdfplumber not installed. Run: pip install pdfplumber")
        
        reservations = []
        
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                if self.debug:
                    print(f"\n[DEBUG] Processing page {page_num + 1}")
                
                # Extract tables from page
                tables = page.extract_tables()
                
                for table_idx, table in enumerate(tables):
                    if not table or len(table) < 2:
                        continue
                    
                    if self.debug:
                        print(f"[DEBUG] Table {table_idx + 1}: {len(table)} rows")
                    
                    # Find header row (contains "Heure", "Pax", "Client")
                    header_idx = self._find_header_row(table)
                    if header_idx is None:
                        continue
                    
                    header = table[header_idx]
                    
                    # Find column indices
                    col_heure = self._find_column(header, ["Heure"])
                    col_pax = self._find_column(header, ["Pax"])
                    col_client = self._find_column(header, ["Client"])
                    
                    if col_heure is None or col_pax is None or col_client is None:
                        if self.debug:
                            print(f"[DEBUG] Missing columns in table {table_idx + 1}")
                        continue
                    
                    if self.debug:
                        print(f"[DEBUG] Columns: Heure={col_heure}, Pax={col_pax}, Client={col_client}")
                    
                    # Parse data rows
                    for row_idx in range(header_idx + 1, len(table)):
                        row = table[row_idx]
                        
                        # Skip empty rows or comment rows
                        if not row or len(row) <= max(col_heure, col_pax, col_client):
                            continue
                        
                        heure = self._clean_cell(row[col_heure])
                        pax = self._clean_cell(row[col_pax])
                        client = self._clean_cell(row[col_client])
                        
                        # Skip if it's a comment row
                        if not heure or "Commentaire" in (client or ""):
                            continue
                        
                        # Validate time format (HH:MM)
                        if not re.match(r'^\d{1,2}:\d{2}$', heure):
                            continue
                        
                        # Validate pax (1-30)
                        try:
                            pax_int = int(pax)
                            if pax_int < 1 or pax_int > 30:
                                continue
                        except (ValueError, TypeError):
                            continue
                        
                        # Extract client name (first line before phone)
                        client_name = self._extract_client_name(client)
                        
                        if not client_name:
                            client_name = f"Client {len(reservations) + 1}"
                        
                        # Create reservation
                        res_id = self._generate_id(heure, pax_int, client_name, len(reservations))
                        
                        reservation = {
                            "id": res_id,
                            "client_name": client_name,
                            "pax": pax_int,
                            "arrival_time": heure,
                            "notes": "",
                            "status": "confirmed"
                        }
                        
                        reservations.append(reservation)
                        
                        if self.debug:
                            print(f"  ✅ {heure} | {pax_int} pax | {client_name}")
        
        if self.debug:
            print(f"\n[DEBUG] Total: {len(reservations)} reservations, {sum(r['pax'] for r in reservations)} covers")
        
        return reservations
    
    def _find_header_row(self, table: List[List[str]]) -> int:
        """Find the row containing column headers."""
        for idx, row in enumerate(table):
            if not row:
                continue
            row_text = " ".join(str(cell or "") for cell in row).lower()
            if "heure" in row_text and "pax" in row_text and "client" in row_text:
                return idx
        return None
    
    def _find_column(self, header: List[str], keywords: List[str]) -> int:
        """Find column index by keyword."""
        for idx, cell in enumerate(header):
            if not cell:
                continue
            cell_lower = str(cell).lower()
            for keyword in keywords:
                if keyword.lower() in cell_lower:
                    return idx
        return None
    
    def _clean_cell(self, cell: Any) -> str:
        """Clean cell content."""
        if cell is None:
            return ""
        return str(cell).strip()
    
    def _extract_client_name(self, client_text: str) -> str:
        """Extract client name from cell (first line, before phone)."""
        if not client_text:
            return ""
        
        # Split by newline and take first line
        lines = client_text.split('\n')
        if not lines:
            return ""
        
        name = lines[0].strip()
        
        # Remove phone number if present
        name = re.sub(r'Téléphone:.*', '', name).strip()
        name = re.sub(r'\+\d+.*', '', name).strip()
        
        # Clean up
        name = name.strip()
        
        return name if len(name) >= 2 else ""
    
    def _generate_id(self, heure: str, pax: int, client_name: str, index: int) -> str:
        """Generate deterministic UUID for reservation."""
        content = f"{self.service_date}_{self.service_label}_{heure}_{pax}_{client_name}_{index}"
        hash_val = hashlib.md5(content.encode()).hexdigest()
        return str(uuid.UUID(hash_val))
