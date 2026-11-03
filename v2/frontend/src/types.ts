export type Peut = { fiches: boolean; devis: boolean; devis_valider: boolean; compta: boolean; prix: boolean; admin: boolean }

export type Moi = {
  id: string
  email: string
  nom: string
  role: 'admin' | 'equipe' | 'compta'
  droits: string[]
  peut: Peut
}

export type Option = { cle: string; libelle: string }

export type Produit = {
  id: string
  nom: string
  categorie: string
  unite: string
  unite_libelle: string
  prix_centimes: number | null
  prix: string
  prix_manquant: boolean
  allergenes: string[]
  actif: boolean
  ordre: number
}

export type FormuleRepas = {
  id: string
  nom: string
  comportement: 'services' | 'carte' | 'sans_plats'
  nb_services: number | null
  produit_id: string | null
  prix_centimes: number | null
  prix: string
  actif: boolean
  ordre: number
  utilisee?: boolean
}

export type FormuleBoissons = {
  id: string
  nom: string
  mode: 'formule' | 'consommation' | 'aucune'
  base_produit_id: string | null
  coupe_produit_id: string | null
  base: string | null
  coupe: string | null
  prix_centimes: number | null
  prix: string
  couleur: string
  par_defaut: boolean
  actif: boolean
  ordre: number
  utilisee?: boolean
}

export type References = {
  formules_repas: FormuleRepas[]
  formules_boissons: FormuleBoissons[]
  privatisations: Produit[]
  espaces: string[]
  types_ligne: Option[]
  allergenes: Option[]
  statuts_fiche: Option[]
  heures_proposees: string[]
  unites: Option[]
  categories: Option[]
  couleurs_boissons: string[]
}

export type Client = {
  id: string
  type: 'particulier' | 'entreprise'
  nom: string
  contact_prenom: string | null
  contact_nom: string | null
  email: string | null
  telephone: string | null
  langue: string
  rue: string | null
  numero: string | null
  boite: string | null
  code_postal: string | null
  ville: string | null
  pays: string
  tva: string | null
  reference_po: string | null
  conditions_paiement: string | null
  notes: string | null
  preferences: string | null
  archive: boolean
  version: number
  adresse_complete: boolean
  manques_facturation: string[]
}

export type LigneFiche = {
  id?: string
  type: string
  type_libelle?: string
  libelle: string
  quantite: number
  commentaire: string | null
  produit_id?: string | null
  hors_catalogue?: boolean
}

export type Fiche = {
  id: string
  version: number
  statut: string
  statut_libelle: string
  date: string
  heure: string
  couverts: number
  espace: string
  client: { id: string; nom: string; type: string }
  formule_repas: string | null
  formule_repas_id: string | null
  formule_boissons: string | null
  formule_boissons_id: string | null
  couleur_boissons: string
  privatisation: string | null
  privatisation_id: string | null
  allergenes: string[]
  lignes: LigneFiche[]
  figee: boolean
  alertes: string[]
  notes_salle?: string | null
  notes_cuisine?: string | null
  contact_sur_place?: string | null
  telephone_sur_place?: string | null
  motif_annulation?: string | null
  dernier_pdf_le?: string | null
  tables_salle?: string[]
  devis?: { id: string; numero: string; version: number; statut: string; a_mettre_a_jour: boolean } | null
  bon?: { id: string; numero: string; statut: string } | null
}

export type LigneDocument = {
  id: string
  categorie: string
  libelle: string
  quantite: number
  quantite_devis?: number
  extra?: boolean
  unite: string
  unite_libelle: string
  produit_id?: string | null
  prix_unitaire_centimes: number | null
  prix_unitaire: string
  total_centimes: number | null
  total: string
}

export type Devis = {
  id: string
  numero: string
  version: number
  reference: string
  statut: string
  statut_libelle: string
  expire: boolean
  fiche_id: string
  client_id: string
  client_nom: string
  date_evenement: string
  heure_evenement: string
  couverts: number
  date_validite: string
  total_centimes: number
  total: string
  remarques_client: string | null
  remarques_compta: string | null
  lignes: LigneDocument[]
  manques: string[]
  a_mettre_a_jour: boolean
  transmis_le: string | null
  transmis_par: string | null
  envoye_le: string | null
  reponse_le: string | null
  version_suivante_id: string | null
  cree_le: string
  alertes?: string[]
}

export type Bon = {
  id: string
  numero: string
  version: number
  statut: string
  statut_libelle: string
  devis_id: string
  devis_reference: string
  fiche_id: string
  client_id: string
  client_nom: string
  date_evenement: string
  heure_evenement: string
  couverts_devis: number
  couverts_reels: number
  total_centimes: number
  total: string
  total_devis_centimes: number
  total_devis: string
  ecart_centimes: number
  ecart: string
  remarques_compta: string | null
  lignes: LigneDocument[]
  manques: string[]
  transmis_le: string | null
  facture_le: string | null
  numero_facture_compta: string | null
  alertes?: string[]
}

export type Utilisateur = {
  id: string
  email: string
  nom: string
  role: string
  droits: string[]
  actif: boolean
  derniere_connexion: string | null
}
