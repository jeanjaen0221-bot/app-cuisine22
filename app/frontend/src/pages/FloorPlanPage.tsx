import { useEffect, useMemo, useState } from 'react'
import { api, autoAssignInstance, createFloorInstance, getFloorBase, getFloorInstance, importReservationsPdf, updateFloorBase, updateFloorInstance, numberBaseTables, exportBasePdf, numberInstanceTables, exportInstancePdf, exportInstanceAnnotatedPdf, setSalleDebug } from '../lib/api'
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
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [debugSalle, setDebugSalle] = useState(false)
  const [logLines, setLogLines] = useState<Array<{ id: number; ts: string; lvl: string; msg: string }>>([])
  const [lastLogId, setLastLogId] = useState<number>(0)
  const [showLogs, setShowLogs] = useState(false)

  useEffect(() => { loadBase() }, [])

  useEffect(() => {
    setSalleDebug(debugSalle)
  }, [debugSalle])

  useEffect(() => {
    if (!debugSalle) return
    
    let timer: any
    let active = true
    
    async function poll() {
      if (!active) return
      try {
        const r = await api.get('/api/floorplan/debug-log', { params: { after: lastLogId || undefined, limit: 200 } })
        const lines = (r.data?.lines || []) as Array<{ id: number; ts: string; lvl: string; msg: string }>
        if (lines.length) {
          setLogLines(prev => {
            const next = [...prev, ...lines]
            return next.slice(-1000)
          })
          const last = (r.data?.last || lastLogId) as number
          setLastLogId(last)
        }
      } catch {}
      if (active) {
        timer = setTimeout(poll, 2000)
      }
    }
    
    poll()
    
    return () => {
      active = false
      if (timer) clearTimeout(timer)
    }
  }, [debugSalle, lastLogId])

  async function loadBase() {
    setBusy(true)
    try { setBase(await getFloorBase()) } finally { setBusy(false) }
  }

  async function doNumberBase() {
    setBusy(true)
    try { setBase(await numberBaseTables()) } finally { setBusy(false) }
  }

  function doExportBase() {
    exportBasePdf()
  }

  async function doNumberInstance() {
    if (!inst) return
    setBusy(true)
    try { setInst(await numberInstanceTables(inst.id as any)) } finally { setBusy(false) }
  }

  function doExportInstance() {
    if (!inst) return
    exportInstancePdf(inst.id as any)
  }

  async function doExportInstanceAnnotated() {
    if (!inst || !pdfFile) return
    setBusy(true)
    try {
      await exportInstanceAnnotatedPdf(inst.id as any, pdfFile)
    } finally { setBusy(false) }
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
    if (!inst) {
      alert('Veuillez d\'abord importer un PDF de réservations')
      return
    }
    setBusy(true)
    try {
      const after = await autoAssignInstance(inst.id)
      setInst(after)
      // enchaîner la numérotation après auto-assign
      const numbered = await numberInstanceTables(after.id as any)
      setInst(numbered)
    } finally { setBusy(false) }
  }

  async function doImport(e: React.ChangeEvent<HTMLInputElement>, createRes: boolean) {
    const f = e.target.files?.[0]
    if (!f) return
    setBusy(true)
    try {
      // Créer l'instance si elle n'existe pas
      let currentInst = inst
      if (!currentInst) {
        const row = await createFloorInstance({ service_date: date, service_label: label })
        const full = await getFloorInstance(row.id)
        setInst(full)
        setMode('service')
        currentInst = full
      }
      // Stocker le fichier pour l'export annoté
      setPdfFile(f)
      await importReservationsPdf(f, date, label, createRes)
      // Rafraîchir l'instance après import
      if (currentInst) {
        const refreshed = await getFloorInstance(currentInst.id)
        setInst(refreshed)
      }
    } finally { setBusy(false) }
  }

  function addTable(kind: 'fixed' | 'rect' | 'round') {
    const next: FloorPlanData = { ...(mode === 'base' ? base?.data : inst?.data) } as any
    if (!next.tables) next.tables = []
    const id = `t_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
    if (kind === 'round') next.tables.push({ id, kind: 'round', x: 200, y: 200, r: 50, capacity: 10 })
    else if (kind === 'rect') next.tables.push({ id, kind: 'rect', x: 200, y: 200, w: 120, h: 60, capacity: 6 })
    else next.tables.push({ id, kind: 'fixed', x: 200, y: 200, w: 120, h: 60, capacity: 4, locked: true })
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
          <button className={`btn ${debugSalle ? 'active' : ''}`} onClick={() => { setDebugSalle(v => { const nv = !v; if (nv) setShowLogs(true); return nv }) }}>
            Debug Salle: {debugSalle ? 'ON' : 'OFF'}
          </button>
          <button className="btn" onClick={() => setShowLogs(v => !v)}>Afficher les logs</button>
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
              <>
                <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                  <button onClick={doNumberBase}>Numéroter (1..20 / T1..T20)</button>
                  <button onClick={doExportBase}>Exporter PDF</button>
                </div>
                <FloorCanvas data={base.data} showGrid={grid} editable onChange={saveBaseData} drawNoGoMode={drawNoGo} />
              </>
            )}
          </div>
        </div>
      )}

      {mode === 'service' && (
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 16, height: 'calc(100vh - 140px)' }}>
          <div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{padding:'8px',background:'#f5f5f5',borderRadius:4,marginBottom:8}}>
                <strong>1. Choisir date et service</strong>
                <label style={{display:'block',marginTop:4}}>Date <input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
                <label style={{display:'block',marginTop:4}}>Service
                  <select value={label || ''} onChange={(e) => setLabel((e.target.value || 'lunch') as ServiceLabel)}>
                    <option value="lunch">Midi</option>
                    <option value="dinner">Soir</option>
                  </select>
                </label>
              </div>
              <div style={{padding:'8px',background:'#f5f5f5',borderRadius:4,marginBottom:8}}>
                <strong>2. Importer PDF réservations</strong>
                <label style={{display:'block',marginTop:4}}>
                  <input type="file" accept="application/pdf" onChange={(e)=>doImport(e, true)} />
                </label>
                {pdfFile && <div style={{fontSize:12,color:'#0a0',fontWeight:'bold',marginTop:4}}>✓ {pdfFile.name}</div>}
              </div>
              <div style={{padding:'8px',background:'#f5f5f5',borderRadius:4,marginBottom:8}}>
                <strong>3. Auto-attribuer les tables</strong>
                <button style={{marginTop:4,width:'100%'}} disabled={!inst} onClick={doAutoAssign}>Auto-attribuer</button>
              </div>
              <hr />
              <button onClick={() => addFixture('rect')} disabled={!inst}>Ajouter objet carré</button>
              <button onClick={() => addFixture('round')} disabled={!inst}>Ajouter objet rond</button>
              <button onClick={addNoGo} disabled={!inst}>Ajouter zone interdite</button>
            </div>
          </div>
          <div>
            {inst && (
              <>
                <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                  <button onClick={doExportInstance}>Exporter PDF</button>
                  <button onClick={doExportInstanceAnnotated} disabled={!pdfFile}>Exporter PDF annoté</button>
                </div>
                <FloorCanvas data={inst.data} assignments={inst.assignments} showGrid={grid} editable onChange={saveInstanceData} drawNoGoMode={drawNoGo} />
              </>
            )}
          </div>
        </div>
      )}
      {debugSalle && (
        <div style={{ position:'fixed', right:12, bottom:12, background:'#222', color:'#0f0', padding:'6px 10px', borderRadius:6, opacity:0.9, zIndex:9999 }}>
          Debug Salle ON
        </div>
      )}
      {showLogs && (
        <div style={{ position:'fixed', right:12, top:72, width:480, height:380, background:'#0b0b0b', color:'#eee', padding:10, border:'1px solid #333', borderRadius:8, overflow:'hidden', zIndex:9998, display:'flex', flexDirection:'column', gap:6 }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <strong>Logs Salle (tail)</strong>
            <div style={{ display:'flex', gap:8 }}>
              <button onClick={() => {
                const text = logLines.map(l => `[${l.ts}] ${l.lvl} ${l.msg}`).join('\n')
                navigator.clipboard.writeText(text).then(() => {
                  alert('Logs copiés dans le presse-papiers !')
                }).catch(() => {
                  alert('Erreur lors de la copie')
                })
              }}>Copier</button>
              <button onClick={() => setLogLines([])}>Vider</button>
              <button onClick={() => setShowLogs(false)}>Fermer</button>
            </div>
          </div>
          <div style={{ flex:'1 1 auto', overflow:'auto', border:'1px solid #222', padding:6, background:'#0f0f0f' }}>
            <pre style={{ whiteSpace:'pre-wrap', margin:0, fontSize:12, lineHeight:'16px' }}>
              {logLines.map(l => `[${l.ts}] ${l.lvl} ${l.msg}`).join('\n')}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}

// Inline styles for debug widgets can remain here for simplicity
