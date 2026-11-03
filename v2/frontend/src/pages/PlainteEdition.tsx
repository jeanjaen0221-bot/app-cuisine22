import { FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, aujourdhui, ouvrirPdf } from '../api'
import ChoixClient from '../composants/ChoixClient'
import { Champ, EnTete, Erreur, useAction } from '../composants/ui'
import { useSession } from '../contexte'
import type { Plainte } from './Plaintes'

const TEXTES: [keyof Plainte, string][] = [
  ['recit_brut', 'Récit (tel que raconté)'], ['contexte', 'Contexte'], ['description', "Description de l'incident"],
  ['reaction_personnel', 'Réaction du personnel'], ['consequences', 'Conséquences'], ['mesures_prises', 'Mesures prises'],
  ['observations', 'Observations'],
]

export default function PlainteEdition() {
  const { id } = useParams()
  const nouvelle = !id || id === 'nouvelle'
  const naviguer = useNavigate()
  const { moi } = useSession()
  const [p, setP] = useState<Partial<Plainte>>({ date: aujourdhui(), gravite: 'faible' })
  const [client, setClient] = useState<{ id: string; nom: string } | null>(null)
  const { enCours, erreur, setErreur, lancer } = useAction()

  useEffect(() => {
    if (nouvelle) return
    api.get<Plainte>(`/api/plaintes/${id}`).then((d) => {
      setP(d)
      setClient(d.client_id ? { id: d.client_id, nom: d.client_nom ?? '' } : null)
    }).catch((e) => setErreur(e.message))
  }, [id, nouvelle, setErreur])

  const maj = (c: Partial<Plainte>) => setP((x) => ({ ...x, ...c }))
  const enregistrer = async (e: FormEvent, statut?: string) => {
    e.preventDefault()
    const corps: Record<string, unknown> = {
      date: p.date, heure: p.heure || null, lieu: p.lieu, employes: p.employes, client_nom: client ? null : p.client_nom,
      client_id: client?.id ?? null, gravite: p.gravite, ...Object.fromEntries(TEXTES.map(([cle]) => [cle, p[cle] ?? ''])),
    }
    if (statut) corps.statut = statut
    const r = await lancer(() => nouvelle ? api.post<Plainte>('/api/plaintes', corps)
      : api.patch<Plainte>(`/api/plaintes/${id}`, { ...corps, version: p.version }))
    if (r) { if (nouvelle) naviguer(`/plaintes/${r.id}`, { replace: true }); else setP(r) }
  }
  const supprimer = async () => {
    if (window.confirm('Supprimer définitivement cette plainte ?') && await lancer(() => api.delete(`/api/plaintes/${id}`))) naviguer('/plaintes')
  }

  return (
    <form onSubmit={(e) => enregistrer(e)}>
      <EnTete titre={nouvelle ? 'Nouvelle plainte' : `Plainte — ${p.statut_libelle ?? ''}`}>
        {!nouvelle && <button type="button" onClick={() => ouvrirPdf(`/api/plaintes/${id}/pdf`)}>PDF</button>}
        {!nouvelle && p.statut === 'brouillon' && <button type="button" onClick={(e) => enregistrer(e as unknown as FormEvent, 'ouverte')}>Valider le brouillon</button>}
        {!nouvelle && p.statut === 'ouverte' && <button type="button" onClick={(e) => enregistrer(e as unknown as FormEvent, 'traitee')}>Marquer traitée</button>}
        {!nouvelle && p.statut === 'traitee' && <button type="button" onClick={(e) => enregistrer(e as unknown as FormEvent, 'ouverte')}>Rouvrir</button>}
        {!nouvelle && moi.peut.admin && <button type="button" className="danger" onClick={supprimer}>Supprimer</button>}
        <button className="principal" disabled={enCours}>Enregistrer</button>
      </EnTete>
      <Erreur message={erreur} />
      {p.statut === 'brouillon' && <div className="bandeau info">Brouillon rédigé par ChatGPT : relire, corriger, puis valider.</div>}
      <section className="carte">
        <div className="ligne-champs">
          <Champ libelle="Date"><input type="date" value={p.date ?? ''} onChange={(e) => maj({ date: e.target.value })} required /></Champ>
          <Champ libelle="Heure"><input type="time" value={p.heure ?? ''} onChange={(e) => maj({ heure: e.target.value })} /></Champ>
          <Champ libelle="Lieu"><input value={p.lieu ?? ''} onChange={(e) => maj({ lieu: e.target.value })} /></Champ>
          <Champ libelle="Employé(s)"><input value={p.employes ?? ''} onChange={(e) => maj({ employes: e.target.value })} /></Champ>
          <Champ libelle="Gravité">
            <select value={p.gravite} onChange={(e) => maj({ gravite: e.target.value as Plainte['gravite'] })}>
              <option value="faible">Faible</option><option value="moyen">Moyen</option><option value="eleve">Élevé</option>
            </select>
          </Champ>
        </div>
        <div className="ligne-champs">
          <Champ libelle="Client (fiche client)" large><ChoixClient valeur={client} surChoix={setClient} /></Champ>
          {!client && <Champ libelle="…ou nom du client"><input value={p.client_nom ?? ''} onChange={(e) => maj({ client_nom: e.target.value })} /></Champ>}
        </div>
        {p.fiche_id && <p className="aide">Liée à la <Link to={`/fiches/${p.fiche_id}`}>fiche de l'événement</Link>.</p>}
      </section>
      <section className="carte">
        {TEXTES.map(([cle, libelle]) => (
          <Champ key={cle} libelle={libelle} large>
            <textarea rows={cle === 'recit_brut' ? 5 : 3} value={(p[cle] as string) ?? ''} onChange={(e) => maj({ [cle]: e.target.value } as Partial<Plainte>)} />
          </Champ>
        ))}
        <p className="aide">Astuce : racontez l'incident à ChatGPT, il rédige ce rapport en brouillon.</p>
      </section>
    </form>
  )
}
