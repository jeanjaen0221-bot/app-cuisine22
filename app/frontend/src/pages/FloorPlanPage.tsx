import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api'
import type {
  FloorPlanTemplate as Tpl,
  FloorPlanLayout,
  FloorPlanFixedTable,
  ParsedReservation,
  FloorPlanInstance,
  FloorPlanAssignment,
  AssignmentTable,
} from '../types'
import FloorPlanEditor from '../components/FloorPlanEditor'

function numberInput(v: any, d = 0) {
  const n = parseInt(v as string, 10)
  return isFinite(n) ? n : d
}

function CanvasPreview({ layout, width, height }: { layout: FloorPlanLayout; width: number; height: number }) {
  const ref = useRef<HTMLCanvasElement | null>(null)
  useEffect(() => {
    const c = ref.current
    if (!c) return
    const ctx = c.getContext('2d')!
    ctx.clearRect(0, 0, c.width, c.height)

    // background
    ctx.fillStyle = '#f8fafc'
    ctx.fillRect(0, 0, c.width, c.height)

    // Zones
    if (layout.zones) {
      for (const z of layout.zones) {
        if (!z.points || z.points.length < 3) continue
        ctx.beginPath()
        ctx.moveTo(z.points[0].x, z.points[0].y)
        for (let i = 1; i < z.points.length; i++) ctx.lineTo(z.points[i].x, z.points[i].y)
        ctx.closePath()
        if (z.kind === 'forbidden') ctx.fillStyle = 'rgba(239,68,68,0.15)'
        else if (z.kind === 'reservable') ctx.fillStyle = 'rgba(16,185,129,0.12)'
        else ctx.fillStyle = 'rgba(59,130,246,0.10)'
        ctx.fill()
        ctx.strokeStyle = 'rgba(100,116,139,0.6)'
        ctx.stroke()
      }
    }

    // Obstacles
    if (layout.obstacles) {
      ctx.fillStyle = '#cbd5e1'
      for (const o of layout.obstacles) {
        if (o.type === 'rect' && o.x != null && o.y != null && o.width && o.height) {
          ctx.fillRect(o.x, o.y, o.width, o.height)
        } else if (o.type === 'circle' && o.x != null && o.y != null && o.radius) {
          ctx.beginPath()
          ctx.arc(o.x, o.y, o.radius, 0, Math.PI * 2)
          ctx.fill()
        } else if (o.type === 'poly' && o.points && o.points.length >= 3) {
          ctx.beginPath()
          ctx.moveTo(o.points[0].x, o.points[0].y)
          for (let i = 1; i < o.points.length; i++) ctx.lineTo(o.points[i].x, o.points[i].y)
          ctx.closePath()
          ctx.fill()
        }
      }
    }

    // Fixed tables
    ctx.fillStyle = '#6d28d9'
    for (const t of layout.fixedTables || []) {
      const w = 40
      const h = 24
      ctx.save()
      ctx.translate(t.x, t.y)
      if (t.rotation) ctx.rotate((t.rotation * Math.PI) / 180)
      ctx.fillRect(-w / 2, -h / 2, w, h)
      ctx.fillStyle = 'white'
      ctx.font = '12px sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText((t.label || t.id) + `(${t.seats})`, 0, 0)
      ctx.restore()
      ctx.fillStyle = '#6d28d9'
    }
  }, [layout, width, height])
  return <canvas ref={ref} width={width} height={height} className="border rounded bg-white" />
}

