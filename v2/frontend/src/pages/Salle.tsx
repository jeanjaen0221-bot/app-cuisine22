import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, aujourdhui, Echec, formatJour, messageErreur, ouvrirPdf } from '../api'
import FloorCanvas from '../composants/FloorCanvas'
import { Alertes, Erreur, Pastille, useAction } from '../composants/ui'
import type { AssignmentMap, FloorPlanData, FloorTable } from '../typesSalle'

type Plan = { id: string; donnees: FloorPlanData; etiquettes: Record<string, string> }
type Resa = {
  id: string; source: 'fiche' | 'import'; fiche_id: string | null; nom: string; pax: number; heure: string
  statut: string | null; doublon_de: string | null; tables: string[]; pax_place: number; place: boolean
}
type Service = {
  id: string; date: string; service: 'midi' | 'soir'; service_libelle: string; donnees: FloorPlanData
  affectations: AssignmentMap; etiquettes: Record<string, string>; reservations: Resa[]; alertes: string[]
  orphelines: { table: string; nom: string; pax: number }[]
  totaux: { reservations: number; couverts: number; placees: number; doublons: number; importees: number }
}

const TABLES: { kind: FloorTable['kind']; libelle: string; capacite: number; couleur: string }[] = [
  { kind: 'fixed', libelle: 'Fixe', capacite: 4, couleur: '#22aa77' },
  { kind: 'rect', libelle: 'Rectangle', capacite: 6, couleur: '#3399ff' },
  { kind: 'round', libelle: 'Ronde', capacite: 10, couleur: '#ff9933' },
  { kind: 'sofa', libelle: 'Canapé', capacite: 5, couleur: '#9c27b0' },
  { kind: 'standing', libelle: 'Debout', capacite: 8, couleur: '#ff5722' },
]
const ZONES = [
  { label: 'Salle', color: '#3b82f6' }, { label: 'Terrasse', color: '#22c55e' }, { label: 'Mezzanine', color: '#f59e0b' },
  { label: 'Bar', color: '#f97316' }, { label: 'Salon', color: '#8b5cf6' },
]
type ModeDessin = null | 'interdite' | 'rondes' | 'rectangles' | { label: string; color: string }

const nouvelId = () => (crypto.randomUUID ? crypto.randomUUID() : `id-${Date.now()}-${Math.random().toString(36).slice(2)}`)

