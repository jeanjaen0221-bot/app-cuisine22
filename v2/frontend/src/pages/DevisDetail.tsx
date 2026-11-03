import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, formatDate, formatInstant, formatJour, ouvrirPdf } from '../api'
import TableauLignes from '../composants/TableauLignes'
import { Alertes, Champ, EnTete, Erreur, Statut, useAction } from '../composants/ui'
import { useSession } from '../contexte'
import type { Bon, Devis } from '../types'

export default function DevisDetail() {
  const { id } = useParams()
  const naviguer = useNavigate()
  const { moi, rechargerCompteur } = useSession()
  const [d, setD] = useState<Devis | null>(null)
  const [remarques, setRemarques] = useState({ remarques_client: '', remarques_compta: '', date_validite: '' })
  const { enCours, erreur, setErreur, lancer } = useAction()

  const appliquer = (devis: Devis) => {
    setD(devis)
    setRemarques({ remarques_client: devis.remarques_client ?? '', remarques_compta: devis.remarques_compta ?? '', date_validite: devis.date_validite })
  }

  useEffect(() => {
    api.get<Devis>(`/api/devis/${id}`).then(appliquer).catch((e) => setErreur(e.message))
    rechargerCompteur()
  }, [id, setErreur, rechargerCompteur])

  if (!d) return <><Erreur message={erreur} /><p className="muet">Chargement…</p></>

  const action = async (nom: string, corps: object = {}) => {
    const r = await lancer(() => api.post<Devis | Bon>(`/api/devis/${d.id}/${nom}`, corps))
    if (!r) return
    if (nom === 'bon') naviguer(`/bons/${r.id}`)
    else if (nom === 'nouvelle-version') naviguer(`/devis/${r.id}`)
    else appliquer(r as Devis)
  }

  const enregistrerRemarques = async () => {
    const r = await lancer(() => api.patch<Devis>(`/api/devis/${d.id}`, remarques))
    if (r) appliquer(r)
  }

  const brouillon = d.statut === 'brouillon' || d.statut === 'valide'
  const p = moi.peut
  return (
    <>
      <EnTete titre={`Devis ${d.reference}`} sousTitre={<><Statut statut={d.statut} libelle={d.statut_libelle} /> · {d.client_nom} · {formatJour(d.date_evenement)} {d.heure_evenement} · {d.couverts} couverts</>}>
        <button onClick={() => ouvrirPdf(`/api/devis/${d.id}/pdf`)}>{d.transmis_le ? 'PDF transmis' : 'Aperçu PDF'}</button>
        {p.fiches && <Link className="bouton" to={`/fiches/${d.fiche_id}`}>Voir la fiche</Link>}
      </EnTete>
      <Erreur message={erreur} />
      <Alertes titre="À compléter avant de valider" liste={d.manques} />
      <Alertes liste={d.alertes} />
      {d.a_mettre_a_jour && d.statut !== 'remplace' && (
        <div className="bandeau attention">
          La fiche a changé depuis ce devis.
          {brouillon && p.devis && <button onClick={() => action('actualiser')} disabled={enCours}>Actualiser le devis</button>}
          {!brouillon && p.devis && ['transmis', 'envoye', 'accepte', 'refuse'].includes(d.statut) &&
            <button onClick={() => action('nouvelle-version')} disabled={enCours}>Créer une nouvelle version</button>}
        </div>
      )}
      {d.version_suivante_id && <div className="bandeau info">Remplacé par <Link to={`/devis/${d.version_suivante_id}`}>une nouvelle version</Link>.</div>}

      <section className="carte">
        <TableauLignes lignes={d.lignes} total={d.total} lienPrix={p.prix} />
        <p className="aide">Prix TVA comprise, repris du menu Prix au moment du calcul. Valable jusqu'au {formatDate(d.date_validite)}.</p>
      </section>

      <div className="grille-2">
        <section className="carte">
          <h2>Remarques</h2>
          <Champ libelle="Pour le client (imprimées sur le devis)" large>
            <textarea rows={3} disabled={!brouillon} value={remarques.remarques_client} onChange={(e) => setRemarques({ ...remarques, remarques_client: e.target.value })} />
          </Champ>
          <Champ libelle="Pour la comptabilité" large>
            <textarea rows={3} disabled={!brouillon} value={remarques.remarques_compta} onChange={(e) => setRemarques({ ...remarques, remarques_compta: e.target.value })} />
          </Champ>
          <Champ libelle="Valable jusqu'au">
            <input type="date" disabled={!brouillon} value={remarques.date_validite} onChange={(e) => setRemarques({ ...remarques, date_validite: e.target.value })} />
          </Champ>
          {brouillon && p.devis && <button onClick={enregistrerRemarques} disabled={enCours}>Enregistrer les remarques</button>}
        </section>

        <section className="carte">
          <h2>Étapes</h2>
          <ol className="etapes">
            <li className={d.statut !== 'brouillon' ? 'fait' : ''}>Validé par l'équipe</li>
            <li className={d.transmis_le ? 'fait' : ''}>Transmis à la compta {d.transmis_le && <span className="muet">le {formatInstant(d.transmis_le)} par {d.transmis_par}</span>}</li>
            <li className={d.envoye_le ? 'fait' : ''}>Envoyé au client par la compta {d.envoye_le && <span className="muet">le {formatInstant(d.envoye_le)}</span>}</li>
            <li className={d.reponse_le ? 'fait' : ''}>Réponse du client {d.reponse_le && <span className="muet">le {formatInstant(d.reponse_le)}</span>}</li>
          </ol>
          <div className="pile">
            {d.statut === 'brouillon' && p.devis && <button onClick={() => action('actualiser')} disabled={enCours}>Recalculer depuis la fiche</button>}
            {d.statut === 'brouillon' && p.devis_valider && <button className="principal" onClick={() => action('valider')} disabled={enCours}>Valider</button>}
            {d.statut === 'valide' && p.devis_valider && <>
              <button className="principal" onClick={() => action('transmettre')} disabled={enCours}>Transmettre à la compta</button>
              <button onClick={() => action('devalider')} disabled={enCours}>Repasser en brouillon</button>
            </>}
            {d.statut === 'transmis' && p.compta && <button className="principal" onClick={() => action('envoye')} disabled={enCours}>Marquer « envoyé au client »</button>}
            {['transmis', 'envoye'].includes(d.statut) && (p.compta || p.devis_valider) && <>
              <button onClick={() => action('accepte')} disabled={enCours}>Le client accepte</button>
              <button onClick={() => action('refuse')} disabled={enCours}>Le client refuse</button>
            </>}
            {d.statut === 'accepte' && p.devis && <button className="principal" onClick={() => action('bon')} disabled={enCours}>Préparer le bon pour facturation</button>}
            {['transmis', 'envoye', 'accepte', 'refuse'].includes(d.statut) && p.devis && !d.a_mettre_a_jour &&
              <button onClick={() => action('nouvelle-version')} disabled={enCours}>Nouvelle version</button>}
          </div>
        </section>
      </div>
    </>
  )
}
