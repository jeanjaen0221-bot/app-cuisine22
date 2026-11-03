import { Link, useSearchParams } from 'react-router-dom'
import { api, formatJour } from '../api'
import { Chargement, EnTete, Erreur, Statut, useCharger } from '../composants/ui'
import type { Bon } from '../types'

const FILTRES = [
  { cle: '', libelle: 'Tous' }, { cle: 'brouillon,valide', libelle: 'À finaliser' },
  { cle: 'transmis', libelle: 'Chez la compta' }, { cle: 'facture', libelle: 'Facturés' },
]

export default function Bons() {
  const [params, setParams] = useSearchParams()
  const statut = params.get('statut') ?? ''
  const { donnees, erreur, chargement } = useCharger(() => api.get<Bon[]>('/api/bons', { statut }), [statut])
  return (
    <>
      <EnTete titre="Bons pour facturation" sousTitre="Ce qui a réellement été servi, transmis à la compta qui établit la facture. Un bon se prépare depuis un devis accepté." />
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
            <thead><tr><th>N°</th><th>Client</th><th>Événement</th><th>Devis</th><th className="droite">Total TVAC</th><th className="droite">Écart</th><th>Statut</th></tr></thead>
            <tbody>
              {donnees.map((b) => (
                <tr key={b.id}>
                  <td><Link to={`/bons/${b.id}`}>{b.numero}</Link></td>
                  <td>{b.client_nom}</td>
                  <td>{formatJour(b.date_evenement)}</td>
                  <td>{b.devis_reference}</td>
                  <td className="droite">{b.total}</td>
                  <td className="droite">{b.ecart_centimes > 0 ? '+' : ''}{b.ecart}</td>
                  <td><Statut statut={b.statut} libelle={b.statut_libelle} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {donnees.length === 0 && <p className="muet">Aucun bon.</p>}
        </section>
      )}
    </>
  )
}
