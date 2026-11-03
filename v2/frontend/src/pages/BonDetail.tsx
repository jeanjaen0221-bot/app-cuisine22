import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, formatInstant, formatJour, ouvrirPdf } from '../api'
import TableauLignes from '../composants/TableauLignes'
import { Alertes, Champ, EnTete, Erreur, Statut, useAction } from '../composants/ui'
import { useSession } from '../contexte'
import type { Bon, LigneDocument, Produit } from '../types'

export default function BonDetail() {
  const { id } = useParams()
  const { moi } = useSession()
  const [b, setB] = useState<Bon | null>(null)
  const [catalogue, setCatalogue] = useState<Produit[]>([])
  const [extra, setExtra] = useState({ produit_id: '', quantite: 1 })
  const [remarques, setRemarques] = useState('')
  const { enCours, erreur, setErreur, lancer } = useAction()

  const appliquer = (bon: Bon) => { setB(bon); setRemarques(bon.remarques_compta ?? '') }

  useEffect(() => {
    api.get<Bon>(`/api/bons/${id}`).then(appliquer).catch((e) => setErreur(e.message))
    api.get<Produit[]>('/api/produits').then((p) => setCatalogue(p.filter((x) => x.actif))).catch(() => {})
  }, [id, setErreur])

  if (!b) return <><Erreur message={erreur} /><p className="muet">Chargement…</p></>

  const modifiable = b.statut === 'brouillon' && moi.peut.devis
  const modifier = async (corps: object) => {
    const r = await lancer(() => api.patch<Bon>(`/api/bons/${b.id}`, { ...corps, version: b.version }))
    if (r) appliquer(r)
  }
  const action = async (nom: string, corps: object = {}) => {
    const r = await lancer(() => api.post<Bon>(`/api/bons/${b.id}/${nom}`, corps))
    if (r) appliquer(r)
  }
  const facturer = () => {
    const numero = window.prompt('Numéro de facture (facultatif) ?') ?? undefined
    action('facture', { numero_facture: numero })
  }

  return (
    <>
      <EnTete titre={`Bon pour facturation ${b.numero}`}
        sousTitre={<><Statut statut={b.statut} libelle={b.statut_libelle} /> · {b.client_nom} · {formatJour(b.date_evenement)} {b.heure_evenement} · devis <Link to={`/devis/${b.devis_id}`}>{b.devis_reference}</Link></>}>
        <button onClick={() => ouvrirPdf(`/api/bons/${b.id}/pdf`)}>{b.transmis_le ? 'PDF transmis' : 'Aperçu PDF'}</button>
      </EnTete>
      <Erreur message={erreur} />
      <Alertes liste={b.alertes} />
      <Alertes titre="À compléter" liste={b.manques} />

      <section className="carte">
        <div className="ligne-champs">
          <Champ libelle="Couverts prévus"><input value={b.couverts_devis} disabled /></Champ>
          <Champ libelle="Couverts réels" aide="Les lignes « par personne » suivent automatiquement.">
            <input type="number" min={1} defaultValue={b.couverts_reels} disabled={!modifiable} key={b.couverts_reels}
              onBlur={(e) => Number(e.target.value) !== b.couverts_reels && modifier({ couverts_reels: Number(e.target.value) })} />
          </Champ>
        </div>
        <TableauLignes lignes={b.lignes} total={b.total} avecPrevu modifiable={modifiable}
          surQuantite={(l: LigneDocument, quantite: number) => modifier({ lignes: [{ id: l.id, quantite }] })}
          surRetirer={(l: LigneDocument) => modifier({ retirer: [l.id] })} />
        <p className="droite">Total du devis : {b.total_devis} · Écart : <strong>{b.ecart_centimes > 0 ? '+' : ''}{b.ecart}</strong></p>
        {modifiable && (
          <div className="ligne-champs">
            <Champ libelle="Ajouter un extra (menu Prix)">
              <select value={extra.produit_id} onChange={(e) => setExtra({ ...extra, produit_id: e.target.value })}>
                <option value="">Choisir…</option>
                {catalogue.map((p) => <option key={p.id} value={p.id}>{p.nom} — {p.prix} ({p.unite_libelle})</option>)}
              </select>
            </Champ>
            <Champ libelle="Quantité"><input type="number" min={1} value={extra.quantite} onChange={(e) => setExtra({ ...extra, quantite: Number(e.target.value) })} /></Champ>
            <button disabled={!extra.produit_id || enCours} onClick={() => { modifier({ ajouter: [extra] }); setExtra({ produit_id: '', quantite: 1 }) }}>Ajouter</button>
          </div>
        )}
      </section>

      <div className="grille-2">
        <section className="carte">
          <h2>Remarques pour la comptabilité</h2>
          <textarea rows={4} value={remarques} disabled={!modifiable} onChange={(e) => setRemarques(e.target.value)} />
          {modifiable && <button onClick={() => modifier({ remarques_compta: remarques })} disabled={enCours}>Enregistrer</button>}
        </section>
        <section className="carte">
          <h2>Étapes</h2>
          <ol className="etapes">
            <li className={b.statut !== 'brouillon' ? 'fait' : ''}>Validé par l'équipe</li>
            <li className={b.transmis_le ? 'fait' : ''}>Transmis à la compta {b.transmis_le && <span className="muet">le {formatInstant(b.transmis_le)}</span>}</li>
            <li className={b.facture_le ? 'fait' : ''}>Facturé par la compta {b.facture_le && <span className="muet">le {formatInstant(b.facture_le)}{b.numero_facture_compta ? ` (n° ${b.numero_facture_compta})` : ''}</span>}</li>
          </ol>
          <div className="pile">
            {b.statut === 'brouillon' && moi.peut.devis_valider && <button className="principal" onClick={() => action('valider')} disabled={enCours}>Valider</button>}
            {b.statut === 'valide' && moi.peut.devis_valider && <>
              <button className="principal" onClick={() => action('transmettre')} disabled={enCours}>Transmettre à la compta</button>
              <button onClick={() => action('devalider')} disabled={enCours}>Repasser en brouillon</button>
            </>}
            {b.statut === 'transmis' && moi.peut.compta && <button className="principal" onClick={facturer} disabled={enCours}>Marquer « facturé »</button>}
          </div>
        </section>
      </div>
    </>
  )
}
