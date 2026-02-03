#!/usr/bin/env python3
"""
Test parser PDF avec pdfplumber (meilleur pour tableaux)
"""
import pdfplumber
import re

pdf_file = r"c:\Users\thib\Desktop\applificvhe cuisine\77c7e340-62f8-4a95-aa5f-3af26d52b7e1.pdf"

print("=" * 80)
print("🧪 TEST EXTRACTION PDF AVEC PDFPLUMBER")
print("=" * 80)

with pdfplumber.open(pdf_file) as pdf:
    print(f"\nNombre de pages: {len(pdf.pages)}")
    
    for page_num, page in enumerate(pdf.pages, 1):
        print(f"\n📄 PAGE {page_num}")
        print("=" * 80)
        
        # Extraire le texte brut
        text = page.extract_text()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        print(f"Lignes de texte: {len(lines)}")
        
        # Extraire les tableaux
        tables = page.extract_tables()
        print(f"Tableaux trouvés: {len(tables)}")
        
        if tables:
            for table_num, table in enumerate(tables, 1):
                print(f"\n📊 TABLEAU {table_num} ({len(table)} lignes x {len(table[0]) if table else 0} colonnes)")
                print("-" * 80)
                
                # Afficher les 20 premières lignes du tableau
                for i, row in enumerate(table[:20]):
                    # Nettoyer les cellules None
                    clean_row = [str(cell).strip() if cell else "" for cell in row]
                    print(f"{i:2d}: {' | '.join(clean_row[:7])}")  # Max 7 colonnes
                
                # Chercher les réservations (lignes avec heure + pax + nom)
                print(f"\n🔍 PARSING DES RÉSERVATIONS...")
                re_time = re.compile(r"^\d{1,2}:\d{2}$")
                re_pax = re.compile(r"^\d{1,2}$")
                
                reservations = []
                for i, row in enumerate(table):
                    if not row or len(row) < 3:
                        continue
                    
                    # Nettoyer
                    clean_row = [str(cell).strip() if cell else "" for cell in row]
                    
                    # Détecter les colonnes heure/pax/nom
                    # Peut être: [Heure, Pax, ..., Nom, ...] (format page 1 avec 17 cols)
                    # Ou: [Heure, Pax, Nom, ...] (format page 2/3 avec 7 cols)
                    heure_idx = None
                    pax_idx = None
                    nom_idx = None
                    
                    for idx, cell in enumerate(clean_row[:7]):  # Chercher dans les 7 premières colonnes
                        if cell and re_time.match(cell):
                            heure_idx = idx
                        elif cell and re_pax.match(cell) and heure_idx is not None:
                            pax_idx = idx
                        elif cell and len(cell) >= 2 and any(c.isupper() for c in cell) and heure_idx is not None and pax_idx is not None:
                            # Première cellule avec majuscules après heure+pax = probablement le nom
                            if nom_idx is None and not cell.startswith('Commentaire'):
                                nom_idx = idx
                                break
                    
                    # Valider et extraire
                    if heure_idx is not None and pax_idx is not None and nom_idx is not None:
                        heure = clean_row[heure_idx]
                        pax_str = clean_row[pax_idx]
                        nom = clean_row[nom_idx]
                        
                        try:
                            pax = int(pax_str)
                            if 1 <= pax <= 30 and nom and len(nom) >= 2:
                                # Nettoyer le nom
                                nom_clean = nom.split('\n')[0]  # Prendre première ligne
                                nom_clean = nom_clean.split('Téléphone')[0].strip()
                                
                                # Filtrer les mots-clés commentaires
                                if nom_clean.lower() not in ['commentaire', 'confirmé', 'web', 'google']:
                                    reservations.append({
                                        'heure': heure,
                                        'pax': pax,
                                        'nom': nom_clean
                                    })
                        except ValueError:
                            pass
                
                print(f"\n✅ RÉSERVATIONS TROUVÉES: {len(reservations)}")
                total_pax = sum(r['pax'] for r in reservations)
                print(f"📊 TOTAL PAX: {total_pax}")
                
                for i, r in enumerate(reservations, 1):
                    print(f"{i:2d}. {r['heure']:5s} | {r['pax']:2d} pax | {r['nom'][:40]}")

print("\n✨ Test terminé!")
