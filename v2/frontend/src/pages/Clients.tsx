import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Chargement, EnTete, Erreur, Pastille, useCharger } from '../composants/ui'
import type { Client } from '../types'

export default function Clients() {
  const [q, setQ] = useState('')
  const [recherche, setRecherche] = useState('')
  const [archives, setArchives] = useState(false)
  const { donnees, erreur, chargement } = useCharger(
    () => api.get<Client[]>('/api/clients', { q: recherche, archives, limite: 200 }), [recherche, archives])
  return (
    <>
      <EnTete titre="Clients">
        <Link className="bouton principal" to="/clients/nouveau">Nouveau client</Link>
      </EnTete>
      <div className="filtres">
        <form onSubmit={(e) => { e.preventDefault(); setRecherche(q) }}>
          <input placeholder="Nom, contact, e-mail, téléphone, n° TVA…" value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
        <label className="case"><input type="checkbox" checked={archives} onChange={(e) => setArchives(e.target.checked)} /> Archivés aussi</label>
      </div>
      <Erreur message={erreur} />
      <Chargement actif={chargement && !donnees} />
      {donnees && (
        <section className="carte">
          <table className="tableau">
            <thead><tr><th>Nom</th><th>Type</th><th>Contact</th><th>E-mail</th><th>Téléphone</th><th>Facturation</th></tr></thead>
            <tbody>
              {donnees.map((c) => (
                <tr key={c.id}>
                  <td><Link to={`/clients/${c.id}`}>{c.nom}</Link> {c.archive && <Pastille couleur="gris">archivé</Pastille>}</td>
                  <td>{c.type === 'entreprise' ? 'Entreprise' : 'Particulier'}</td>
                  <td>{[c.contact_prenom, c.contact_nom].filter(Boolean).join(' ')}</td>
                  <td>{c.email}</td>
                  <td>{c.telephone}</td>
                  <td>{c.manques_facturation.length ? <span className="texte-alerte">à compléter</span> : 'complète'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {donnees.length === 0 && <p className="muet">Aucun client.</p>}
        </section>
      )}
    </>
  )
}