export default function Salle() {
  const [onglet, setOnglet] = useState<'service' | 'plan'>('service')
  const [jour, setJour] = useState(aujourdhui())
  const [moment, setMoment] = useState<'midi' | 'soir'>(new Date().getHours() < 16 ? 'midi' : 'soir')
  const [plan, setPlan] = useState<Plan | null>(null)
  const [service, setService] = useState<Service | null>(null)
  const [donnees, setDonnees] = useState<FloorPlanData | null>(null) // plan en cours d'édition (base ou service)
  const [modifie, setModifie] = useState(false)
  const [selection, setSelection] = useState<string[]>([])
  const [dessin, setDessin] = useState<ModeDessin>(null)
  const [grille, setGrille] = useState(true)
  const [recentrer, setRecentrer] = useState(0)
  const [renum, setRenum] = useState({ prefixe: '', debut: 1 })
  const [annote, setAnnote] = useState({ page_debut: 0, debut_y_mm: 95, hauteur_ligne_mm: 13.5, colonne_x_mm: 137 })
  const fichierImport = useRef<HTMLInputElement>(null)
  const fichierAnnote = useRef<HTMLInputElement>(null)
  const { enCours, erreur, setErreur, lancer } = useAction()

  const ouvrirService = async () => {
    const s = await lancer(() => api.post<Service>('/api/salle/services', { date: jour, service: moment }))
    if (s) { setService(s); setDonnees(s.donnees); setModifie(false); setSelection([]) }
  }
  const chargerPlan = async () => {
    const p = await lancer(() => api.get<Plan>('/api/salle/plan'))
    if (p) { setPlan(p); setDonnees(p.donnees); setModifie(false); setSelection([]) }
  }

  useEffect(() => {
    setDessin(null)
    if (onglet === 'plan') chargerPlan()
    else ouvrirService()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onglet, jour, moment])

  const appliquerService = (s: Service | undefined) => { if (s) { setService(s); setDonnees(s.donnees); setModifie(false) } }

  const changer = (d: FloorPlanData) => { setDonnees(d); setModifie(true) }
  const enregistrer = async () => {
    if (!donnees) return
    if (onglet === 'plan') {
      const p = await lancer(() => api.put<Plan>('/api/salle/plan', { donnees }))
      if (p) { setPlan(p); setDonnees(p.donnees); setModifie(false) }
    } else if (service) {
      appliquerService(await lancer(() => api.put<Service>(`/api/salle/services/${service.id}`, { donnees })))
    }
  }
  const actionService = async (action: string, corps: object = {}) => {
    if (!service) return
    if (modifie && !window.confirm('Des modifications du plan ne sont pas enregistrées. Continuer sans elles ?')) return
    appliquerService(await lancer(() => api.post<Service>(`/api/salle/services/${service.id}/${action}`, corps)))
  }
  const numeroter = async (seulementSelection: boolean) => {
    const corps = seulementSelection ? { table_ids: selection, prefixe: renum.prefixe, debut: renum.debut } : {}
    if (onglet === 'plan') {
      if (modifie) await enregistrer()
      const p = await lancer(() => api.post<Plan>('/api/salle/plan/numeroter', corps))
      if (p) { setPlan(p); setDonnees(p.donnees) }
    } else await actionService('numeroter', corps)
  }

  const envoyerFichier = async (chemin: string, fichier: File, champs: Record<string, string | number> = {}) => {
    const formulaire = new FormData()
    formulaire.append('fichier', fichier)
    for (const [cle, valeur] of Object.entries(champs)) formulaire.append(cle, String(valeur))
    const reponse = await fetch(chemin, { method: 'POST', body: formulaire, credentials: 'same-origin', headers: { 'X-Albert': '1' } })
    if (!reponse.ok) {
      const corps = await reponse.json().catch(() => null)
      throw new Echec(reponse.status, corps?.erreur ?? { code: 'erreur', message: 'Envoi impossible.' })
    }
    return reponse
  }
  const importer = async (fichier?: File) => {
    if (!fichier || !service) return
    const r = await lancer(async () => (await envoyerFichier(`/api/salle/services/${service.id}/import-pdf`, fichier)).json() as Promise<Service>)
    appliquerService(r)
  }
  const pdfAnnote = async (fichier?: File) => {
    if (!fichier || !service) return
    try {
      const r = await envoyerFichier(`/api/salle/services/${service.id}/pdf-annote`, fichier, annote)
      const lien = URL.createObjectURL(await r.blob())
      window.open(lien, '_blank', 'noopener')
    } catch (e) { setErreur(messageErreur(e)) }
  }

  const ajouterTable = (kind: FloorTable['kind'], capacite: number) => {
    if (!donnees) return
    const base = { id: nouvelId(), kind, capacity: capacite, x: 100, y: 100 }
    const forme = kind === 'round' ? { r: 50 } : kind === 'standing' ? { r: 40 } : kind === 'sofa' ? { w: 180, h: 80 } : { w: 120, h: 60 }
    changer({ ...donnees, tables: [...(donnees.tables || []), { ...base, ...forme }] })
  }
  const ajouterElement = (forme: 'mur' | 'colonne') => {
    if (!donnees) return
    const element = forme === 'colonne' ? { id: nouvelId(), x: 200, y: 200, r: 30 } : { id: nouvelId(), x: 200, y: 200, w: 60, h: 20 }
    changer({ ...donnees, fixtures: [...((donnees.fixtures as unknown[]) || []), element] as FloorPlanData['fixtures'] })
  }

  // Placement à la main : la table cliquée, puis la réservation.
  const tableChoisie = selection.length === 1 ? selection[0] : null
  const affectationChoisie = tableChoisie ? service?.affectations.tables[tableChoisie] : undefined
  const [resaChoisie, setResaChoisie] = useState('')
  useEffect(() => { setResaChoisie(affectationChoisie?.res_id ?? '') }, [tableChoisie, affectationChoisie?.res_id])
  const etiquettes = onglet === 'plan' ? plan?.etiquettes : service?.etiquettes
  const aPlacer = useMemo(() => (service?.reservations ?? []).filter((r) => !r.doublon_de), [service])

  const affectationsAffichees = onglet === 'service' ? service?.affectations : undefined
  const modeDessin = {
    drawNoGoMode: dessin === 'interdite', drawRoundOnlyMode: dessin === 'rondes', drawRectOnlyMode: dessin === 'rectangles',
    drawZoneMode: typeof dessin === 'object' && dessin ? dessin : undefined,
  }

  const outilsPlan = donnees && (
    <>
      <h3>Ajouter</h3>
      <div className="grille-boutons">
        {TABLES.map((t) => (
          <button key={t.kind} onClick={() => ajouterTable(t.kind, t.capacite)}>
            <span className="point" style={{ background: t.couleur }} /> {t.libelle} ({t.capacite})
          </button>
        ))}
        <button onClick={() => ajouterElement('mur')}>Mur / meuble</button>
        <button onClick={() => ajouterElement('colonne')}>Colonne</button>
      </div>
      <h3>Zones</h3>
      <p className="aide">Les zones guident le placement automatique : grandes tables en zone T, rondes en zone R.</p>
      <div className="pile">
        <button className={dessin === 'rectangles' ? 'principal' : ''} onClick={() => setDessin(dessin === 'rectangles' ? null : 'rectangles')}>Zone T (rectangles)</button>
        <button className={dessin === 'rondes' ? 'principal' : ''} onClick={() => setDessin(dessin === 'rondes' ? null : 'rondes')}>Zone R (rondes)</button>
        <button className={dessin === 'interdite' ? 'danger' : ''} onClick={() => setDessin(dessin === 'interdite' ? null : 'interdite')}>Zone interdite</button>
      </div>
      <div className="grille-boutons">
        {ZONES.map((z) => (
          <button key={z.label} style={{ borderColor: z.color, color: z.color }}
            onClick={() => setDessin(typeof dessin === 'object' && dessin?.label === z.label ? null : z)}>{z.label}</button>
        ))}
      </div>
      {dessin && <p className="aide">Dessiner la zone sur le plan en glissant. <button className="lien" onClick={() => setDessin(null)}>Terminer</button></p>}
      <h3>Numérotation</h3>
      <button onClick={() => numeroter(false)} disabled={enCours}>Numéroter toutes les tables</button>
      {selection.length > 0 && (
        <div className="ligne-champs">
          <input placeholder="Préfixe" value={renum.prefixe} onChange={(e) => setRenum({ ...renum, prefixe: e.target.value })} style={{ width: 80 }} />
          <input type="number" value={renum.debut} onChange={(e) => setRenum({ ...renum, debut: Number(e.target.value) || 1 })} style={{ width: 70 }} />
          <button onClick={() => numeroter(true)} disabled={enCours}>Renuméroter {selection.length} table(s)</button>
        </div>
      )}
      <p className="aide">Clic droit sur un élément : le supprimer. Double-clic : verrouiller.</p>
    </>
  )

  return (
    <div className="salle">
      <header className="en-tete">
        <div>
          <h1>Salle</h1>
          <div className="onglets">
            <button className={onglet === 'service' ? 'actif' : ''} onClick={() => setOnglet('service')}>Plan d'un service</button>
            <button className={onglet === 'plan' ? 'actif' : ''} onClick={() => setOnglet('plan')}>Plan de base</button>
          </div>
        </div>
        <div className="actions">
          {onglet === 'service' && <>
            <input type="date" value={jour} onChange={(e) => setJour(e.target.value)} />
            <select value={moment} onChange={(e) => setMoment(e.target.value as 'midi' | 'soir')}>
              <option value="midi">Midi</option><option value="soir">Soir</option>
            </select>
          </>}
          <label className="case"><input type="checkbox" checked={grille} onChange={(e) => setGrille(e.target.checked)} /> Grille</label>
          <button onClick={() => setRecentrer((n) => n + 1)}>Recentrer</button>
          {modifie && <button className="principal" onClick={enregistrer} disabled={enCours}>Enregistrer le plan</button>}
        </div>
      </header>
      <Erreur message={erreur} />

      <div className="salle-corps">
        <aside className="salle-panneau">
          {onglet === 'service' && service && (
            <>
              <section>
                <h2>{service.service_libelle} — {formatJour(service.date)}</h2>
                <div className="chiffres">
                  <div><strong>{service.totaux.reservations}</strong><span>réservations</span></div>
                  <div><strong>{service.totaux.couverts}</strong><span>couverts</span></div>
                  <div><strong>{service.totaux.placees}</strong><span>placées</span></div>
                </div>
                <Alertes liste={service.alertes} />
                <div className="pile">
                  <button className="principal" onClick={() => actionService('placement-auto')} disabled={enCours}>Placement automatique</button>
                  <button onClick={() => fichierImport.current?.click()} disabled={enCours}>
                    {service.totaux.importees ? `Remplacer le PDF importé (${service.totaux.importees})` : 'Importer le PDF de réservations'}
                  </button>
                  <input ref={fichierImport} type="file" accept="application/pdf" hidden onChange={(e) => { importer(e.target.files?.[0]); e.target.value = '' }} />
                  {service.totaux.importees > 0 && <button onClick={() => actionService('retirer-import')} disabled={enCours}>Retirer les réservations importées</button>}
                  <button onClick={() => ouvrirPdf(`/api/salle/services/${service.id}/pdf`)}>PDF du service (liste + plan)</button>
                </div>
              </section>

              {tableChoisie && (
                <section className="encadre">
                  <h3>Table {service.etiquettes[tableChoisie] || '(sans numéro)'}</h3>
                  <select value={resaChoisie} onChange={(e) => setResaChoisie(e.target.value)}>
                    <option value="">— libre —</option>
                    {aPlacer.map((r) => <option key={r.id} value={r.id}>{r.heure} {r.nom} ({r.pax} p.){r.place ? ' ✓' : ''}</option>)}
                  </select>
                  <div className="ligne-champs">
                    <button className="principal" disabled={enCours || resaChoisie === (affectationChoisie?.res_id ?? '')}
                      onClick={() => actionService('affecter', { table_id: tableChoisie, reservation_id: resaChoisie || null })}>
                      {resaChoisie ? 'Attribuer' : 'Libérer la table'}
                    </button>
                  </div>
                </section>
              )}
              {!tableChoisie && <p className="aide">Cliquer une table pour l'attribuer à la main.</p>}

              <section>
                <h3>Réservations</h3>
                <ul className="resas">
                  {service.reservations.map((r) => (
                    <li key={r.id} className={r.doublon_de ? 'inactif' : r.place ? '' : 'texte-alerte'}>
                      <span className="heure">{r.heure}</span>
                      <span className="nom">
                        {r.fiche_id ? <Link to={`/fiches/${r.fiche_id}`}>{r.nom}</Link> : r.nom}
                        {r.source === 'import' && !r.doublon_de && <Pastille couleur="gris">PDF</Pastille>}
                        {r.doublon_de && <span className="aide"> déjà une fiche</span>}
                      </span>
                      <span>{r.pax} p.</span>
                      <span className="tables">{r.tables.join(', ') || (r.doublon_de ? '' : '—')}</span>
                    </li>
                  ))}
                  {service.reservations.length === 0 && <li className="muet">Aucune fiche dans la salle pour ce service. Importer le PDF de réservations, ou créer des fiches.</li>}
                </ul>
              </section>

              <details>
                <summary>Modifier le plan de ce service</summary>
                {outilsPlan}
                <div className="pile">
                  <button onClick={() => actionService('reinitialiser')} disabled={enCours}>Retirer les tables ajoutées et le placement</button>
                  <button onClick={() => window.confirm('Repartir du plan de base ? Le placement de ce service sera effacé.') && actionService('reinitialiser', { depuis_le_plan: true })} disabled={enCours}>Repartir du plan de base</button>
                </div>
              </details>

              <details>
                <summary>PDF de réservations annoté</summary>
                <p className="aide">Écrit les numéros de table dans la colonne du PDF importé, puis ajoute la liste et le plan.</p>
                <div className="ligne-champs">
                  <label className="champ">Page de départ<input type="number" value={annote.page_debut} onChange={(e) => setAnnote({ ...annote, page_debut: Number(e.target.value) })} /></label>
                  <label className="champ">Première ligne (mm du haut)<input type="number" step="0.5" value={annote.debut_y_mm} onChange={(e) => setAnnote({ ...annote, debut_y_mm: Number(e.target.value) })} /></label>
                  <label className="champ">Hauteur de ligne (mm)<input type="number" step="0.5" value={annote.hauteur_ligne_mm} onChange={(e) => setAnnote({ ...annote, hauteur_ligne_mm: Number(e.target.value) })} /></label>
                  <label className="champ">Colonne (mm de la gauche)<input type="number" step="0.5" value={annote.colonne_x_mm} onChange={(e) => setAnnote({ ...annote, colonne_x_mm: Number(e.target.value) })} /></label>
                </div>
                <button onClick={() => fichierAnnote.current?.click()}>Choisir le PDF et l'annoter</button>
                <input ref={fichierAnnote} type="file" accept="application/pdf" hidden onChange={(e) => { pdfAnnote(e.target.files?.[0]); e.target.value = '' }} />
              </details>
              <details>
                <summary>Supprimer le plan de ce service</summary>
                <button className="danger" onClick={() => window.confirm('Supprimer le plan de ce service ?') && lancer(() => api.post(`/api/salle/services/${service.id}/supprimer`)).then((r) => r && ouvrirService())}>Supprimer</button>
              </details>
            </>
          )}

          {onglet === 'plan' && donnees && (
            <>
              <section>
                <p className="aide">Le plan de base sert de départ à chaque nouveau service. Les services déjà ouverts gardent leur plan.</p>
                {outilsPlan}
                <h3>Réglages du placement</h3>
                <div className="reglages">
                  <label>Chaises des tables fixes<input type="number" min={0} value={donnees.fixed_chair_stock ?? 28} onChange={(e) => changer({ ...donnees, fixed_chair_stock: Number(e.target.value) })} /></label>
                  <label>Tables rectangulaires en réserve<input type="number" min={0} value={donnees.max_dynamic_tables?.rect ?? 10} onChange={(e) => changer({ ...donnees, max_dynamic_tables: { ...donnees.max_dynamic_tables, rect: Number(e.target.value) } })} /></label>
                  <label>Tables rondes en réserve<input type="number" min={0} value={donnees.max_dynamic_tables?.round ?? 5} onChange={(e) => changer({ ...donnees, max_dynamic_tables: { ...donnees.max_dynamic_tables, round: Number(e.target.value) } })} /></label>
                  <label>Groupe à droite au-delà de (couverts)<input type="number" min={1} value={donnees.large_table_config?.pax_threshold_right ?? 10} onChange={(e) => changer({ ...donnees, large_table_config: { ...donnees.large_table_config, pax_threshold_right: Number(e.target.value) } })} /></label>
                  <label>Table verticale au-delà de (couverts)<input type="number" min={1} value={donnees.large_table_config?.pax_threshold_vertical ?? 20} onChange={(e) => changer({ ...donnees, large_table_config: { ...donnees.large_table_config, pax_threshold_vertical: Number(e.target.value) } })} /></label>
                  <label>Largeur de salle<input type="number" min={100} value={donnees.room?.width ?? 1600} onChange={(e) => changer({ ...donnees, room: { ...(donnees.room ?? { height: 1000 }), width: Number(e.target.value) } })} /></label>
                  <label>Profondeur de salle<input type="number" min={100} value={donnees.room?.height ?? 1000} onChange={(e) => changer({ ...donnees, room: { ...(donnees.room ?? { width: 1600 }), height: Number(e.target.value) } })} /></label>
                </div>
                <button onClick={() => ouvrirPdf('/api/salle/plan/pdf')}>PDF du plan</button>
              </section>
            </>
          )}
        </aside>

        <div className="salle-canevas">
          {donnees && (
            <FloorCanvas
              data={donnees}
              assignments={affectationsAffichees}
              editable
              showGrid={grille}
              onChange={changer}
              resetTrigger={recentrer}
              onSelectionChange={setSelection}
              {...modeDessin}
            />
          )}
          {etiquettes && selection.length > 0 && (
            <div className="selection-info">{selection.length} table(s) choisie(s) : {selection.map((id) => etiquettes[id] || '?').join(', ')}</div>
          )}
        </div>
      </div>
    </div>
  )
}
