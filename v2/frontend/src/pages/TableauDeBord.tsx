import { Link } from 'react-router-dom'
import { api, formatJour } from '../api'
import { Chargement, EnTete, Erreur, Statut, useCharger } from '../composants/ui'
import { useSession } from '../contexte'
import type { Devis, Fiche } from '../types'

type Tableau = {
  prix_manquants: number
  prochaines_fiches: Fiche[]
  rappels_plats: Fiche[]
  devis_a_mettre_a_jour: Devis[]
  devis_sans_reponse: Devis[]
  bons_a_faire: Devis[]
  compta?: { a_envoyer: number; a_facturer: number }
}

export default function TableauDeBord() {
  const { moi } = useSession()
  const { donnees: t, erreur, chargement } = useCharger(() => api.get<Tableau>('/api/tableau-de-bord'))
  return (
    <>
      <EnTete titre="Tableau de bord" sousTitre={`Bonjour${moi.nom ? ' ' + moi.nom : ''}.`}>
        <Link className="bouton principal" to="/fiches/nouvelle">Nouvelle fiche</Link>
      </EnTete>
      <Erreur message={erreur} />
      <Chargement actif={chargement && !t} />
      {t && (
        <>
          <div className="tuiles">
            <Tuile chiffre={t.prochaines_fiches.length} libelle="fiches dans les 7 jours" vers="/fiches" />
            <Tuile chiffre={t.rappels_plats.length} libelle="sans formule ni plat" alerte />
            <Tuile chiffre={t.devis_a_mettre_a_jour.length} libelle="devis à mettre à jour" alerte vers="/devis" />
            <Tuile chiffre={t.bons_a_faire.length} libelle="bons pour facturation à faire" alerte vers="/devis?statut=accepte" />
            {moi.peut.prix && <Tuile chiffre={t.prix_manquants} libelle="prix manquants" alerte vers="/prix?manquants=1" />}
          </div>

          <section className="carte">
            <h2>Les 7 prochains jours</h2>
            {t.prochaines_fiches.length === 0 ? <p className="muet">Aucune fiche.</p> : (
              <table className="tableau">
                <thead><tr><th>Date</th><th>Heure</th><th>Client</th><th>Couverts</th><th>Espace</th><th>Repas</th><th>Statut</th></tr></thead>
                <tbody>
                  {t.prochaines_fiches.map((f) => (
                    <tr key={f.id}>
                      <td>{formatJour(f.date)}</td>
                      <td>{f.heure}</td>
                      <td><Link to={`/fiches/${f.id}`}>{f.client.nom}</Link></td>
                      <td>{f.couverts}</td>
                      <td>{f.espace}</td>
                      <td>{f.formule_repas ?? (f.lignes.some((l) => l.type !== 'supplement') ? 'plats choisis' : <span className="texte-alerte">à compléter</span>)}</td>
                      <td><Statut statut={f.statut} libelle={f.statut_libelle} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <div className="grille-2">
            <ListeDevis titre="Devis à mettre à jour (la fiche a changé)" liste={t.devis_a_mettre_a_jour} />
            <ListeDevis titre="Devis sans réponse du client" liste={t.devis_sans_reponse} />
            <ListeDevis titre="Événements passés sans bon pour facturation" liste={t.bons_a_faire} />
            <section className="carte">
              <h2>Fiches à compléter</h2>
              {t.rappels_plats.length === 0 ? <p className="muet">Rien à signaler.</p> : (
                <ul className="liste">
                  {t.rappels_plats.map((f) => (
                    <li key={f.id}><Link to={`/fiches/${f.id}`}>{f.client.nom}</Link> — {formatJour(f.date)}, {f.couverts} couverts</li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </>
  )
}

function Tuile({ chiffre, libelle, alerte, vers }: { chiffre: number; libelle: string; alerte?: boolean; vers?: string }) {
  const contenu = (
    <>
      <div className={`tuile-chiffre${alerte && chiffre ? ' texte-alerte' : ''}`}>{chiffre}</div>
      <div className="muet">{libelle}</div>
    </>
  )
  return vers ? <Link to={vers} className="tuile">{contenu}</Link> : <div className="tuile">{contenu}</div>
}

function ListeDevis({ titre, liste }: { titre: string; liste: Devis[] }) {
  return (
    <section className="carte">
      <h2>{titre}</h2>
      {liste.length === 0 ? <p className="muet">Rien à signaler.</p> : (
        <ul className="liste">
          {liste.map((d) => (
            <li key={d.id}>
              <Link to={`/devis/${d.id}`}>{d.reference}</Link> — {d.client_nom}, {formatJour(d.date_evenement)} · {d.total}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
