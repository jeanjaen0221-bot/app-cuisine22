import { Link, useSearchParams } from 'react-router-dom'
import { api, formatJour } from '../api'
import { Chargement, EnTete, Erreur, Statut, useCharger } from '../composants/ui'
import type { Devis } from '../types'

const FILTRES = [
  { cle: '', libelle: 'En cours' }, { cle: 'brouillon,valide', libelle: 'À valider' },
  { cle: 'transmis,envoye', libelle: 'Chez la compta / le client' }, { cle: 'accepte', libelle: 'Acceptés' },
  { cle: 'refuse', libelle: 'Refusés' },
]

export default function DevisListe() {
  const [params, setParams] = useSearchParams()
  const statut = params.get('statut') ?? ''
  const { donnees, erreur, chargement } = useCharger(() => api.get<Devis[]>('/api/devis', { statut }), [statut])
  return (
    <>
      <EnTete titre="Devis" sousTitre="Prix TVA comprise. Un devis se prépare depuis sa fiche." />
      <div className="onglets">
        {FILTRES.map((f) => (
          <button key={f.cle} className={statut === f.cle ? 'actif' : ''} onClick={() => setParams(f.cle ? { statut: f.cle } : {})}>{f.libelle}</button>
        ))}
      </div>
      <Erreur message={erreur} />
      <Chargement actif={chargement && !donnees} />
      {donnees && (
        <section className="carte">
          <table className="tableau">
            <thead><tr><th>Référence</th><th>Client</th><th>Événement</th><th>Couverts</th><th className="droite">Total TVAC</th><th>Statut</th><th /></tr></thead>
            <tbody>
              {donnees.map((d) => (
                <tr key={d.id}>
                  <td><Link to={`/devis/${d.id}`}>{d.reference}</Link></td>
                  <td>{d.client_nom}</td>
                  <td>{formatJour(d.date_evenement)} {d.heure_evenement}</td>
                  <td>{d.couverts}</td>
                  <td className="droite">{d.total}</td>
                  <td><Statut statut={d.statut} libelle={d.statut_libelle} /></td>
                  <td>
                    {d.manques.length > 0 && <span className="texte-alerte" title={d.manques.join('\n')}>manques</span>}
                    {d.a_mettre_a_jour && <span className="texte-alerte"> à mettre à jour</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {donnees.length === 0 && <p className="muet">Aucun devis.</p>}
        </section>
      )}
    </>
  )
}
