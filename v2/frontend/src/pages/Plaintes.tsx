import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, formatJour } from '../api'
import { Chargement, EnTete, Erreur, Pastille, Statut, useCharger } from '../composants/ui'

export type Plainte = {
  id: string; version: number; date: string; heure: string | null; lieu: string | null; employes: string | null
  client_nom: string | null; client_id: string | null; fiche_id: string | null; recit_brut: string | null
  contexte: string | null; description: string | null; reaction_personnel: string | null; consequences: string | null
  mesures_prises: string | null; observations: string | null; gravite: 'faible' | 'moyen' | 'eleve'
  gravite_libelle: string; statut: string; statut_libelle: string
}

export const COULEUR_GRAVITE = { faible: 'vert', moyen: 'ambre', eleve: 'rouge' }

export default function Plaintes() {
  const [params, setParams] = useSearchParams()
  const statut = params.get('statut') ?? 'brouillon,ouverte'
  const [q, setQ] = useState('')
  const [recherche, setRecherche] = useState('')
  const { donnees, erreur, chargement } = useCharger(() => api.get<Plainte[]>('/api/plaintes', { statut, q: recherche }), [statut, recherche])
  return (
    <>
      <EnTete titre="Plaintes"><Link className="bouton principal" to="/plaintes/nouvelle">Nouvelle plainte</Link></EnTete>
      <div className="onglets">
        {[['brouillon,ouverte', 'À traiter'], ['brouillon', 'Brouillons (ChatGPT)'], ['traitee', 'Traitées'], ['', 'Toutes']].map(([cle, libelle]) => (
          <button key={cle} className={statut === cle ? 'actif' : ''} onClick={() => setParams({ statut: cle })}>{libelle}</button>
        ))}
      </div>
      <div className="filtres">
        <form onSubmit={(e) => { e.preventDefault(); setRecherche(q) }}>
          <input placeholder="Client, lieu, récit…" value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
      </div>
      <Erreur message={erreur} />
      <Chargement actif={chargement && !donnees} />
      {donnees && (
        <section className="carte">
          <table className="tableau">
            <thead><tr><th>Date</th><th>Client</th><th>Lieu</th><th>Résumé</th><th>Gravité</th><th>Statut</th></tr></thead>
            <tbody>
              {donnees.map((p) => (
                <tr key={p.id}>
                  <td><Link to={`/plaintes/${p.id}`}>{formatJour(p.date)}{p.heure ? ` ${p.heure}` : ''}</Link></td>
                  <td>{p.client_nom}</td>
                  <td>{p.lieu}</td>
                  <td className="muet">{(p.description || p.recit_brut || '').slice(0, 90)}</td>
                  <td><Pastille couleur={COULEUR_GRAVITE[p.gravite]}>{p.gravite_libelle}</Pastille></td>
                  <td><Statut statut={p.statut === 'traitee' ? 'realisee' : p.statut === 'ouverte' ? 'confirmee' : 'brouillon'} libelle={p.statut_libelle} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {donnees.length === 0 && <p className="muet">Aucune plainte.</p>}
        </section>
      )}
    </>
  )
}
