import { FormEvent, Fragment, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, Echec, formatInstant, messageErreur } from '../api'
import { Champ, EnTete, Erreur, Pastille, Statut, useAction, useCharger } from '../composants/ui'

type Offre = { fournisseur_id: string; fournisseur: string; reference: string | null; prix_achat_centimes: number | null; prix_achat: string | null; colisage: number | null; prefere: boolean }
type Boisson = { id: string; nom: string; categorie: string | null; unite: string | null; stock_min: number; stock_max: number; colisage: number | null; reassort: boolean; actif: boolean; fournisseurs: Offre[]; fournisseur_prefere: string | null }
type Fournisseur = { id: string; nom: string; email: string | null; telephone: string | null; notes: string | null; actif: boolean }
type LigneReassort = { boisson_id: string; nom: string; categorie: string | null; unite: string | null; reste: number; stock_min: number; stock_max: number; colisage: number | null; reassort: boolean; sous_le_minimum: boolean; a_commander: number; fournisseur: string | null }
export type BonCommande = {
  id: string; numero: string; version: number; statut: string; statut_libelle: string; fournisseur_id: string | null; fournisseur: string | null
  fournisseur_email: string | null; note: string | null; total_achat: string; prix_manquants: boolean; cree_le: string; envoye_le: string | null; recu_le: string | null
  lignes: { id: string; boisson_id: string | null; libelle: string; unite: string | null; reference: string | null; quantite: number; prix_achat: string | null }[]
}

const ONGLETS = [['reassort', 'Réassort'], ['commandes', 'Bons de commande'], ['boissons', 'Boissons'], ['fournisseurs', 'Fournisseurs']] as const
export const STATUT_COULEUR: Record<string, string> = { brouillon: 'brouillon', envoye: 'transmis', recu: 'realisee', annule: 'annulee' }

export default function Achats() {
  const [params, setParams] = useSearchParams()
  const onglet = params.get('onglet') ?? 'reassort'
  return (
    <>
      <EnTete titre="Achats" sousTitre="Boissons, stock, bons de commande fournisseurs. Les prix d'achat sont séparés des prix de vente." />
      <div className="onglets">
        {ONGLETS.map(([cle, libelle]) => <button key={cle} className={onglet === cle ? 'actif' : ''} onClick={() => setParams({ onglet: cle })}>{libelle}</button>)}
      </div>
      {onglet === 'reassort' && <Reassort />}
      {onglet === 'commandes' && <Commandes />}
      {onglet === 'boissons' && <Boissons />}
      {onglet === 'fournisseurs' && <Fournisseurs />}
    </>
  )
}

