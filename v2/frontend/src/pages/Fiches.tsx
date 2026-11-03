import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, aujourdhui, formatJour, ouvrirPdf } from '../api'
import { Chargement, EnTete, Erreur, Pastille, Statut, useCharger } from '../composants/ui'
import { useSession } from '../contexte'
import type { Fiche } from '../types'

export default function Fiches() {
  const { references } = useSession()
  const [params, setParams] = useSearchParams()
  const periode = params.get('periode') ?? 'a_venir'
  const espace = params.get('espace') ?? ''
  const statut = params.get('statut') ?? ''
  const jour = params.get('jour') ?? ''
  const [q, setQ] = useState(params.get('q') ?? '')

  const { donnees: fiches, erreur, chargement } = useCharger(
    () => api.get<Fiche[]>('/api/fiches', { periode, espace, statut, jour, q: params.get('q') ?? '' }),
    [periode, espace, statut, jour, params.get('q')],
  )

  const changer = (cle: string, valeur: string) => {
    const suivant = new URLSearchParams(params)
    if (valeur) suivant.set(cle, valeur)
    else suivant.delete(cle)
    setParams(suivant)
  }

  const parJour = new Map<string, Fiche[]>()
  for (const f of fiches ?? []) parJour.set(f.date, [...(parJour.get(f.date) ?? []), f])

  return (
    <>
      <EnTete titre="Fiches">
        <button onClick={() => ouvrirPdf(`/api/jour/${jour || aujourdhui()}/pdf`)}>PDF du jour</button>
        <Link className="bouton principal" to="/fiches/nouvelle">Nouvelle fiche</Link>
      </EnTete>
      <div className="filtres">
        <form onSubmit={(e) => { e.preventDefault(); changer('q', q) }}>
          <input placeholder="Client, contact…" value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
        <select value={periode} onChange={(e) => changer('periode', e.target.value)} disabled={!!jour}>
          <option value="a_venir">À venir</option>
          <option value="passees">Passées</option>
          <option value="toutes">Toutes</option>
        </select>
        <input type="date" value={jour} onChange={(e) => changer('jour', e.target.value)} title="Un jour précis" />
        <select value={espace} onChange={(e) => changer('espace', e.target.value)}>
          <option value="">Tous les espaces</option>
          {references?.espaces.map((e) => <option key={e} value={e}>{e}</option>)}
        </select>
        <select value={statut} onChange={(e) => changer('statut', e.target.value)}>
          <option value="">Tous les statuts</option>
          {references?.statuts_fiche.map((s) => <option key={s.cle} value={s.cle}>{s.libelle}</option>)}
        </select>
      </div>
      <Erreur message={erreur} />
      <Chargement actif={chargement && !fiches} />
      {fiches && fiches.length === 0 && <p className="muet">Aucune fiche.</p>}
      {[...parJour.entries()].map(([date, liste]) => (
        <section key={date} className="carte">
          <h2 className="jour">
            {formatJour(date)}
            <span className="muet"> · {liste.reduce((n, f) => n + (f.statut === 'annulee' ? 0 : f.couverts), 0)} couverts</span>
          </h2>
          <table className="tableau">
            <tbody>
              {liste.map((f) => (
                <tr key={f.id} className={f.statut === 'annulee' ? 'barre-texte' : ''}>
                  <td className="etroit">{f.heure}</td>
                  <td><Link to={`/fiches/${f.id}`}>{f.client.nom}</Link></td>
                  <td>{f.couverts} couv.</td>
                  <td>{f.espace !== 'salle' && <Pastille couleur="indigo">{f.espace}</Pastille>}</td>
                  <td>{f.formule_repas ?? (f.lignes.some((l) => l.type !== 'supplement') ? 'plats choisis' : '—')}</td>
                  <td><Pastille couleur={f.couleur_boissons}>{f.formule_boissons ?? '—'}</Pastille></td>
                  <td>{f.allergenes.length > 0 && <Pastille couleur="rouge">{f.allergenes.length} allergène(s)</Pastille>}</td>
                  <td><Statut statut={f.statut} libelle={f.statut_libelle} /></td>
                  <td>{f.alertes.length > 0 && <span className="texte-alerte" title={f.alertes.join('\n')}>⚠</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </>
  )
}
