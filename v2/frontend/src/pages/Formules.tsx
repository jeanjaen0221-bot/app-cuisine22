import { FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Champ, EnTete, Erreur, Pastille, useAction, useCharger } from '../composants/ui'
import { useSession } from '../contexte'
import type { FormuleBoissons, FormuleRepas, Produit } from '../types'

type Liste = { repas: FormuleRepas[]; boissons: FormuleBoissons[] }

const COMPORTEMENTS = {
  services: 'Services (plats facultatifs ; s\'il y en a, la formule est déduite des plats)',
  carte: 'À la carte (chaque plat compté à son prix)',
  sans_plats: 'Sans plats (suppléments seulement, comme Brunch ou Sharing)',
}
const MODES = { formule: 'Formule (au devis)', consommation: 'À la consommation (au bon pour facturation)', aucune: 'Aucune' }
const COULEURS = ['bleu', 'rouge', 'cyan', 'violet', 'vert', 'ambre', 'indigo', 'gris']

export default function Formules() {
  const { moi, rechargerReferences } = useSession()
  const peut = moi.peut.prix
  const { donnees: f, erreur, recharger } = useCharger(() => api.get<Liste>('/api/formules'))
  const { donnees: produits } = useCharger(() => api.get<Produit[]>('/api/produits'))
  const action = useAction()
  const [repas, setRepas] = useState({ nom: '', comportement: 'services', nb_services: 2 })
  const [boissons, setBoissons] = useState({ nom: '', mode: 'formule', base_produit_id: '', coupe_produit_id: '', couleur: 'bleu' })

  const bases = (produits ?? []).filter((p) => p.categorie === 'formule_boissons')
  const coupes = (produits ?? []).filter((p) => p.categorie === 'coupe')

  const enregistrer = async (chemin: string, corps: object, methode: 'post' | 'patch' = 'patch') => {
    const r = await action.lancer(() => (methode === 'post' ? api.post(chemin, corps) : api.patch(chemin, corps)))
    if (r) { recharger(); rechargerReferences() }
    return r
  }
  const supprimer = async (genre: string, id: string) => {
    if (!window.confirm('Supprimer cette formule ?')) return
    if (await action.lancer(() => api.delete(`/api/formules/${genre}/${id}`))) { recharger(); rechargerReferences() }
  }

  const ajouterRepas = async (e: FormEvent) => {
    e.preventDefault()
    if (await enregistrer('/api/formules/repas', repas, 'post')) setRepas({ ...repas, nom: '' })
  }
  const ajouterBoissons = async (e: FormEvent) => {
    e.preventDefault()
    if (await enregistrer('/api/formules/boissons', boissons, 'post')) setBoissons({ ...boissons, nom: '' })
  }

  return (
    <>
      <EnTete titre="Formules" sousTitre={<>Ce qu'on choisit sur une fiche. Les prix viennent du menu <Link to="/prix">Prix</Link>. Une formule désactivée disparaît des choix ; les fiches qui l'utilisent la gardent.</>} />
      {!peut && <div className="bandeau info">Lecture seule : seuls les administrateurs (ou le droit « prix ») modifient les formules.</div>}
      <Erreur message={erreur || action.erreur} />

      <section className="carte">
        <h2>Formules repas</h2>
        <table className="tableau">
          <thead><tr><th>Ordre</th><th>Nom</th><th>Fonctionnement</th><th className="droite">Prix</th><th>Active</th><th /></tr></thead>
          <tbody>
            {f?.repas.map((r) => (
              <tr key={r.id} className={r.actif ? '' : 'inactif'}>
                <td className="etroit"><input type="number" disabled={!peut} defaultValue={r.ordre} onBlur={(e) => Number(e.target.value) !== r.ordre && enregistrer(`/api/formules/repas/${r.id}`, { ordre: Number(e.target.value) })} /></td>
                <td><input disabled={!peut} defaultValue={r.nom} key={r.nom} onBlur={(e) => e.target.value !== r.nom && enregistrer(`/api/formules/repas/${r.id}`, { nom: e.target.value })} /></td>
                <td>
                  <select disabled={!peut} value={r.comportement} onChange={(e) => enregistrer(`/api/formules/repas/${r.id}`, { comportement: e.target.value, nb_services: r.nb_services ?? 2 })}>
                    {Object.entries(COMPORTEMENTS).map(([cle, l]) => <option key={cle} value={cle}>{l}</option>)}
                  </select>
                  {r.comportement === 'services' && (
                    <select disabled={!peut} value={r.nb_services ?? 2} onChange={(e) => enregistrer(`/api/formules/repas/${r.id}`, { nb_services: Number(e.target.value) })}>
                      <option value={1}>1 service</option><option value={2}>2 services</option><option value={3}>3 services</option>
                    </select>
                  )}
                </td>
                <td className="droite">{r.prix_centimes === null && r.comportement !== 'carte'
                  ? <Link className="texte-alerte" to={`/prix?produit=${r.produit_id}`}>prix manquant</Link> : r.prix}</td>
                <td><input type="checkbox" disabled={!peut} checked={r.actif} onChange={(e) => enregistrer(`/api/formules/repas/${r.id}`, { actif: e.target.checked })} /></td>
                <td>{peut && !r.utilisee && <button className="lien" onClick={() => supprimer('repas', r.id)}>supprimer</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {peut && (
          <form className="ligne-champs" onSubmit={ajouterRepas}>
            <Champ libelle="Nouvelle formule repas"><input value={repas.nom} onChange={(e) => setRepas({ ...repas, nom: e.target.value })} required /></Champ>
            <Champ libelle="Fonctionnement">
              <select value={repas.comportement} onChange={(e) => setRepas({ ...repas, comportement: e.target.value })}>
                {Object.entries(COMPORTEMENTS).map(([cle, l]) => <option key={cle} value={cle}>{l}</option>)}
              </select>
            </Champ>
            {repas.comportement === 'services' && (
              <Champ libelle="Services">
                <select value={repas.nb_services} onChange={(e) => setRepas({ ...repas, nb_services: Number(e.target.value) })}>
                  <option value={1}>1</option><option value={2}>2</option><option value={3}>3</option>
                </select>
              </Champ>
            )}
            <button className="principal" disabled={action.enCours}>Ajouter</button>
          </form>
        )}
        <p className="aide">Une nouvelle formule crée sa ligne dans le menu Prix, à compléter.</p>
      </section>

      <section className="carte">
        <h2>Formules boissons</h2>
        <table className="tableau">
          <thead><tr><th>Ordre</th><th>Nom</th><th>Mode</th><th>Base</th><th>Coupe</th><th className="droite">Prix par personne</th><th>Badge</th><th>Par défaut</th><th>Active</th><th /></tr></thead>
          <tbody>
            {f?.boissons.map((b) => (
              <tr key={b.id} className={b.actif ? '' : 'inactif'}>
                <td className="etroit"><input type="number" disabled={!peut} defaultValue={b.ordre} onBlur={(e) => Number(e.target.value) !== b.ordre && enregistrer(`/api/formules/boissons/${b.id}`, { ordre: Number(e.target.value) })} /></td>
                <td><input disabled={!peut} defaultValue={b.nom} key={b.nom} onBlur={(e) => e.target.value !== b.nom && enregistrer(`/api/formules/boissons/${b.id}`, { nom: e.target.value })} /></td>
                <td>
                  <select disabled={!peut} value={b.mode} onChange={(e) => enregistrer(`/api/formules/boissons/${b.id}`, { mode: e.target.value, base_produit_id: b.base_produit_id ?? bases[0]?.id })}>
                    {Object.entries(MODES).map(([cle, l]) => <option key={cle} value={cle}>{l}</option>)}
                  </select>
                </td>
                <td>
                  {b.mode === 'formule' && (
                    <select disabled={!peut} value={b.base_produit_id ?? ''} onChange={(e) => enregistrer(`/api/formules/boissons/${b.id}`, { base_produit_id: e.target.value || null })}>
                      <option value="">aucune</option>
                      {bases.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
                    </select>
                  )}
                </td>
                <td>
                  {b.mode === 'formule' && (
                    <select disabled={!peut} value={b.coupe_produit_id ?? ''} onChange={(e) => enregistrer(`/api/formules/boissons/${b.id}`, { coupe_produit_id: e.target.value || null })}>
                      <option value="">aucune</option>
                      {coupes.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
                    </select>
                  )}
                </td>
                <td className="droite">{b.prix}</td>
                <td>
                  <select disabled={!peut} value={b.couleur} onChange={(e) => enregistrer(`/api/formules/boissons/${b.id}`, { couleur: e.target.value })}>
                    {COULEURS.map((c) => <option key={c}>{c}</option>)}
                  </select>
                  <Pastille couleur={b.couleur}>{b.nom}</Pastille>
                </td>
                <td><input type="radio" name="defaut" disabled={!peut} checked={b.par_defaut} onChange={() => enregistrer(`/api/formules/boissons/${b.id}`, { par_defaut: true })} /></td>
                <td><input type="checkbox" disabled={!peut} checked={b.actif} onChange={(e) => enregistrer(`/api/formules/boissons/${b.id}`, { actif: e.target.checked })} /></td>
                <td>{peut && !b.utilisee && <button className="lien" onClick={() => supprimer('boissons', b.id)}>supprimer</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {peut && (
          <form className="ligne-champs" onSubmit={ajouterBoissons}>
            <Champ libelle="Nouvelle formule boissons"><input value={boissons.nom} onChange={(e) => setBoissons({ ...boissons, nom: e.target.value })} required /></Champ>
            <Champ libelle="Mode">
              <select value={boissons.mode} onChange={(e) => setBoissons({ ...boissons, mode: e.target.value })}>
                {Object.entries(MODES).map(([cle, l]) => <option key={cle} value={cle}>{l}</option>)}
              </select>
            </Champ>
            {boissons.mode === 'formule' && <>
              <Champ libelle="Base">
                <select value={boissons.base_produit_id} onChange={(e) => setBoissons({ ...boissons, base_produit_id: e.target.value })}>
                  <option value="">aucune</option>
                  {bases.map((p) => <option key={p.id} value={p.id}>{p.nom} ({p.prix})</option>)}
                </select>
              </Champ>
              <Champ libelle="Coupe">
                <select value={boissons.coupe_produit_id} onChange={(e) => setBoissons({ ...boissons, coupe_produit_id: e.target.value })}>
                  <option value="">aucune</option>
                  {coupes.map((p) => <option key={p.id} value={p.id}>{p.nom} ({p.prix})</option>)}
                </select>
              </Champ>
            </>}
            <Champ libelle="Badge">
              <select value={boissons.couleur} onChange={(e) => setBoissons({ ...boissons, couleur: e.target.value })}>
                {COULEURS.map((c) => <option key={c}>{c}</option>)}
              </select>
            </Champ>
            <button className="principal" disabled={action.enCours}>Ajouter</button>
          </form>
        )}
        <p className="aide">Le prix d'une formule boissons = prix de la base + prix de la coupe (menu Prix). Pour une nouvelle base ou coupe, l'ajouter d'abord dans le menu Prix.</p>
      </section>
    </>
  )
}