export default function FloorPlanPage() {
  const [templates, setTemplates] = useState<Tpl[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected = useMemo(() => templates.find(t => t.id === selectedId) || null, [templates, selectedId])

  const [editing, setEditing] = useState<Tpl | null>(null)
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [parsed, setParsed] = useState<ParsedReservation[]>([])
  const [serviceDate, setServiceDate] = useState<string>('')
  const [serviceLabel, setServiceLabel] = useState<string>('service')
  const [instance, setInstance] = useState<FloorPlanInstance | null>(null)
  const [instances, setInstances] = useState<FloorPlanInstance[]>([])
  const [scale, setScale] = useState<number>(1)

  useEffect(() => {
    fetchTemplates()
  }, [])

  useEffect(() => {
    if (selected) setEditing(selected)
  }, [selectedId])

  async function fetchTemplates() {
    const r = await api.get<Tpl[]>('/api/floorplan/templates')
    setTemplates(r.data)
    if (!selectedId && r.data.length) setSelectedId(r.data[0].id)
  }

  function ensureEditing() {
    if (!editing) setEditing({
      id: '' as any,
      name: 'Modèle',
      width: 1000,
      height: 800,
      layout: { fixedTables: [], movableTables6Count: 22, round10ReserveCount: 11 },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
  }

  function updateFixedTable(idx: number, patch: Partial<FloorPlanFixedTable>) {
    if (!editing) return
    const next = { ...editing, layout: { ...(editing.layout || { fixedTables: [] }), fixedTables: [...(editing.layout?.fixedTables || [])] } }
    next.layout.fixedTables[idx] = { ...next.layout.fixedTables[idx], ...patch }
    setEditing(next)
  }

  function addFixedTable() {
    ensureEditing()
    setEditing(prev => {
      if (!prev) return prev
      const next = { ...prev, layout: { ...(prev.layout || {}), fixedTables: [...(prev.layout?.fixedTables || [])] } }
      next.layout.fixedTables.push({ id: `F-${(next.layout.fixedTables.length + 1)}`, x: 100, y: 100, seats: 2, rotation: 0, label: '' })
      return next
    })
  }

  function removeFixedTable(i: number) {
    if (!editing) return
    const next = { ...editing, layout: { ...(editing.layout || { fixedTables: [] }), fixedTables: [...(editing.layout?.fixedTables || [])] } }
    next.layout.fixedTables.splice(i, 1)
    setEditing(next)
  }

  async function saveTemplate() {
    if (!editing) return
    const payload = {
      name: editing.name,
      width: editing.width,
      height: editing.height,
      layout: editing.layout as FloorPlanLayout,
    }
    if (!editing.id) {
      const r = await api.post<Tpl>('/api/floorplan/templates', payload)
      await fetchTemplates()
      setSelectedId(r.data.id)
    } else {
      const r = await api.put<Tpl>(`/api/floorplan/templates/${editing.id}`, payload)
      setEditing(r.data)
      await fetchTemplates()
    }
  }

  async function handleParsePdf() {
    if (!pdfFile) return
    const form = new FormData()
    form.append('f', pdfFile)
    const r = await api.post<ParsedReservation[]>(`/api/floorplan/parse-pdf`, form, { params: { default_date: serviceDate || undefined }, headers: { 'Content-Type': 'multipart/form-data' } })
    setParsed(r.data)
  }

  async function generateInstance() {
    if (!editing?.id) return
    const body = {
      template_id: editing.id,
      service_date: serviceDate,
      service_label: serviceLabel || 'service',
      reservations: parsed,
    }
    const r = await api.post<FloorPlanInstance>('/api/floorplan/generate', body)
    setInstance(r.data)
  }

  async function saveInstanceChanges() {
    if (!instance) return
    const body = { assignments: instance.assignments, layout_overrides: instance.layout_overrides || {} }
    const r = await api.put<FloorPlanInstance>(`/api/floorplan/instances/${instance.id}`, body)
    setInstance(r.data)
  }

  async function refreshInstances() {
    const r = await api.get<FloorPlanInstance[]>('/api/floorplan/instances', { params: { service_date: serviceDate || undefined, service_label: serviceLabel || undefined } })
    setInstances(r.data)
  }

  function addTableToAssignment(key: string, table: AssignmentTable) {
    if (!instance) return
    const next = { ...instance, assignments: { ...instance.assignments } }
    const a = { ...(next.assignments[key] || { name: key, pax: 0, tables: [] as AssignmentTable[] }) }
    a.tables = [...(a.tables || []), table]
    next.assignments[key] = a
    setInstance(next)
  }

  function removeTableFromAssignment(key: string, idx: number) {
    if (!instance) return
    const next = { ...instance, assignments: { ...instance.assignments } }
    const a = { ...(next.assignments[key]) }
    a.tables = [...(a.tables || [])]
    a.tables.splice(idx, 1)
    next.assignments[key] = a
    setInstance(next)
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Plan de salle</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-3">
          <div className="card p-3 space-y-2">
            <div className="flex items-center gap-2">
              <select className="input" value={selectedId || ''} onChange={e => setSelectedId(e.target.value || null)}>
                {templates.map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
              <button className="btn" onClick={() => setEditing({ id: '' as any, name: 'Nouveau modèle', width: 1000, height: 800, layout: { fixedTables: [], movableTables6Count: 22, round10ReserveCount: 11 }, created_at: '', updated_at: '' })}>Nouveau</button>
            </div>
            {editing && (
              <div className="space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <label className="text-sm">Nom<input className="input" value={editing.name} onChange={e => setEditing({ ...editing, name: e.target.value })} /></label>
                  <label className="text-sm">Largeur<input className="input" type="number" value={editing.width} onChange={e => setEditing({ ...editing, width: numberInput(e.target.value, 1000) })} /></label>
                  <label className="text-sm">Hauteur<input className="input" type="number" value={editing.height} onChange={e => setEditing({ ...editing, height: numberInput(e.target.value, 800) })} /></label>
                  <label className="text-sm">Tables 6 dispo<input className="input" type="number" value={editing.layout?.movableTables6Count || 0} onChange={e => setEditing({ ...editing, layout: { ...(editing.layout || { fixedTables: [] }), movableTables6Count: numberInput(e.target.value, 22) } as any })} /></label>
                  <label className="text-sm">Tables rondes 10 réserve<input className="input" type="number" value={editing.layout?.round10ReserveCount || 0} onChange={e => setEditing({ ...editing, layout: { ...(editing.layout || { fixedTables: [] }), round10ReserveCount: numberInput(e.target.value, 11) } as any })} /></label>
                </div>

                <div className="flex items-center justify-between">
                  <h3 className="font-medium">Tables fixes</h3>
                  <button className="btn" onClick={addFixedTable}>Ajouter une table fixe</button>
                </div>
                <div className="space-y-2 max-h-64 overflow-auto pr-1">
                  {(editing.layout?.fixedTables || []).map((t, i) => (
                    <div key={i} className="grid grid-cols-6 gap-2 items-end">
                      <label className="text-sm">ID<input className="input" value={t.id} onChange={e => updateFixedTable(i, { id: e.target.value })} /></label>
                      <label className="text-sm">Sièges<input className="input" type="number" value={t.seats} onChange={e => updateFixedTable(i, { seats: numberInput(e.target.value, t.seats) })} /></label>
                      <label className="text-sm">X<input className="input" type="number" value={t.x} onChange={e => updateFixedTable(i, { x: numberInput(e.target.value, t.x) })} /></label>
                      <label className="text-sm">Y<input className="input" type="number" value={t.y} onChange={e => updateFixedTable(i, { y: numberInput(e.target.value, t.y) })} /></label>
                      <label className="text-sm">Rotation<input className="input" type="number" value={t.rotation || 0} onChange={e => updateFixedTable(i, { rotation: numberInput(e.target.value, 0) })} /></label>
                      <div className="flex gap-2">
                        <button className="btn" onClick={() => removeFixedTable(i)}>Supprimer</button>
                      </div>
                    </div>
                  ))}
                </div>

                <div>
                  <button className="btn btn-primary" onClick={saveTemplate}>Enregistrer le modèle</button>
                </div>
              </div>
            )}
          </div>

          {editing && (
            <div className="card p-3 space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">Éditeur visuel</h3>
                <div className="flex items-center gap-2">
                  <label className="text-sm">Zoom</label>
                  <input className="input" type="range" min={0.25} max={2} step={0.05} value={scale} onChange={e => setScale(parseFloat(e.target.value))} style={{ width: 160 }} />
                  <button className="btn" onClick={() => setScale(1)}>100%</button>
                  <button className="btn" onClick={() => setScale(s => Math.max(0.25, s - 0.1))}>-</button>
                  <button className="btn" onClick={() => setScale(s => Math.min(2, s + 0.1))}>+</button>
                </div>
              </div>
              <FloorPlanEditor
                layout={(editing.layout as FloorPlanLayout) || { fixedTables: [] }}
                width={editing.width || 1000}
                height={editing.height || 800}
                scale={scale}
                onLayoutChange={(next) => setEditing(prev => prev ? { ...prev, layout: next } : prev)}
              />
            </div>
          )}
        </div>

        <div className="space-y-3">
          <div className="card p-3 space-y-2">
            <h3 className="font-medium">Génération à partir d'un PDF</h3>
            <div className="grid grid-cols-2 gap-2">
              <label className="text-sm">Date de service<input className="input" type="date" value={serviceDate} onChange={e => setServiceDate(e.target.value)} /></label>
              <label className="text-sm">Libellé service<input className="input" value={serviceLabel} onChange={e => setServiceLabel(e.target.value)} /></label>
              <label className="text-sm col-span-2">PDF de réservations<input className="input" type="file" accept="application/pdf" onChange={e => setPdfFile(e.target.files?.[0] || null)} /></label>
            </div>
            <div className="flex gap-2">
              <button className="btn" onClick={handleParsePdf} disabled={!pdfFile}>Analyser PDF</button>
              <button className="btn btn-primary" onClick={generateInstance} disabled={!parsed.length || !editing?.id || !serviceDate}>Générer</button>
            </div>

            {!!parsed.length && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium">Réservations détectées ({parsed.length})</h4>
                <div className="max-h-52 overflow-auto border rounded">
                  <table className="min-w-full text-sm">
                    <thead><tr className="bg-slate-50"><th className="px-2 py-1 text-left">Nom</th><th className="px-2 py-1">Couverts</th><th className="px-2 py-1">Heure</th></tr></thead>
                    <tbody>
                      {parsed.map((r, i) => (
                        <tr key={i} className="border-t">
                          <td className="px-2 py-1"><input className="input" value={r.name} onChange={e => setParsed(prev => prev.map((x, j) => j===i?{...x, name:e.target.value}:x))} /></td>
                          <td className="px-2 py-1 w-24"><input className="input" type="number" value={r.pax} onChange={e => setParsed(prev => prev.map((x, j) => j===i?{...x, pax:numberInput(e.target.value, r.pax)}:x))} /></td>
                          <td className="px-2 py-1 w-32"><input className="input" value={r.arrival_time || ''} onChange={e => setParsed(prev => prev.map((x, j) => j===i?{...x, arrival_time:e.target.value}:x))} placeholder="HH:MM" /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {instance && (
            <div className="card p-3 space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">Plan généré – {instance.service_date} ({instance.service_label})</h3>
                <button className="btn btn-primary" onClick={saveInstanceChanges}>Sauvegarder</button>
              </div>
              <div className="max-h-64 overflow-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50">
                      <th className="px-2 py-1 text-left">Groupe</th>
                      <th className="px-2 py-1">Pax</th>
                      <th className="px-2 py-1 text-left">Tables</th>
                      <th className="px-2 py-1">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(instance.assignments || {}).map(([k, a]) => (
                      <tr key={k} className="border-t align-top">
                        <td className="px-2 py-1">{(a as FloorPlanAssignment).name || k}</td>
                        <td className="px-2 py-1 text-center">{(a as FloorPlanAssignment).pax}</td>
                        <td className="px-2 py-1">
                          <div className="flex flex-wrap gap-1">
                            {(a as FloorPlanAssignment).tables?.map((t, i) => (
                              <span key={i} className="px-2 py-1 rounded bg-slate-100 border">{t.type}:{t.id}{t.seats?`(${t.seats})`:''} <button className="ml-1 text-red-600" onClick={() => removeTableFromAssignment(k, i)}>×</button></span>
                            ))}
                          </div>
                        </td>
                        <td className="px-2 py-1">
                          <div className="flex gap-2">
                            <button className="btn" onClick={() => addTableToAssignment(k, { type: 't6', id: `T6-extra`, seats: 6 })}>+ T6</button>
                            <button className="btn" onClick={() => addTableToAssignment(k, { type: 't6', id: `T8-extra`, seats: 8, head: true })}>+ T8</button>
                            <button className="btn" onClick={() => addTableToAssignment(k, { type: 'r10', id: `R10-extra`, seats: 10 })}>+ R10</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="card p-3 space-y-2">
            <div className="flex items-center gap-2">
              <h3 className="font-medium">Plans sauvegardés</h3>
              <button className="btn" onClick={refreshInstances}>Rafraîchir</button>
            </div>
            <div className="max-h-56 overflow-auto">
              <table className="min-w-full text-sm">
                <thead><tr className="bg-slate-50"><th className="px-2 py-1 text-left">Date</th><th className="px-2 py-1 text-left">Service</th><th className="px-2 py-1 text-left">Template</th><th className="px-2 py-1 text-left">ID</th></tr></thead>
                <tbody>
                  {instances.map((i) => (
                    <tr key={i.id} className="border-t">
                      <td className="px-2 py-1">{i.service_date}</td>
                      <td className="px-2 py-1">{i.service_label}</td>
                      <td className="px-2 py-1">{i.template_id}</td>
                      <td className="px-2 py-1">{i.id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
