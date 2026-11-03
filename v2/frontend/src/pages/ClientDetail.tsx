import { FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, Echec, formatJour } from '../api'
import { Alertes, Champ, EnTete, Erreur, Statut, useAction } from '../composants/ui'
import type { Bon, Client, Devis, Fiche } from '../types'

type Detail = Client & { fiches: Fiche[]; devis: Devis[]; bons: Bon[] }

const VIDE: Partial<Client> = { type: 'particulier', nom: '', pays: 'Belgique', langue: 'fr' }
const CHAMPS: { cle: keyof Client; libelle: string; type?: string }[] = [
  { cle: 'contact_prenom', libelle: 'Prénom du contact' }, { cle: 'contact_nom', libelle: 'Nom du contact' },
  { cle: 'email', libelle: 'E-mail', type: 'email' }, { cle: 'telephone', libelle: 'Téléphone' },
  { cle: 'rue', libelle: 'Rue' }, { cle: 'numero', libelle: 'N°' }, { cle: 'boite', libelle: 'Boîte' },
  { cle: 'code_postal', libelle: 'Code postal' }, { cle: 'ville', libelle: 'Ville' }, { cle: 'pays', libelle: 'Pays' },
  { cle: 'tva', libelle: 'N° TVA' }, { cle: 'reference_po', libelle: 'Référence de commande (PO)' },
  { cle: 'conditions_paiement', libelle: 'Conditions de paiement' },
]

export default function ClientDetail() {
  const { id } = useParams()
  const nouveau = id === 'nouveau'
  const naviguer = useNavigate()
  const [detail, setDetail] = useState<Detail | null>(null)
  const [c, setC] = useState<Partial<Client>>(VIDE)
  const [proches, setProches] = useState<{ id: string; nom: string }[]>([])
  const { enCours, erreur, setErreur, lancer } = useAction()

  useEffect(() => {
    if (nouveau || !id) { setDetail(null); setC(VIDE); return }
    api.get<Detail>(`/api/clients/${id}`).then((d) => { setDetail(d); setC(d) }).catch((e) => setErreur(e.message))
  }, [id, nouveau, setErreur])

  const maj = (changement: Partial<Client>) => setC((x) => ({ ...x, ...changement }))

  const enregistrer = async (e: FormEvent, confirmer = false) => {
    e.preventDefault()
    const corps: Record<string, unknown> = { type: c.type, nom: c.nom, langue: c.langue, notes: c.notes, preferences: c.preferences }
    for (const { cle } of CHAMPS) corps[cle] = c[cle] ?? ''
    try {
      if (nouveau) {
        const cree = await api.post<Client>('/api/clients', { ...corps, confirmer_doublon: confirmer })
        naviguer(`/clients/${cree.id}`, { replace: true })
      } else {
        const modifie = await lancer(() => api.patch<Client>(`/api/clients/${id}`, { ...corps, version: detail!.version }))
        if (modifie) { setDetail({ ...detail!, ...modifie }); setC(modifie) }
      }
      setProches([])
    } catch (err) {
      if (err instanceof Echec && err.erreur.code === 'doublon_probable') {
        setProches((err.erreur.details?.clients as { id: string; nom: string }[]) ?? [])
      }
      setErreur(err instanceof Error ? err.message : String(err))
    }
  }

  const archiver = async () => {
    const r = await lancer(() => api.patch<Client>(`/api/clients/${id}`, { archive: !c.archive, version: detail!.version }))
    if (r) { setDetail({ ...detail!, ...r }); setC(r) }
  }

  return (
    <form onSubmit={enregistrer}>
      <EnTete titre={nouveau ? 'Nouveau client' : c.nom ?? ''}>
        {!nouveau && <Link className="bouton" to="/fiches/nouvelle">Nouvelle fiche</Link>}
        {!nouveau && <button type="button" onClick={archiver}>{c.archive ? 'Désarchiver' : 'Archiver'}</button>}
        <button className="principal" disabled={enCours}>Enregistrer</button>
      </EnTete>
      <Erreur message={erreur} />
      {proches.length > 0 && (
        <div className="bandeau attention">
          Clients proches : {proches.map((p) => <Link key={p.id} to={`/clients/${p.id}`}> {p.nom}</Link>)}
          <button type="button" onClick={(e) => enregistrer(e as unknown as FormEvent, true)}>Créer quand même</button>
        </div>
      )}
      {detail && <Alertes liste={detail.manques_facturation.map((m) => `Pour valider un devis : ${m} manquant(e).`)} />}

      <section className="carte">
        <div className="ligne-champs">
          <Champ libelle="Type">
            <select value={c.type} onChange={(e) => maj({ type: e.target.value as Client['type'] })}>
              <option value="particulier">Particulier</option>
              <option value="entreprise">Entreprise</option>
            </select>
          </Champ>
          <Champ libelle="Nom ou raison sociale" large><input value={c.nom ?? ''} onChange={(e) => maj({ nom: e.target.value })} required /></Champ>
          <Champ libelle="Langue">
            <select value={c.langue} onChange={(e) => maj({ langue: e.target.value })}>
              <option value="fr">Français</option><option value="nl">Néerlandais</option><option value="en">Anglais</option>
            </select>
          </Champ>
        </div>
        <div className="ligne-champs">
          {CHAMPS.map(({ cle, libelle, type }) => (
            <Champ key={cle} libelle={libelle}>
              <input type={type ?? 'text'} value={(c[cle] as string) ?? ''} onChange={(e) => maj({ [cle]: e.target.value } as Partial<Client>)} />
            </Champ>
          ))}
        </div>
        <div className="ligne-champs">
          <Champ libelle="Préférences et allergies habituelles" large>
            <textarea rows={3} value={c.preferences ?? ''} onChange={(e) => maj({ preferences: e.target.value })} />
          </Champ>
          <Champ libelle="Notes internes" large>
            <textarea rows={3} value={c.notes ?? ''} onChange={(e) => maj({ notes: e.target.value })} />
          </Champ>
        </div>
      </section>

      {detail && (
        <div className="grille-2">
          <section className="carte">
            <h2>Fiches</h2>
            <ul className="liste">
              {detail.fiches.map((f) => (
                <li key={f.id}><Link to={`/fiches/${f.id}`}>{formatJour(f.date)} {f.heure}</Link> — {f.couverts} couverts · <Statut statut={f.statut} libelle={f.statut_libelle} /></li>
              ))}
              {detail.fiches.length === 0 && <li className="muet">Aucune fiche.</li>}
            </ul>
          </section>
          <section className="carte">
            <h2>Devis et bons</h2>
            <ul className="liste">
              {detail.devis.map((d) => (
                <li key={d.id}><Link to={`/devis/${d.id}`}>{d.reference}</Link> — {d.total} · <Statut statut={d.statut} libelle={d.statut_libelle} /></li>
              ))}
              {detail.bons.map((b) => (
                <li key={b.id}><Link to={`/bons/${b.id}`}>{b.numero}</Link> — {b.total} · <Statut statut={b.statut} libelle={b.statut_libelle} /></li>
              ))}
              {detail.devis.length + detail.bons.length === 0 && <li className="muet">Aucun document.</li>}
            </ul>
          </section>
        </div>
      )}
    </form>
  )
}
