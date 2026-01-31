import { useEffect, useMemo, useState } from 'react'
import { api, autoAssignInstance, createFloorInstance, getFloorBase, getFloorInstance, importReservationsPdf, updateFloorBase, updateFloorInstance } from '../lib/api'
import type { AssignmentMap, FloorPlanBase, FloorPlanData, FloorPlanInstance, ServiceLabel } from '../types'
import FloorCanvas from '../components/FloorCanvas'

export default function FloorPlanPage() {
  const [mode, setMode] = useState<'base' | 'service'>('base')
  const [base, setBase] = useState<FloorPlanBase | null>(null)
  const [inst, setInst] = useState<FloorPlanInstance | null>(null)
  const [date, setDate] = useState<string>(() => new Date().toISOString().slice(0, 10))
  const [label, setLabel] = useState<ServiceLabel>('lunch')
  const [grid, setGrid] = useState(true)
  const [busy, setBusy] = useState(false)
  const [drawNoGo, setDrawNoGo] = useState(false)

  useEffect(() => { loadBase() }, [])

  async function loadBase() {
    setBusy(true)
    try { setBase(await getFloorBase()) } finally { setBusy(false) }
  }

  async function saveBaseData(next: FloorPlanData) {
    if (!base) return
    const updated = await updateFloorBase({ data: next })
    setBase(updated)
  }

  async function saveInstanceData(next: FloorPlanData) {
    if (!inst) return
    const updated = await updateFloorInstance(inst.id, { data: next })
    setInst(updated)
  }

  async function ensureInstance() {
    setBusy(true)
    try {
      const row = await createFloorInstance({ service_date: date, service_label: label })
      const full = await getFloorInstance(row.id)
      setInst(full)
      setMode('service')
    } finally { setBusy(false) }
  }

  async function doAutoAssign() {
    if (!inst) return
    setBusy(true)
    try { setInst(await autoAssignInstance(inst.id)) } finally { setBusy(false) }
  }

  async function doImport(e: React.ChangeEvent<HTMLInputElement>, createRes: boolean) {
    const f = e.target.files?.[0]
    if (!f) return
    setBusy(true)
    try {
      await importReservationsPdf(f, date, label, createRes)
      if (inst) {
        const full = await getFloorInstance(inst.id)
        setInst(full)
      }
    } finally { setBusy(false) }
  }

  function addTable(kind: 'fixed' | 'rect' | 'round') {
    const next: FloorPlanData = { ...(mode === 'base' ? base?.data : inst?.data) } as any
    if (!next.tables) next.tables = []
    const id = `t_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
    if (kind === 'round') next.tables.push({ id, kind: 'round', x: 200, y: 200, r: 50, capacity: 10, label: 'Ronde' })
    else if (kind === 'rect') next.tables.push({ id, kind: 'rect', x: 200, y: 200, w: 120, h: 60, capacity: 6, label: 'Rect' })
    else next.tables.push({ id, kind: 'fixed', x: 200, y: 200, w: 120, h: 60, capacity: 4, locked: true, label: 'Fixe' })
    if (mode === 'base' && base) saveBaseData(next)
    if (mode === 'service' && inst) saveInstanceData(next)
  }

  function addFixture(shape: 'rect' | 'round') {
    const next: FloorPlanData = { ...(mode === 'base' ? base?.data : inst?.data) } as any
    if (!next.fixtures) next.fixtures = [] as any
    const id = `fx_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
    const name = window.prompt('Nom de l\'objet', shape === 'rect' ? 'Objet' : 'Colonne') || ''
    if (shape === 'round') (next.fixtures as any).push({ id, shape: 'round', x: 300, y: 220, r: 40, label: name })
    else (next.fixtures as any).push({ id, shape: 'rect', x: 300, y: 220, w: 120, h: 60, label: name })
    if (mode === 'base' && base) saveBaseData(next)
    if (mode === 'service' && inst) saveInstanceData(next)
  }

  function addNoGo() {
    const next: FloorPlanData = { ...(mode === 'base' ? base?.data : inst?.data) } as any
    if (!next.no_go) next.no_go = [] as any
    const id = `ng_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
    const w = 200, h = 120
    const x = 150, y = 150
    ;(next.no_go as any).push({ id, x, y, w, h })
    if (mode === 'base' && base) saveBaseData(next)
    if (mode === 'service' && inst) saveInstanceData(next)
  }

  return (
    <div className="page">
      <div className="toolbar" style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
        <div>
          <button className={`btn ${mode==='base'?'active':''}`} onClick={() => setMode('base')}>Plan de base</button>
          <button className={`btn ${mode==='service'?'active':''}`} onClick={() => setMode('service')}>Plan du service</button>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
            <input type="checkbox" checked={grid} onChange={(e) => setGrid(e.target.checked)} /> Grille
          </label>
          <button className={`btn ${drawNoGo?'active':''}`} onClick={() => setDrawNoGo(v => !v)}>
            {drawNoGo ? 'Arrêter: Zone interdite' : 'Dessiner zone interdite'}
          </button>
          {busy && <span>Chargement…</span>}
        </div>
      </div>

      {mode === 'base' && (
        <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 16, height: 'calc(100vh - 140px)' }}>
          <div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button onClick={() => addTable('fixed')}>Ajouter table fixe</button>
              <button onClick={() => addTable('rect')}>Ajouter table rectangulaire</button>
              <button onClick={() => addTable('round')}>Ajouter table ronde</button>
              <hr />
              <button onClick={() => addFixture('rect')}>Ajouter objet carré</button>
              <button onClick={() => addFixture('round')}>Ajouter objet rond</button>
              <button onClick={addNoGo}>Ajouter zone interdite</button>
            </div>
            <div style={{ marginTop: 16 }}>
              <div>Date par défaut: {new Date().toLocaleDateString()}</div>
            </div>
          </div>
          <div style={{ minHeight: 400 }}>
            {base && (
              <FloorCanvas data={base.data} showGrid={grid} editable onChange={saveBaseData} drawNoGoMode={drawNoGo} />
            )}
          </div>
        </div>
      )}

      {mode === 'service' && (
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 16, height: 'calc(100vh - 140px)' }}>
          <div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label>Date <input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
              <label>Service
                <select value={label || ''} onChange={(e) => setLabel((e.target.value || 'lunch') as ServiceLabel)}>
                  <option value="lunch">Midi</option>
                  <option value="dinner">Soir</option>
                </select>
              </label>
              <button onClick={ensureInstance}>Créer/Charger</button>
              <button disabled={!inst} onClick={doAutoAssign}>Auto-attribuer</button>
              <label>Importer PDF
                <input type="file" accept="application/pdf" onChange={(e)=>doImport(e, false)} />
              </label>
              <label>Importer & créer
                <input type="file" accept="application/pdf" onChange={(e)=>doImport(e, true)} />
              </label>
              <hr />
              <button onClick={() => addFixture('rect')} disabled={!inst}>Ajouter objet carré</button>
              <button onClick={() => addFixture('round')} disabled={!inst}>Ajouter objet rond</button>
              <button onClick={addNoGo} disabled={!inst}>Ajouter zone interdite</button>
            </div>
          </div>
          <div>
            {inst && (
              <FloorCanvas data={inst.data} assignments={inst.assignments} showGrid={grid} editable onChange={saveInstanceData} drawNoGoMode={drawNoGo} />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
