import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, formatInstant, ouvrirPdf } from '../api'
import ChoixClient from '../composants/ChoixClient'
import { Alertes, Champ, EnTete, Erreur, Statut, useAction } from '../composants/ui'
import { useSession } from '../contexte'
import type { Devis, Fiche, LigneFiche, Produit } from '../types'

type Formulaire = {
  client: { id: string; nom: string } | null
  date: string
  heure: string
  couverts: number
  espace: string
  formule_repas: string
  formule_boissons: string
  privatisation: string
  allergenes: string[]
  lignes: LigneFiche[]
  notes_salle: string
  notes_cuisine: string
  contact_sur_place: string
  telephone_sur_place: string
}

const VIDE: Formulaire = {
  client: null, date: '', heure: '', couverts: 2, espace: 'salle', formule_repas: '', formule_boissons: '',
  privatisation: '', allergenes: [], lignes: [], notes_salle: '', notes_cuisine: '', contact_sur_place: '',
  telephone_sur_place: '',
}

const TRANSITIONS: Record<string, { cible: string; libelle: string; principal?: boolean }[]> = {
  brouillon: [{ cible: 'confirmee', libelle: 'Confirmer', principal: true }],
  confirmee: [{ cible: 'finale', libelle: 'Passer en version finale', principal: true }, { cible: 'brouillon', libelle: 'Repasser en brouillon' }],
  finale: [{ cible: 'realisee', libelle: 'Marquer réalisée', principal: true }, { cible: 'confirmee', libelle: 'Rouvrir' }],
  realisee: [{ cible: 'finale', libelle: 'Rouvrir' }],
  annulee: [{ cible: 'brouillon', libelle: 'Rétablir en brouillon' }],
}

function depuisFiche(f: Fiche): Formulaire {
  return {
    client: { id: f.client.id, nom: f.client.nom }, date: f.date, heure: f.heure, couverts: f.couverts,
    espace: f.espace, formule_repas: f.formule_repas ?? '', formule_boissons: f.formule_boissons ?? '',
    privatisation: f.privatisation ?? '', allergenes: f.allergenes, lignes: f.lignes,
    notes_salle: f.notes_salle ?? '', notes_cuisine: f.notes_cuisine ?? '',
    contact_sur_place: f.contact_sur_place ?? '', telephone_sur_place: f.telephone_sur_place ?? '',
  }
}

