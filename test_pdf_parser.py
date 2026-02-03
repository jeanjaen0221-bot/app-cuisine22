#!/usr/bin/env python3
"""
Script de test pour parser PDF de réservations Albert Brussels
"""
import io
import re
from datetime import time as dtime, date
from typing import List, Dict, Any
import hashlib
import uuid

def test_parse_pdf(pdf_path: str):
    """Parse un PDF et affiche les résultats."""
    
    try:
        from pdfminer.high_level import extract_text
        from pdfminer.layout import LAParams
    except ImportError:
        print("❌ pdfminer.six non installé. Installer avec: pip install pdfminer.six")
        return
    
    print(f"\n📄 Lecture du PDF: {pdf_path}")
    print("=" * 80)
    
    # Lire le fichier
    with open(pdf_path, 'rb') as f:
        blob = f.read()
    
    # Extraire le texte avec LAParams pour préserver les colonnes
    try:
        text = extract_text(io.BytesIO(blob), laparams=LAParams())
    except Exception as e:
        print(f"❌ Erreur extraction: {e}")
        return
    
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    
    print(f"\n📊 Total lignes extraites: {len(lines)}")
    print("\n🔍 Premières 50 lignes:")
    print("-" * 80)
    for i, ln in enumerate(lines[:50], 1):
        print(f"{i:3d}: {ln[:120]}")
    
    # Trouver toutes les heures et afficher contexte
    print("\n\n🕐 LIGNES CONTENANT DES HEURES (avec contexte ±3 lignes):")
    print("=" * 80)
    for i, ln in enumerate(lines):
        if re.match(r"^\d{1,2}:\d{2}$", ln):
            print(f"\n--- Heure trouvée à ligne {i}: {ln} ---")
            for j in range(max(0, i-2), min(len(lines), i+8)):
                marker = ">>>" if j == i else "   "
                print(f"{marker} {j:3d}: {lines[j][:120]}")
    
    # Patterns
    re_reservation_line = re.compile(
        r'^(\d{1,2}:\d{2})\s+(\d{1,2})\s+([A-Z][A-Za-z\s-]+?)\s+(?:Téléphone|Confirmé|Annulé|Web|Google|Table|\d{4}-\d{2}-\d{2})'
    )
    re_time = re.compile(r"^\d{1,2}:\d{2}$")
    re_pax = re.compile(r"^\d{1,2}$")
    re_phone = re.compile(r"Téléphone:|^\+\d{2}|^0\d{1,2}\s")
    
    skip_patterns = [
        r"^Nombre de couverts",
        r"^Brunch\s*-\s*Nombre",
        r"^albert brussels",
        r"^Standard",
        r"^\d{2}/\d{2}/\d{4}$",
        r"^Heure$",
        r"^Pax$",
        r"^Client$",
        r"^Table$",
        r"^Statut$",
        r"^Source$",
    ]
    
    def is_valid_client_name(raw: str) -> bool:
        """Valide si c'est vraiment un nom de client."""
        if not raw or len(raw) < 2:
            return False
        
        # Ignorer nombres seuls
        if raw.isdigit():
            return False
        
        # Ignorer mots-clés commentaires
        invalid_keywords = [
            "pregnancy", "végétarien", "vegetarian", "brunch", "formula",
            "personen", "personne", "commentaire", "carte", "chaise haute",
            "allergies", "gluten", "lactose", "verjaardag", "birthday",
            "anniversary", "inschatting", "definitief", "aantal"
        ]
        raw_lower = raw.lower()
        if any(kw in raw_lower for kw in invalid_keywords):
            return False
        
        # Doit contenir au moins 1 lettre majuscule (noms propres)
        if not any(c.isupper() for c in raw):
            return False
        
        # Doit avoir au moins 2 lettres
        letter_count = sum(1 for c in raw if c.isalpha())
        if letter_count < 2:
            return False
        
        return True
    
    def clean_client_name(raw: str) -> str:
        """Nettoie le nom du client."""
        name = raw
        for sep in ["Confirmé", "Annulé", "En attente", "Pending", "Confirmed", "Cancelled"]:
            if sep in name:
                name = name.split(sep)[0]
                break
        if "Table" in name:
            name = name.split("Table")[0]
        name = re.sub(r"\d{4}-\d{2}-\d{2}", "", name)
        name = re.sub(r"\d{2}/\d{2}/\d{4}", "", name)
        name = re.sub(r"\d{2}:\d{2}", "", name)
        name = re.sub(r"\+\d{2,}[\d\s()-]+", "", name)
        name = re.sub(r"\b0\d[\d\s()-]{7,}", "", name)
        for src in ["Web", "Google", "Phone", "Téléphone", "Email"]:
            name = name.replace(src, "")
        name = name.strip(" -,|")
        name = re.sub(r"\s+", " ", name)
        name = re.sub(r"\s+\d{1,3}$", "", name)
        return name.strip()
    
    # Parser
    out: List[Dict[str, Any]] = []
    parsed_horizontal = 0
    parsed_vertical = 0
    skipped_count = 0
    i = 0
    
    print("\n\n🔎 PARSING EN COURS...")
    print("=" * 80)
    
    while i < len(lines):
        ln = lines[i]
        
        # Ignorer en-têtes
        if any(re.search(pat, ln, re.IGNORECASE) for pat in skip_patterns):
            skipped_count += 1
            i += 1
            continue
        
        # Ignorer téléphones/commentaires
        if re_phone.search(ln) or "Commentaire" in ln or ln.startswith("("):
            i += 1
            continue
        
        # MÉTHODE 1: Ligne horizontale complète
        match = re_reservation_line.match(ln)
        if match:
            time_str = match.group(1)
            pax = int(match.group(2))
            client_name = clean_client_name(match.group(3))
            
            if client_name and len(client_name) >= 2:
                out.append({
                    "arrival_time": time_str,
                    "pax": pax,
                    "client_name": client_name,
                    "method": "horizontal"
                })
                parsed_horizontal += 1
                print(f"✅ HORIZONTAL #{parsed_horizontal}: {time_str} | {pax} pax | {client_name}")
            
            i += 1
            continue
        
        # MÉTHODE 2: Vertical (fallback)
        if not re_time.match(ln):
            i += 1
            continue
        
        time_str = ln
        
        # Debug spécial pour 13:00
        if time_str == "13:00":
            print(f"\n🔍 DEBUG 13:00 trouvé à ligne {i}:")
            for j in range(i, min(i+10, len(lines))):
                print(f"  {j:3d}: {lines[j][:80]}")
        
        # Chercher pax
        pax = None
        pax_idx = None
        for j in range(i+1, min(i+6, len(lines))):
            if re_pax.match(lines[j]):
                try:
                    pax_val = int(lines[j])
                    if 1 <= pax_val <= 30:
                        pax = pax_val
                        pax_idx = j
                        break
                except ValueError:
                    pass
        
        if pax is None:
            i += 1
            continue
        
        # Chercher nom
        client_name = None
        for j in range(pax_idx+1, min(pax_idx+6, len(lines))):
            candidate = lines[j]
            if not candidate or len(candidate) < 2:
                continue
            if re_phone.search(candidate):
                continue
            if candidate in ["Commentaire du client", "Confirmé", "Annulé", "-", "Web", "Google", "Phone"]:
                continue
            if re.match(r"^\d{4}-\d{2}-\d{2}", candidate):
                continue
            
            # Valider avant de nettoyer
            if not is_valid_client_name(candidate):
                continue
            
            client_name = clean_client_name(candidate)
            if client_name and len(client_name) >= 2:
                break
        
        if client_name:
            out.append({
                "arrival_time": time_str,
                "pax": pax,
                "client_name": client_name,
                "method": "vertical"
            })
            parsed_vertical += 1
            print(f"✅ VERTICAL   #{parsed_vertical}: {time_str} | {pax} pax | {client_name}")
            i = pax_idx + 1
        else:
            i += 1
    
    # Résumé
    print("\n\n" + "=" * 80)
    print("📊 RÉSUMÉ DU PARSING")
    print("=" * 80)
    print(f"Total lignes traitées: {len(lines)}")
    print(f"Lignes ignorées (en-têtes): {skipped_count}")
    print(f"Réservations parsées (horizontal): {parsed_horizontal}")
    print(f"Réservations parsées (vertical): {parsed_vertical}")
    print(f"TOTAL RÉSERVATIONS: {len(out)}")
    
    if len(out) == 0:
        print("\n❌ AUCUNE RÉSERVATION TROUVÉE!")
        print("\n💡 Suggestions:")
        print("1. Vérifier que le PDF contient bien des lignes comme:")
        print("   11:00 10 NADEIGE Téléphone Confirmé ...")
        print("2. Vérifier l'extraction de texte (voir premières lignes ci-dessus)")
    else:
        print("\n✅ PARSING RÉUSSI!")
        print("\n📋 Détail des réservations:")
        print("-" * 80)
        for i, res in enumerate(out, 1):
            print(f"{i:2d}. {res['arrival_time']:5s} | {res['pax']:2d} pax | {res['client_name']:30s} | [{res['method']}]")
    
    return out

if __name__ == "__main__":
    import sys
    
    pdf_file = r"c:\Users\thib\Desktop\applificvhe cuisine\77c7e340-62f8-4a95-aa5f-3af26d52b7e1.pdf"
    
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
    
    print("\n" + "=" * 80)
    print("🧪 TEST PARSER PDF - ALBERT BRUSSELS")
    print("=" * 80)
    
    results = test_parse_pdf(pdf_file)
    
    print("\n✨ Test terminé!\n")
