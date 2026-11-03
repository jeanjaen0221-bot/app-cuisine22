import { FormEvent, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, euros } from '../api'
import { Champ, EnTete, Erreur, useAction, useCharger } from '../composants/ui'
import { useSession } from '../contexte'
import type { Produit } from '../types'

const ONGLETS = [
  { cle: 'formule_repas', libelle: 'Formules repas' }, { cle: 'formule_boissons', libelle: 'Formules boissons' },
  { cle: 'coupe', libelle: 'Coupes' }, { cle: 'entree,plat,dessert', libelle: 'Plats de la carte' },
  { cle: 'supplement', libelle: 'Suppléments' }, { cle: 'privatisation', libelle: 'Privatisations' },
]
const NOMS_CATEGORIES: Record<string, string> = {
  formule_repas: 'Formule repas', formule_boissons: 'Formule boissons', coupe: 'Coupe', entree: 'Entrée',
  plat: 'Plat', dessert: 'Dessert', supplement: 'Supplément', privatisation: 'Privatisation',
}

/** Saisie en euros : « 4,31 » ; vide = prix manquant. */
const versSaisie = (c: number | null) => (c === null ? '' : (c / 100).toFixed(2).replace('.', ','))

export default function Prix() {
  const { moi, rechargerCompteur, rechargerReferences } = useSession()
  const peutModifier = moi.peut.prix
  const [params, setParams] = useSearchParams()
  const manquants = params.get('manquants') === '1'
  const cible = params.get('produit')
  const [onglet, setOnglet] = useState(ONGLETS[0].cle)
  const [q, setQ] = useState('')
  const { donnees: produits, setDonnees, erreur, recharger } = useCharger(() => api.get<Produit[]>('/api/produits'))
  const action = useAction()
  const [nouveau, setNouveau] = useState({ nom: '', categorie: 'plat', unite: 'piece', prix: '' })

  // Arrivée depuis « Compléter le prix » d'un devis : ouvrir le bon onglet.
  useEffect(() => {
    if (!cible || !produits) return
    const p = produits.find((x) => x.id === cible)
    const o = p && ONGLETS.find((x) => x.cle.split(',').includes(p.categorie))
    if (o) setOnglet(o.cle)
    setTimeout(() => document.getElementById(`produit-${cible}`)?.scrollIntoView({ block: 'center' }), 50)
  }, [cible, produits])

  const nbManquants = produits?.filter((p) => p.prix_manquant && p.actif).length ?? 0
  const visibles = (produits ?? []).filter((p) =>
    (manquants ? p.prix_manquant && p.actif : onglet.split(',').includes(p.categorie)) &&
    (!q || p.nom.toLowerCase().includes(q.toLowerCase())))

  const enregistrer = async (p: Produit, changement: Record<string, unknown>) => {
    const r = await action.lancer(() => api.patch<Produit>(`/api/produits/${p.id}`, changement))
    if (r) {
      setDonnees((liste) => liste?.map((x) => (x.id === r.id ? r : x)) ?? null)
      rechargerCompteur()
      rechargerReferences()
    }
  }

  const ajouter = async (e: FormEvent) => {
    e.preventDefault()
    const r = await action.lancer(() => api.post<Produit>('/api/produits', nouveau))
    if (r) {
      setNouveau({ ...nouveau, nom: '', prix: '' })
      recharger()
      rechargerCompteur()
      rechargerReferences()
    }
  }

  return (
    <>
      <EnTete titre="Prix" sousTitre="Tout ce qui se vend, TVA comprise. Changer un prix ne modifie pas les devis déjà préparés : seulement les nouveaux et ceux qu'on recalcule.">
        <button className={manquants ? 'principal' : ''} onClick={() => setParams(manquants ? {} : { manquants: '1' })}>
          Prix manquants ({nbManquants})
        </button>
      </EnTete>
      {!peutModifier && <div className="bandeau info">Lecture seule : seuls les administrateurs (ou le droit « prix ») modifient les prix.</div>}
      <Erreur message={erreur || action.erreur} />
      {!manquants && (
        <div className="onglets">
          {ONGLETS.map((o) => <button key={o.cle} className={onglet === o.cle ? 'actif' : ''} onClick={() => setOnglet(o.cle)}>{o.libelle}</button>)}
        </div>
      )}
      <div className="filtres"><input placeholder="Filtrer par nom…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      <section className="carte">
        <table className="tableau">
          <thead><tr><th>Nom</th><th>Catégorie</th><th>Unité</th><th className="droite">Prix TVA comprise</th><th>Actif</th></tr></thead>
          <tbody>
            {visibles.map((p) => (
              <tr key={p.id} id={`produit-${p.id}`} className={`${p.prix_manquant ? 'ligne-alerte' : ''}${p.id === cible ? ' ligne-cible' : ''}`}>
                <td>
                  {peutModifier
                    ? <input defaultValue={p.nom} key={p.nom} onBlur={(e) => e.target.value.trim() !== p.nom && enregistrer(p, { nom: e.target.value })} />
                    : p.nom}
                </td>
                <td>{NOMS_CATEGORIES[p.categorie]}</td>
                <td>
                  {peutModifier ? (
                    <select value={p.unite} onChange={(e) => enregistrer(p, { unite: e.target.value })}>
                      <option value="par_personne">par personne</option><option value="piece">pièce</option>
                      <option value="forfait">forfait</option><option value="bouteille">bouteille</option>
                    </select>
                  ) : p.unite_libelle}
                </td>
                <td className="droite">
                  {peutModifier ? (
                    <span className="saisie-prix">
                      <input inputMode="decimal" placeholder="à compléter" defaultValue={versSaisie(p.prix_centimes)} key={String(p.prix_centimes)}
                        onBlur={(e) => {
                          const valeur = e.target.value.trim()
                          if (valeur === versSaisie(p.prix_centimes)) return
                          if (valeur && Number(valeur.replace(',', '.')) === 0 && !window.confirm(`${p.nom} : gratuit ?`)) {
                            e.target.value = versSaisie(p.prix_centimes)
                            return
                          }
                          enregistrer(p, { prix: valeur })
                        }} /> €
                    </span>
                  ) : euros(p.prix_centimes)}
                </td>
                <td>
                  <input type="checkbox" checked={p.actif} disabled={!peutModifier} onChange={(e) => enregistrer(p, { actif: e.target.checked })} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {visibles.length === 0 && <p className="muet">{manquants ? 'Tous les prix sont complétés.' : 'Rien dans cette catégorie.'}</p>}
      </section>

      {peutModifier && (
        <form className="carte" onSubmit={ajouter}>
          <h2>Ajouter</h2>
          <div className="ligne-champs">
            <Champ libelle="Nom"><input value={nouveau.nom} onChange={(e) => setNouveau({ ...nouveau, nom: e.target.value })} required /></Champ>
            <Champ libelle="Catégorie">
              <select value={nouveau.categorie} onChange={(e) => setNouveau({ ...nouveau, categorie: e.target.value })}>
                {Object.entries(NOMS_CATEGORIES).map(([cle, nom]) => <option key={cle} value={cle}>{nom}</option>)}
              </select>
            </Champ>
            <Champ libelle="Unité">
              <select value={nouveau.unite} onChange={(e) => setNouveau({ ...nouveau, unite: e.target.value })}>
                <option value="par_personne">par personne</option><option value="piece">pièce</option>
                <option value="forfait">forfait</option><option value="bouteille">bouteille</option>
              </select>
            </Champ>
            <Champ libelle="Prix TVA comprise" aide="Vide = à compléter plus tard."><input inputMode="decimal" placeholder="ex. 24,50" value={nouveau.prix} onChange={(e) => setNouveau({ ...nouveau, prix: e.target.value })} /></Champ>
            <button className="principal" disabled={action.enCours}>Ajouter</button>
          </div>
          <p className="aide">Une nouvelle formule repas ou boissons se crée dans le menu Formules.</p>
        </form>
      )}
    </>
  )
}