export default function FicheEdition() {
  const { id } = useParams()
  const naviguer = useNavigate()
  const { references, moi } = useSession()
  const [fiche, setFiche] = useState<Fiche | null>(null)
  const [f, setF] = useState<Formulaire>(VIDE)
  const [modifie, setModifie] = useState(false)
  const [catalogue, setCatalogue] = useState<Produit[]>([])
  const [historique, setHistorique] = useState<{ le: string; utilisateur: string; canal: string; resume: string; action: string }[]>([])
  const { enCours, erreur, setErreur, lancer } = useAction()

  const charger = async () => {
    if (!id) return
    const donnees = await api.get<Fiche>(`/api/fiches/${id}`)
    setFiche(donnees)
    setF(depuisFiche(donnees))
    setModifie(false)
    api.get<typeof historique>('/api/journal', { objet_type: 'fiche', objet_id: id, limite: 30 }).then(setHistorique).catch(() => {})
  }

  useEffect(() => {
    if (id) charger().catch((e) => setErreur(String(e.message ?? e)))
    else {
      setFiche(null)
      setF(VIDE)
    }
    api.get<Produit[]>('/api/produits').then((p) => setCatalogue(p.filter((x) => x.actif))).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  useEffect(() => {
    // Formule boissons par défaut à la création.
    if (!id && references && !f.formule_boissons) {
      const defaut = references.formules_boissons.find((b) => b.par_defaut)
      if (defaut) setF((x) => ({ ...x, formule_boissons: defaut.nom }))
    }
  }, [id, references, f.formule_boissons])

  const maj = (changement: Partial<Formulaire>) => { setF((x) => ({ ...x, ...changement })); setModifie(true) }
  const fige = fiche?.figee ?? false

  const formuleRepas = references?.formules_repas.find((r) => r.nom === f.formule_repas)
  const sansPlats = formuleRepas?.comportement === 'sans_plats'
  const typesPermis = (references?.types_ligne ?? []).filter((t) => !sansPlats || t.cle === 'supplement')
  const aDesPlats = f.lignes.some((l) => l.type !== 'supplement')
  const totaux = useMemo(() => {
    const t: Record<string, number> = { entree: 0, plat: 0, dessert: 0 }
    for (const l of f.lignes) if (l.type in t) t[l.type] += Number(l.quantite) || 0
    return t
  }, [f.lignes])

  const suggestions = (type: string) => catalogue.filter((p) =>
    type === 'supplement' ? ['supplement', 'coupe'].includes(p.categorie) : p.categorie === type)

  const enregistrer = async (e: FormEvent) => {
    e.preventDefault()
    const corps = {
      client_id: f.client?.id, date: f.date, heure: f.heure, couverts: Number(f.couverts), espace: f.espace,
      formule_repas: f.formule_repas, formule_boissons: f.formule_boissons, privatisation: f.privatisation || 'aucune',
      allergenes: f.allergenes, notes_salle: f.notes_salle, notes_cuisine: f.notes_cuisine,
      contact_sur_place: f.contact_sur_place, telephone_sur_place: f.telephone_sur_place,
      lignes: f.lignes.filter((l) => l.libelle.trim()).map((l) => ({
        type: l.type, libelle: l.libelle, quantite: Number(l.quantite), commentaire: l.commentaire || null,
      })),
    }
    const resultat = await lancer(() => fiche
      ? api.patch<Fiche>(`/api/fiches/${fiche.id}`, { ...corps, version: fiche.version })
      : api.post<Fiche>('/api/fiches', corps))
    if (!resultat) return
    if (!fiche) naviguer(`/fiches/${resultat.id}`, { replace: true })
    else { setFiche(resultat); setF(depuisFiche(resultat)); setModifie(false) }
  }

  const changerStatut = async (cible: string) => {
    let motif: string | null = null
    if (cible === 'annulee') {
      motif = window.prompt('Motif de l\'annulation ?')
      if (!motif) return
    }
    const r = await lancer(() => api.post<Fiche>(`/api/fiches/${fiche!.id}/statut`, { statut: cible, version: fiche!.version, motif }))
    if (r) { setFiche(r); setF(depuisFiche(r)) }
  }

  const preparerDevis = async () => {
    const d = await lancer(() => api.post<Devis>(`/api/fiches/${fiche!.id}/devis`))
    if (d) naviguer(`/devis/${d.id}`)
  }

  const dupliquer = async () => {
    const date = window.prompt('Date de la copie (AAAA-MM-JJ) ?', fiche!.date)
    if (!date) return
    const copie = await lancer(() => api.post<Fiche>(`/api/fiches/${fiche!.id}/dupliquer`, { date }))
    if (copie) naviguer(`/fiches/${copie.id}`)
  }

  const ligne = (i: number, changement: Partial<LigneFiche>) =>
    maj({ lignes: f.lignes.map((l, j) => (j === i ? { ...l, ...changement } : l)) })

  return (
    <form onSubmit={enregistrer}>
      <EnTete
        titre={fiche ? `Fiche — ${fiche.client.nom}` : 'Nouvelle fiche'}
        sousTitre={fiche && <><Statut statut={fiche.statut} libelle={fiche.statut_libelle} /> version {fiche.version}
          {fiche.dernier_pdf_le ? ` · imprimée le ${formatInstant(fiche.dernier_pdf_le)}` : ' · pas encore imprimée depuis la dernière modification'}</>}
      >
        {fiche && <>
          <button type="button" onClick={() => ouvrirPdf(`/api/fiches/${fiche.id}/pdf?variante=salle`)}>PDF salle</button>
          <button type="button" onClick={() => ouvrirPdf(`/api/fiches/${fiche.id}/pdf?variante=cuisine`)}>PDF cuisine</button>
          <button type="button" onClick={() => ouvrirPdf(`/api/fiches/${fiche.id}/pdf`)}>PDF complet</button>
        </>}
        {!fige && <button className="principal" disabled={enCours || (!!fiche && !modifie)}>Enregistrer</button>}
      </EnTete>

      <Erreur message={erreur} />
      <Alertes liste={fiche?.alertes} />
      {fiche?.statut === 'annulee' && <div className="bandeau erreur">Annulée : {fiche.motif_annulation}</div>}
      {fige && fiche?.statut !== 'annulee' && <div className="bandeau info">Fiche figée : la rouvrir pour la modifier.</div>}

      <div className="grille-fiche">
        <div>
          <section className="carte">
            <h2>Événement</h2>
            <Champ libelle="Client" large>
              <ChoixClient valeur={f.client} surChoix={(client) => maj({ client })} desactive={fige} />
            </Champ>
            <fieldset disabled={fige} className="ligne-champs">
              <Champ libelle="Date"><input type="date" value={f.date} onChange={(e) => maj({ date: e.target.value })} required /></Champ>
              <Champ libelle="Heure d'arrivée">
                <input type="time" value={f.heure} onChange={(e) => maj({ heure: e.target.value })} required list="heures" />
                <datalist id="heures">{references?.heures_proposees.map((h) => <option key={h} value={h} />)}</datalist>
              </Champ>
              <Champ libelle="Couverts"><input type="number" min={1} max={500} value={f.couverts} onChange={(e) => maj({ couverts: Number(e.target.value) })} required /></Champ>
              <Champ libelle="Espace">
                <select value={f.espace} onChange={(e) => maj({ espace: e.target.value })}>
                  {references?.espaces.map((e) => <option key={e}>{e}</option>)}
                </select>
              </Champ>
              <Champ libelle="Privatisation">
                <select value={f.privatisation} onChange={(e) => maj({ privatisation: e.target.value })}>
                  <option value="">Aucune</option>
                  {references?.privatisations.map((p) => <option key={p.id} value={p.nom}>{p.nom} ({p.prix})</option>)}
                </select>
              </Champ>
            </fieldset>
            <fieldset disabled={fige} className="ligne-champs">
              <Champ libelle="Contact sur place"><input value={f.contact_sur_place} onChange={(e) => maj({ contact_sur_place: e.target.value })} /></Champ>
              <Champ libelle="Téléphone sur place"><input value={f.telephone_sur_place} onChange={(e) => maj({ telephone_sur_place: e.target.value })} /></Champ>
            </fieldset>
          </section>

          <section className="carte">
            <h2>Repas et boissons</h2>
            <fieldset disabled={fige} className="ligne-champs">
              <Champ libelle="Formule repas">
                <select value={f.formule_repas} onChange={(e) => maj({ formule_repas: e.target.value })}>
                  <option value="">— (plats choisis ou à définir)</option>
                  {references?.formules_repas.map((r) => <option key={r.id} value={r.nom}>{r.nom} — {r.prix}</option>)}
                </select>
              </Champ>
              <Champ libelle="Formule boissons">
                <select value={f.formule_boissons} onChange={(e) => maj({ formule_boissons: e.target.value })}>
                  <option value="">—</option>
                  {references?.formules_boissons.map((b) => <option key={b.id} value={b.nom}>{b.nom} — {b.prix}</option>)}
                </select>
              </Champ>
            </fieldset>
            {formuleRepas?.comportement === 'services' && aDesPlats && (
              <p className="aide">Des plats sont listés : à l'enregistrement, la formule est retirée (les plats prévalent) et le devis compte la formule correspondant aux plats.</p>
            )}
            {sansPlats && <p className="aide">{formuleRepas?.nom} : pas d'entrée, de plat ni de dessert, seulement des suppléments.</p>}
            {formuleRepas?.comportement === 'carte' && <p className="aide">À la carte : chaque plat est compté à son prix du menu Prix.</p>}

            <table className="tableau lignes">
              <thead><tr><th>Type</th><th>Libellé</th><th>Qté</th><th>Commentaire</th><th /></tr></thead>
              <tbody>
                {f.lignes.map((l, i) => (
                  <tr key={i}>
                    <td>
                      <select value={l.type} disabled={fige} onChange={(e) => ligne(i, { type: e.target.value })}>
                        {(references?.types_ligne ?? []).map((t) => <option key={t.cle} value={t.cle}>{t.libelle}</option>)}
                      </select>
                    </td>
                    <td>
                      <input value={l.libelle} disabled={fige} list={`catalogue-${l.type}`} onChange={(e) => ligne(i, { libelle: e.target.value })} />
                      {l.hors_catalogue && <span className="aide">hors menu Prix</span>}
                    </td>
                    <td className="etroit"><input type="number" min={1} value={l.quantite} disabled={fige} onChange={(e) => ligne(i, { quantite: Number(e.target.value) })} /></td>
                    <td><input value={l.commentaire ?? ''} disabled={fige} onChange={(e) => ligne(i, { commentaire: e.target.value })} /></td>
                    <td>{!fige && <button type="button" className="lien" onClick={() => maj({ lignes: f.lignes.filter((_, j) => j !== i) })}>retirer</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {['entree', 'plat', 'dessert', 'supplement'].map((t) => (
              <datalist key={t} id={`catalogue-${t}`}>{suggestions(t).map((p) => <option key={p.id} value={p.nom} />)}</datalist>
            ))}
            {!fige && (
              <div className="ligne-champs">
                {typesPermis.map((t) => (
                  <button type="button" key={t.cle} onClick={() => maj({ lignes: [...f.lignes, { type: t.cle, libelle: '', quantite: t.cle === 'supplement' ? Number(f.couverts) : 1, commentaire: '' }] })}>
                    + {t.libelle}
                  </button>
                ))}
              </div>
            )}
            <div className="totaux">
              {(['entree', 'plat', 'dessert'] as const).map((t) => (
                <span key={t} className={`pastille ${totaux[t] > f.couverts ? 'rouge' : totaux[t] ? 'vert' : 'gris'}`}>
                  {t === 'entree' ? 'Entrées' : t === 'plat' ? 'Plats' : 'Desserts'} : {totaux[t]}/{f.couverts}
                </span>
              ))}
            </div>
          </section>

          <section className="carte">
            <h2>Allergènes</h2>
            <div className="puces">
              {references?.allergenes.map((a) => {
                const actif = f.allergenes.includes(a.cle)
                return (
                  <button type="button" key={a.cle} disabled={fige} className={`puce${actif ? ' active' : ''}`}
                    onClick={() => maj({ allergenes: actif ? f.allergenes.filter((x) => x !== a.cle) : [...f.allergenes, a.cle] })}>
                    {a.libelle}
                  </button>
                )
              })}
            </div>
          </section>

          <section className="carte">
            <h2>Notes</h2>
            <p className="aide">Mise en forme : **gras**, _italique_, lignes commençant par « - » pour une liste.</p>
            <fieldset disabled={fige} className="ligne-champs">
              <Champ libelle="Notes salle (occasion, demandes, déroulé)" large>
                <textarea rows={5} value={f.notes_salle} onChange={(e) => maj({ notes_salle: e.target.value })} />
              </Champ>
              <Champ libelle="Notes cuisine (allergies détaillées, régimes, timing)" large>
                <textarea rows={5} value={f.notes_cuisine} onChange={(e) => maj({ notes_cuisine: e.target.value })} />
              </Champ>
            </fieldset>
          </section>
        </div>

        {fiche && (
          <aside>
            <section className="carte">
              <h2>Statut</h2>
              <div className="pile">
                {(TRANSITIONS[fiche.statut] ?? []).map((t) => (
                  <button type="button" key={t.cible} className={t.principal ? 'principal' : ''} disabled={enCours || modifie}
                    onClick={() => changerStatut(t.cible)}>{t.libelle}</button>
                ))}
                {fiche.statut !== 'annulee' && fiche.statut !== 'realisee' && (
                  <button type="button" className="danger" disabled={enCours || modifie} onClick={() => changerStatut('annulee')}>Annuler la fiche</button>
                )}
                {modifie && <p className="aide">Enregistrer d'abord les modifications.</p>}
              </div>
            </section>
            <section className="carte">
              <h2>Devis</h2>
              {fiche.devis ? (
                <div className="pile">
                  <Link to={`/devis/${fiche.devis.id}`}>{fiche.devis.numero} v{fiche.devis.version}</Link>
                  <span>Statut : {fiche.devis.statut}</span>
                  {fiche.devis.a_mettre_a_jour && <span className="texte-alerte">La fiche a changé depuis le devis.</span>}
                </div>
              ) : moi.peut.devis && fiche.statut !== 'annulee' ? (
                <button type="button" className="principal" disabled={enCours || modifie} onClick={preparerDevis}>Préparer le devis</button>
              ) : <p className="muet">Aucun devis.</p>}
              {fiche.bon && <p>Bon : <Link to={`/bons/${fiche.bon.id}`}>{fiche.bon.numero}</Link> ({fiche.bon.statut})</p>}
            </section>
            <section className="carte">
              <h2>Autres actions</h2>
              <button type="button" onClick={dupliquer} disabled={enCours}>Dupliquer la fiche</button>
            </section>
            <section className="carte">
              <h2>Historique</h2>
              <ul className="historique">
                {historique.map((h, i) => (
                  <li key={i}>
                    <span className="muet">{formatInstant(h.le)}</span> {h.utilisateur}
                    {h.canal === 'chatgpt' && <span className="pastille violet">ChatGPT</span>}
                    <div>{h.resume || h.action}</div>
                  </li>
                ))}
              </ul>
            </section>
          </aside>
        )}
      </div>
    </form>
  )
}
