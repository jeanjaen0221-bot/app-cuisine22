import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, formatInstant, formatJour, ouvrirPdf } from '../api'
import { Chargement, EnTete, Erreur, Statut, useAction, useCharger } from '../composants/ui'
import type { Bon, Devis } from '../types'

type Espace = {
  a_envoyer: Devis[]
  attente_reponse: Devis[]
  a_facturer: Bon[]
  historique_devis: Devis[]
  historique_bons: Bon[]
}

export default function Compta() {
  const [onglet, setOnglet] = useState<'envoyer' | 'reponse' | 'facturer' | 'historique'>('envoyer')
  const { donnees: e, erreur, chargement, recharger } = useCharger(() => api.get<Espace>('/api/compta'))
  const action = useAction()

  const faire = async (chemin: string, corps: object = {}) => {
    if (await action.lancer(() => api.post(chemin, corps))) recharger()
  }

  return (
    <>
      <EnTete titre="Espace compta" sousTitre="Devis à envoyer aux clients et bons à facturer. Montants TVA comprise." />
      <div className="onglets">
        <button className={onglet === 'envoyer' ? 'actif' : ''} onClick={() => setOnglet('envoyer')}>À envoyer ({e?.a_envoyer.length ?? 0})</button>
        <button className={onglet === 'reponse' ? 'actif' : ''} onClick={() => setOnglet('reponse')}>En attente de réponse ({e?.attente_reponse.length ?? 0})</button>
        <button className={onglet === 'facturer' ? 'actif' : ''} onClick={() => setOnglet('facturer')}>À facturer ({e?.a_facturer.length ?? 0})</button>
        <button className={onglet === 'historique' ? 'actif' : ''} onClick={() => setOnglet('historique')}>Historique</button>
      </div>
      <Erreur message={erreur || action.erreur} />
      <Chargement actif={chargement && !e} />
      {e && onglet === 'envoyer' && (
        <TableDevis liste={e.a_envoyer} actions={(d) => <>
          <button onClick={() => ouvrirPdf(`/api/devis/${d.id}/pdf`)}>PDF</button>
          <button className="principal" disabled={action.enCours} onClick={() => faire(`/api/devis/${d.id}/envoye`)}>Envoyé au client</button>
        </>} />
      )}
      {e && onglet === 'reponse' && (
        <TableDevis liste={e.attente_reponse} actions={(d) => <>
          <button onClick={() => ouvrirPdf(`/api/devis/${d.id}/pdf`)}>PDF</button>
          <button disabled={action.enCours} onClick={() => faire(`/api/devis/${d.id}/accepte`)}>Accepté</button>
          <button disabled={action.enCours} onClick={() => faire(`/api/devis/${d.id}/refuse`)}>Refusé</button>
        </>} />
      )}
      {e && onglet === 'facturer' && (
        <TableBons liste={e.a_facturer} actions={(b) => <>
          <button onClick={() => ouvrirPdf(`/api/bons/${b.id}/pdf`)}>PDF</button>
          <button className="principal" disabled={action.enCours} onClick={() => {
            const numero = window.prompt('Numéro de facture (facultatif) ?')
            if (numero !== null) faire(`/api/bons/${b.id}/facture`, { numero_facture: numero })
          }}>Facturé</button>
        </>} />
      )}
      {e && onglet === 'historique' && (
        <>
          <h2>Devis</h2>
          <TableDevis liste={e.historique_devis} actions={(d) => <button onClick={() => ouvrirPdf(`/api/devis/${d.id}/pdf`)}>PDF</button>} />
          <h2>Bons facturés</h2>
          <TableBons liste={e.historique_bons} actions={(b) => <button onClick={() => ouvrirPdf(`/api/bons/${b.id}/pdf`)}>PDF</button>} />
        </>
      )}
    </>
  )
}

function TableDevis({ liste, actions }: { liste: Devis[]; actions: (d: Devis) => React.ReactNode }) {
  if (!liste.length) return <p className="muet">Rien pour le moment.</p>
  return (
    <section className="carte">
      <table className="tableau">
        <thead><tr><th>Devis</th><th>Client</th><th>Événement</th><th className="droite">Total TVAC</th><th>Transmis</th><th>Statut</th><th /></tr></thead>
        <tbody>
          {liste.map((d) => (
            <tr key={d.id}>
              <td><Link to={`/devis/${d.id}`}>{d.reference}</Link></td>
              <td>{d.client_nom}</td>
              <td>{formatJour(d.date_evenement)}</td>
              <td className="droite">{d.total}</td>
              <td>{formatInstant(d.transmis_le)}</td>
              <td><Statut statut={d.statut} libelle={d.statut_libelle} /></td>
              <td className="actions-ligne">{actions(d)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function TableBons({ liste, actions }: { liste: Bon[]; actions: (b: Bon) => React.ReactNode }) {
  if (!liste.length) return <p className="muet">Rien pour le moment.</p>
  return (
    <section className="carte">
      <table className="tableau">
        <thead><tr><th>Bon</th><th>Client</th><th>Événement</th><th>Devis</th><th className="droite">Total TVAC</th><th>Statut</th><th /></tr></thead>
        <tbody>
          {liste.map((b) => (
            <tr key={b.id}>
              <td><Link to={`/bons/${b.id}`}>{b.numero}</Link></td>
              <td>{b.client_nom}</td>
              <td>{formatJour(b.date_evenement)}</td>
              <td>{b.devis_reference}</td>
              <td className="droite">{b.total}</td>
              <td><Statut statut={b.statut} libelle={b.statut_libelle} />{b.numero_facture_compta && <span className="muet"> n° {b.numero_facture_compta}</span>}</td>
              <td className="actions-ligne">{actions(b)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