function Reassort() {
  const naviguer = useNavigate()
  const [restant, setRestant] = useState<Record<string, number>>(() => {
    try { return JSON.parse(localStorage.getItem('albert.reassort') ?? '{}') } catch { return {} }
  })
  const [cible, setCible] = useState<'max' | 'min'>('max')
  const [quantites, setQuantites] = useState<Record<string, number>>({})
  const { donnees, erreur, recharger } = useCharger(() => api.post<LigneReassort[]>('/api/achats/reassort', { restant, cible }), [cible])
  const action = useAction()
  const lignes = (donnees ?? []).filter((l) => l.reassort)

  const saisir = (id: string, valeur: number) => {
    const suivant = { ...restant, [id]: valeur }
    setRestant(suivant)
    try { localStorage.setItem('albert.reassort', JSON.stringify(suivant)) } catch { /* stockage indisponible */ }
  }
  const qte = (l: LigneReassort) => quantites[l.boisson_id] ?? l.a_commander
  const commander = async () => {
    const r = await action.lancer(() => api.post<BonCommande[]>('/api/achats/reassort/commander', {
      quantites: Object.fromEntries(lignes.map((l) => [l.boisson_id, qte(l)])),
    }))
    if (r) naviguer(r.length === 1 ? `/achats/commandes/${r[0].id}` : '/achats?onglet=commandes')
  }
  const total = lignes.reduce((n, l) => n + (qte(l) > 0 ? 1 : 0), 0)

  return (
    <section className="carte">
      <div className="ligne-champs">
        <span>Compléter jusqu'au</span>
        <select value={cible} onChange={(e) => setCible(e.target.value as 'max' | 'min')}><option value="max">stock maximum</option><option value="min">stock minimum</option></select>
        <button onClick={() => recharger()}>Recalculer</button>
        <button className="principal" onClick={commander} disabled={!total || action.enCours}>Préparer les bons de commande ({total})</button>
      </div>
      <p className="aide">Saisir ce qui reste en stock, puis « Recalculer ». Un bon de commande en brouillon est préparé pour chaque fournisseur préféré.</p>
      <Erreur message={erreur || action.erreur} />
      <table className="tableau">
        <thead><tr><th>Boisson</th><th>Fournisseur</th><th className="droite">Min / max</th><th className="droite">Colis</th><th className="droite">Reste</th><th className="droite">À commander</th></tr></thead>
        <tbody>
          {lignes.map((l) => (
            <tr key={l.boisson_id} className={l.sous_le_minimum ? 'ligne-alerte' : ''}>
              <td>{l.nom} <span className="muet">{l.categorie}</span></td>
              <td>{l.fournisseur ?? <span className="muet">à choisir</span>}</td>
              <td className="droite">{l.stock_min} / {l.stock_max} {l.unite}</td>
              <td className="droite">{l.colisage ?? '—'}</td>
              <td className="droite"><input className="etroit" type="number" min={0} value={restant[l.boisson_id] ?? ''} onChange={(e) => saisir(l.boisson_id, Number(e.target.value))} /></td>
              <td className="droite"><input className="etroit" type="number" min={0} value={qte(l)} onChange={(e) => setQuantites({ ...quantites, [l.boisson_id]: Number(e.target.value) })} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      {lignes.length === 0 && <p className="muet">Aucune boisson suivie : en ajouter dans l'onglet Boissons.</p>}
    </section>
  )
}

function Commandes() {
  const [statut, setStatut] = useState('brouillon,envoye')
  const { donnees, erreur } = useCharger(() => api.get<BonCommande[]>('/api/achats/commandes', { statut }), [statut])
  return (
    <section className="carte">
      <div className="onglets">
        {[['brouillon,envoye', 'En cours'], ['recu', 'Reçus'], ['annule', 'Annulés'], ['', 'Tous']].map(([cle, l]) => (
          <button key={cle} className={statut === cle ? 'actif' : ''} onClick={() => setStatut(cle)}>{l}</button>
        ))}
        <Link className="bouton" to="/achats/commandes/nouveau">Nouveau bon</Link>
      </div>
      <Erreur message={erreur} />
      <table className="tableau">
        <thead><tr><th>N°</th><th>Fournisseur</th><th>Lignes</th><th className="droite">Total d'achat</th><th>Créé</th><th>Statut</th></tr></thead>
        <tbody>
          {donnees?.map((b) => (
            <tr key={b.id}>
              <td><Link to={`/achats/commandes/${b.id}`}>{b.numero}</Link></td>
              <td>{b.fournisseur ?? <span className="texte-alerte">à choisir</span>}</td>
              <td>{b.lignes.length}</td>
              <td className="droite">{b.total_achat}{b.prix_manquants && ' *'}</td>
              <td>{formatInstant(b.cree_le)}</td>
              <td><Statut statut={STATUT_COULEUR[b.statut]} libelle={b.statut_libelle} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      {donnees?.length === 0 && <p className="muet">Aucun bon.</p>}
    </section>
  )
}

function Boissons() {
  const { donnees, erreur, recharger } = useCharger(() => api.get<Boisson[]>('/api/achats/boissons'))
  const { donnees: fournisseurs } = useCharger(() => api.get<Fournisseur[]>('/api/achats/fournisseurs'))
  const action = useAction()
  const [q, setQ] = useState('')
  const [nouvelle, setNouvelle] = useState({ nom: '', categorie: '', unite: '' })
  const [ouverte, setOuverte] = useState<string | null>(null)
  const fichier = useRef<HTMLInputElement>(null)
  const [import_, setImport] = useState('')
  const visibles = useMemo(() => (donnees ?? []).filter((b) => !q || `${b.nom} ${b.categorie ?? ''}`.toLowerCase().includes(q.toLowerCase())), [donnees, q])

  const maj = async (b: Boisson, changement: object) => { if (await action.lancer(() => api.patch(`/api/achats/boissons/${b.id}`, changement))) recharger() }
  const ajouter = async (e: FormEvent) => {
    e.preventDefault()
    if (await action.lancer(() => api.post('/api/achats/boissons', nouvelle))) { setNouvelle({ nom: '', categorie: '', unite: '' }); recharger() }
  }
  const importer = async (f?: File) => {
    if (!f) return
    const formulaire = new FormData()
    formulaire.append('fichier', f)
    try {
      const r = await fetch('/api/achats/boissons/import', { method: 'POST', body: formulaire, credentials: 'same-origin', headers: { 'X-Albert': '1' } })
      const corps = await r.json()
      if (!r.ok) throw new Echec(r.status, corps.erreur)
      setImport(`${corps.ajoutees} boisson(s) ajoutée(s) sur ${corps.lues} lue(s).`)
      recharger()
    } catch (e) { action.setErreur(messageErreur(e)) }
  }

  return (
    <>
      <section className="carte">
        <div className="filtres">
          <input placeholder="Filtrer…" value={q} onChange={(e) => setQ(e.target.value)} />
          <button onClick={() => fichier.current?.click()}>Importer une liste (texte, CSV ou PDF de la carte)</button>
          <input ref={fichier} type="file" accept=".txt,.csv,.pdf,text/plain,text/csv,application/pdf" hidden onChange={(e) => { importer(e.target.files?.[0]); e.target.value = '' }} />
          {import_ && <span className="muet">{import_}</span>}
        </div>
        <Erreur message={erreur || action.erreur} />
        <table className="tableau">
          <thead><tr><th>Boisson</th><th>Catégorie</th><th>Unité</th><th className="droite">Min</th><th className="droite">Max</th><th className="droite">Colis</th><th>Fournisseur préféré</th><th>Réassort</th><th>Active</th></tr></thead>
          <tbody>
            {visibles.map((b) => (
              <Fragment key={b.id}>
                <tr className={b.actif ? '' : 'inactif'}>
                  <td><button className="lien" onClick={() => setOuverte(ouverte === b.id ? null : b.id)}>{b.nom}</button></td>
                  <td><input defaultValue={b.categorie ?? ''} onBlur={(e) => e.target.value !== (b.categorie ?? '') && maj(b, { categorie: e.target.value })} /></td>
                  <td><input defaultValue={b.unite ?? ''} onBlur={(e) => e.target.value !== (b.unite ?? '') && maj(b, { unite: e.target.value })} /></td>
                  <td className="etroit"><input type="number" min={0} defaultValue={b.stock_min} onBlur={(e) => Number(e.target.value) !== b.stock_min && maj(b, { stock_min: Number(e.target.value) })} /></td>
                  <td className="etroit"><input type="number" min={0} defaultValue={b.stock_max} onBlur={(e) => Number(e.target.value) !== b.stock_max && maj(b, { stock_max: Number(e.target.value) })} /></td>
                  <td className="etroit"><input type="number" min={1} defaultValue={b.colisage ?? ''} onBlur={(e) => Number(e.target.value || 0) !== (b.colisage ?? 0) && maj(b, { colisage: e.target.value ? Number(e.target.value) : null })} /></td>
                  <td>{b.fournisseur_prefere ?? <span className="muet">—</span>}</td>
                  <td><input type="checkbox" checked={b.reassort} onChange={(e) => maj(b, { reassort: e.target.checked })} /></td>
                  <td><input type="checkbox" checked={b.actif} onChange={(e) => maj(b, { actif: e.target.checked })} /></td>
                </tr>
                {ouverte === b.id && (
                  <tr><td colSpan={9}><Offres boisson={b} fournisseurs={fournisseurs ?? []} surEnregistrer={(offres) => maj(b, { fournisseurs: offres })} /></td></tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
        <p className="aide">Cliquer le nom d'une boisson pour ses fournisseurs et prix d'achat.</p>
      </section>
      <form className="carte ligne-champs" onSubmit={ajouter}>
        <Champ libelle="Nouvelle boisson"><input value={nouvelle.nom} onChange={(e) => setNouvelle({ ...nouvelle, nom: e.target.value })} required /></Champ>
        <Champ libelle="Catégorie"><input value={nouvelle.categorie} onChange={(e) => setNouvelle({ ...nouvelle, categorie: e.target.value })} /></Champ>
        <Champ libelle="Unité"><input value={nouvelle.unite} placeholder="bouteille, fût…" onChange={(e) => setNouvelle({ ...nouvelle, unite: e.target.value })} /></Champ>
        <button className="principal" disabled={action.enCours}>Ajouter</button>
      </form>
    </>
  )
}

function Offres({ boisson, fournisseurs, surEnregistrer }: { boisson: Boisson; fournisseurs: Fournisseur[]; surEnregistrer: (o: object[]) => void }) {
  const [offres, setOffres] = useState(boisson.fournisseurs.map((o) => ({
    fournisseur_id: o.fournisseur_id, reference: o.reference ?? '', prix_achat: o.prix_achat_centimes === null ? '' : (o.prix_achat_centimes / 100).toFixed(2).replace('.', ','),
    colisage: o.colisage ?? '', prefere: o.prefere,
  })))
  const maj = (i: number, c: object) => setOffres(offres.map((o, j) => (j === i ? { ...o, ...c } : o)))
  return (
    <div className="encadre">
      {offres.map((o, i) => (
        <div className="ligne-champs" key={i}>
          <select value={o.fournisseur_id} onChange={(e) => maj(i, { fournisseur_id: e.target.value })}>
            {fournisseurs.map((f) => <option key={f.id} value={f.id}>{f.nom}</option>)}
          </select>
          <input placeholder="Référence" value={o.reference} onChange={(e) => maj(i, { reference: e.target.value })} />
          <input placeholder="Prix d'achat" inputMode="decimal" value={o.prix_achat} onChange={(e) => maj(i, { prix_achat: e.target.value })} style={{ width: 110 }} />
          <input placeholder="Colis" type="number" value={o.colisage} onChange={(e) => maj(i, { colisage: e.target.value })} style={{ width: 80 }} />
          <label className="case"><input type="radio" checked={o.prefere} onChange={() => setOffres(offres.map((x, j) => ({ ...x, prefere: j === i })))} /> préféré</label>
          <button className="lien" onClick={() => setOffres(offres.filter((_, j) => j !== i))}>retirer</button>
        </div>
      ))}
      <div className="ligne-champs">
        <button disabled={!fournisseurs.length} onClick={() => setOffres([...offres, { fournisseur_id: fournisseurs[0]?.id ?? '', reference: '', prix_achat: '', colisage: '', prefere: offres.length === 0 }])}>+ Fournisseur</button>
        <button className="principal" onClick={() => surEnregistrer(offres.map((o) => ({ ...o, colisage: o.colisage === '' ? null : Number(o.colisage) })))}>Enregistrer</button>
      </div>
      {!fournisseurs.length && <p className="aide">Créer d'abord un fournisseur (onglet Fournisseurs).</p>}
    </div>
  )
}

function Fournisseurs() {
  const { donnees, erreur, recharger } = useCharger(() => api.get<Fournisseur[]>('/api/achats/fournisseurs'))
  const action = useAction()
  const [nouveau, setNouveau] = useState({ nom: '', email: '', telephone: '' })
  const maj = async (f: Fournisseur, c: object) => { if (await action.lancer(() => api.patch(`/api/achats/fournisseurs/${f.id}`, c))) recharger() }
  const ajouter = async (e: FormEvent) => {
    e.preventDefault()
    if (await action.lancer(() => api.post('/api/achats/fournisseurs', nouveau))) { setNouveau({ nom: '', email: '', telephone: '' }); recharger() }
  }
  return (
    <>
      <section className="carte">
        <Erreur message={erreur || action.erreur} />
        <table className="tableau">
          <thead><tr><th>Nom</th><th>E-mail</th><th>Téléphone</th><th>Notes</th><th>Actif</th></tr></thead>
          <tbody>
            {donnees?.map((f) => (
              <tr key={f.id} className={f.actif ? '' : 'inactif'}>
                <td><input defaultValue={f.nom} onBlur={(e) => e.target.value !== f.nom && maj(f, { nom: e.target.value })} /></td>
                <td><input defaultValue={f.email ?? ''} onBlur={(e) => e.target.value !== (f.email ?? '') && maj(f, { email: e.target.value })} /></td>
                <td><input defaultValue={f.telephone ?? ''} onBlur={(e) => e.target.value !== (f.telephone ?? '') && maj(f, { telephone: e.target.value })} /></td>
                <td><input defaultValue={f.notes ?? ''} onBlur={(e) => e.target.value !== (f.notes ?? '') && maj(f, { notes: e.target.value })} /></td>
                <td><input type="checkbox" checked={f.actif} onChange={(e) => maj(f, { actif: e.target.checked })} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {donnees?.length === 0 && <p className="muet">Aucun fournisseur.</p>}
      </section>
      <form className="carte ligne-champs" onSubmit={ajouter}>
        <Champ libelle="Nouveau fournisseur"><input value={nouveau.nom} onChange={(e) => setNouveau({ ...nouveau, nom: e.target.value })} required /></Champ>
        <Champ libelle="E-mail"><input type="email" value={nouveau.email} onChange={(e) => setNouveau({ ...nouveau, email: e.target.value })} /></Champ>
        <Champ libelle="Téléphone"><input value={nouveau.telephone} onChange={(e) => setNouveau({ ...nouveau, telephone: e.target.value })} /></Champ>
        <button className="principal" disabled={action.enCours}>Ajouter</button>
      </form>
      <p className="aide"><Pastille couleur="gris">astuce</Pastille> Le fournisseur « préféré » d'une boisson reçoit ses commandes de réassort.</p>
    </>
  )
}
