import { Link } from 'react-router-dom'
import type { LigneDocument } from '../types'

/** Lignes d'un devis ou d'un bon : montants TVA comprise, prix manquants signalés. */
export default function TableauLignes({ lignes, total, avecPrevu, modifiable, surQuantite, surRetirer, lienPrix }: {
  lignes: LigneDocument[]
  total: string
  avecPrevu?: boolean
  modifiable?: boolean
  surQuantite?: (ligne: LigneDocument, quantite: number) => void
  surRetirer?: (ligne: LigneDocument) => void
  lienPrix?: boolean
}) {
  return (
    <table className="tableau">
      <thead>
        <tr>
          <th>Désignation</th>
          {avecPrevu && <th className="droite">Prévu</th>}
          <th className="droite">Qté</th>
          <th>Unité</th>
          <th className="droite">Prix unitaire</th>
          <th className="droite">Total</th>
          {modifiable && <th />}
        </tr>
      </thead>
      <tbody>
        {lignes.map((l) => (
          <tr key={l.id} className={l.prix_unitaire_centimes === null ? 'ligne-alerte' : ''}>
            <td>{l.libelle} {l.extra && <span className="pastille ambre">extra</span>}</td>
            {avecPrevu && <td className="droite">{l.quantite_devis || '—'}</td>}
            <td className="droite">
              {modifiable && surQuantite
                ? <input className="etroit" type="number" min={0} defaultValue={l.quantite}
                    onBlur={(e) => Number(e.target.value) !== l.quantite && surQuantite(l, Number(e.target.value))} />
                : l.quantite}
            </td>
            <td>{l.unite_libelle}</td>
            <td className="droite">
              {l.prix_unitaire_centimes === null && lienPrix && l.produit_id
                ? <Link to={`/prix?produit=${l.produit_id}`} className="texte-alerte">Compléter le prix</Link>
                : l.prix_unitaire}
            </td>
            <td className="droite">{l.total}</td>
            {modifiable && <td>{l.extra && surRetirer && <button type="button" className="lien" onClick={() => surRetirer(l)}>retirer</button>}</td>}
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <td colSpan={avecPrevu ? 5 : 4} className="droite"><strong>Total TVA comprise</strong></td>
          <td className="droite"><strong>{total}</strong></td>
          {modifiable && <td />}
        </tr>
      </tfoot>
    </table>
  )
}
