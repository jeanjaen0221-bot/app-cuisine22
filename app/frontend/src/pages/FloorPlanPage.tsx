import React, { useEffect, useState } from 'react'
import { api, fileDownload, getFloorBase, updateFloorBase } from '../lib/api'
import FloorCanvas from '../components/FloorCanvas'
import type { FloorPlanData, FloorPlanBase, FloorPlanInstance } from '../types'
import { Plus, Save, Trash2, Download, Upload, Calendar, Layers } from 'lucide-react'

type Toast = { id: string; type: 'success' | 'error' | 'warning' | 'info'; message: string }
type TemplateTab = 'elements' | 'config'
type InstanceTab = 'reservations' | 'plan'

const ZONE_PRESETS = [
  { label: 'Salle', color: '#3b82f6' },
  { label: 'Terrasse', color: '#22c55e' },
  { label: 'Mezzanine', color: '#f59e0b' },
  { label: 'Bar', color: '#f97316' },
  { label: 'Salon', color: '#8b5cf6' },
]

export default function FloorPlanPage() {
  const [baseTemplate, setBaseTemplate] = useState<FloorPlanBase | null>(null)
  const [instances, setInstances] = useState<FloorPlanInstance[]>([])
  const [selectedInstance, setSelectedInstance] = useState<FloorPlanInstance | null>(null)
  const [editMode, setEditMode] = useState<'template' | 'instance'>('template')
  const [showGrid, setShowGrid] = useState(true)
  const [drawNoGoMode, setDrawNoGoMode] = useState(false)
  const [drawRoundOnlyMode, setDrawRoundOnlyMode] = useState(false)
  const [drawRectOnlyMode, setDrawRectOnlyMode] = useState(false)
  const [drawZoneMode, setDrawZoneMode] = useState<{ label: string; color: string } | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newInstanceDate, setNewInstanceDate] = useState('')
  const [newInstanceLabel, setNewInstanceLabel] = useState('lunch')
  const [uploadingPDF, setUploadingPDF] = useState(false)
  const [viewByInstance, setViewByInstance] = useState<Record<string, { scale: number; offset: { x: number; y: number } }>>({})
  const [compareResult, setCompareResult] = useState<any | null>(null)
  const [showCompareModal, setShowCompareModal] = useState(false)
  const [uiAlerts, setUiAlerts] = useState<string[]>([])
  const [resetViewTick, setResetViewTick] = useState(0)
  const [selectedTableIds, setSelectedTableIds] = useState<string[]>([])
  const [renumberPrefix, setRenumberPrefix] = useState('')
  const [renumberStart, setRenumberStart] = useState(1)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [newZoneLabel, setNewZoneLabel] = useState('')
  const [newZoneColor, setNewZoneColor] = useState('#22c55e')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [templateTab, setTemplateTab] = useState<TemplateTab>('elements')
  const [instanceTab, setInstanceTab] = useState<InstanceTab>('reservations')

  useEffect(() => {
    loadBase()
    loadInstances()
  }, [])

  useEffect(() => {
    try {
      const raw = localStorage.getItem('floorViewByInstance')
      if (raw) setViewByInstance(JSON.parse(raw))
    } catch {}
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem('floorViewByInstance', JSON.stringify(viewByInstance))
    } catch {}
  }, [viewByInstance])

  async function loadBase() {
    try {
      const data = await getFloorBase()
      setBaseTemplate(data)
    } catch (err) {
      console.error('Failed to load base template:', err)
    }
  }

  async function resetInstanceAction() {
    if (!selectedInstance) return
    try {
      const res = await api.post(`/api/floorplan/instances/${selectedInstance.id}/reset`)
      setSelectedInstance(res.data)
      toast('success', 'Instance rÃ©initialisÃ©e')
    } catch (err) {
      console.error('Failed to reset instance:', err)
      toast('error', 'Erreur rÃ©initialisation')
    }
  }

  async function compareWithPDF() {
    if (!selectedInstance) { toast('warning', "SÃ©lectionnez d'abord une instance"); return }
    try {
      const res = await api.get(`/api/floorplan/instances/${selectedInstance.id}/compare`)
      setCompareResult(res.data)
      setShowCompareModal(true)
    } catch (err) {
      console.error('Failed to compare instance:', err)
      toast('error', 'Erreur comparaison')
    }
  }

  async function loadInstances() {
    try {
      const res = await api.get('/api/floorplan/instances')
      setInstances(res.data)
    } catch (err) {
      console.error('Failed to load instances:', err)
    }
  }

  async function saveBase() {
    if (!baseTemplate) return
    try {
      await updateFloorBase({ name: baseTemplate.name, data: baseTemplate.data })
      toast('success', 'Plan de base sauvegardÃ©')
      await loadBase()
    } catch (err) {
      console.error('Failed to save base:', err)
      toast('error', 'Erreur lors de la sauvegarde')
    }
  }

  async function saveInstance() {
    if (!selectedInstance) return
    try {
      await api.put(`/api/floorplan/instances/${selectedInstance.id}`, { data: selectedInstance.data, assignments: selectedInstance.assignments })
      toast('success', 'Instance sauvegardÃ©e')
      await loadInstances()
    } catch (err) {
      console.error('Failed to save instance:', err)
      toast('error', 'Erreur lors de la sauvegarde')
    }
  }

  async function createInstance() {
    if (!newInstanceDate) { toast('warning', 'Veuillez sÃ©lectionner une date'); return }
    try {
      await api.post('/api/floorplan/instances', { service_date: newInstanceDate, service_label: newInstanceLabel })
      toast('success', 'Service crÃ©Ã©')
      setShowCreateModal(false)
      setNewInstanceDate('')
      await loadInstances()
    } catch (err: any) {
      console.error('Failed to create instance:', err)
      toast('error', 'Erreur: ' + (err.response?.data?.detail || 'CrÃ©ation Ã©chouÃ©e'))
    }
  }

  async function deleteInstance() {
    if (!selectedInstance) return
    try {
      await api.delete(`/api/floorplan/instances/${selectedInstance.id}`)
      setSelectedInstance(null)
      setConfirmDelete(false)
      toast('success', 'Service supprimÃ©')
      await loadInstances()
    } catch (err) {
      console.error('Failed to delete instance:', err)
      toast('error', 'Erreur lors de la suppression')
    }
  }

  async function importPDF() {
    if (!selectedInstance) { toast('warning', "SÃ©lectionnez d'abord une instance"); return }
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.pdf'
    input.onchange = async (e: any) => {
      const file = e.target?.files?.[0]
      if (!file) return
      setUploadingPDF(true)
      try {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('service_date', selectedInstance.service_date)
        formData.append('service_label', selectedInstance.service_label || 'lunch')
        const res = await api.post('/api/floorplan/import-pdf', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        const count = Array.isArray(res.data.parsed) ? res.data.parsed.length : 0
        console.log('[IMPORT-PDF] RÃ©sultat:', res.data)
        toast('success', `${count} rÃ©servation(s) importÃ©e(s)`)
        await loadInstances()
        // Reload selected instance
        const updated = await api.get(`/api/floorplan/instances/${selectedInstance.id}`)
        setSelectedInstance(updated.data)
      } catch (err: any) {
        console.error('Failed to import PDF:', err)
        toast('error', 'Erreur import: ' + (err.response?.data?.detail || 'Ã‰chec'))
      } finally {
        setUploadingPDF(false)
      }
    }
    input.click()
  }

  async function exportBase() {
    try {
      const res = await api.get('/api/floorplan/base/export-pdf', {
        responseType: 'blob'
      })
      fileDownload(res.data, 'plan_de_base.pdf')
    } catch (err) {
      console.error('Failed to export base pdf:', err)
      toast('error', 'Erreur export PDF')
    }
  }

  async function autoAssign() {
    if (!selectedInstance) { toast('warning', "SÃ©lectionnez d'abord une instance"); return }
    try {
      // Capturer AVANT l'appel API (Ã©vite bug de rÃ©fÃ©rence)
      const tablesBefore = selectedInstance?.data?.tables?.length || 0
      const res = await api.post(`/api/floorplan/instances/${selectedInstance.id}/auto-assign`)
      const assigned = Object.keys(res.data.assignments?.tables || {}).length
      const tablesAfter = res.data?.data?.tables?.length || 0
      const newTablesCreated = tablesAfter - tablesBefore
      const alerts: string[] = Array.isArray(res.data?.assignments?.alerts) ? res.data.assignments.alerts : []
      
      console.log('[AUTO-ASSIGN] RÃ©sultat:', {
        assigned,
        tablesBefore,
        tablesAfter,
        newTablesCreated,
        instanceData: res.data
      })
      
      if (alerts.length > 0) setUiAlerts(alerts)
      toast('success', `${assigned} tables assignÃ©es${newTablesCreated > 0 ? ` (+${newTablesCreated} nouvelles)` : ''}${alerts.length > 0 ? ` Â· ${alerts.length} alerte(s)` : ''}`)
      setSelectedInstance(res.data)
    } catch (err: any) {
      console.error('Failed to auto-assign:', err)
      toast('error', 'Erreur: ' + (err.response?.data?.detail || 'Placement automatique Ã©chouÃ©'))
    }
  }

  async function numberTables() {
    const target = editMode === 'template' ? baseTemplate : selectedInstance
    if (!target) return
    const endpoint = editMode === 'template' 
      ? '/api/floorplan/base/number-tables'
      : `/api/floorplan/instances/${selectedInstance!.id}/number-tables`
    try {
      const res = await api.post(endpoint)
      if (editMode === 'template') {
        setBaseTemplate(res.data)
      } else {
        setSelectedInstance(res.data)
      }
      toast('success', 'Tables numÃ©rotÃ©es')
    } catch (err) {
      console.error('Failed to number tables:', err)
      toast('error', 'Erreur numÃ©rotation')
    }
  }

  async function renumberSelectedTables() {
    const ids = selectedTableIds
    if (!ids.length) { toast('warning', "SÃ©lectionnez d'abord des tables"); return }
    try {
      const payload = { table_ids: ids, prefix: renumberPrefix, start: renumberStart }
      const res = editMode === 'template'
        ? await api.post('/api/floorplan/base/renumber-tables', payload)
        : await api.post(`/api/floorplan/instances/${selectedInstance!.id}/renumber-tables`, payload)
      if (editMode === 'template') {
        setBaseTemplate(res.data)
      } else {
        setSelectedInstance(res.data)
      }
      toast('success', 'NumÃ©rotation appliquÃ©e')
    } catch (err: any) {
      console.error('Failed to renumber tables:', err)
      toast('error', 'Erreur renumÃ©rotation: ' + (err.response?.data?.detail || 'Ã‰chec'))
    }
  }

  async function exportAnnotated() {
    if (!selectedInstance) { toast('warning', "SÃ©lectionnez d'abord une instance"); return }
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.pdf'
    input.onchange = async (e: any) => {
      const file = e.target?.files?.[0]
      if (!file) return
      try {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('start_y_mm', '95.0')
        formData.append('row_h_mm', '13.5')
        formData.append('table_x_mm', '137.0')
        const res = await api.post(
          `/api/floorplan/instances/${selectedInstance.id}/export-annotated`,
          formData,
          { responseType: 'blob', headers: { 'Content-Type': 'multipart/form-data' } }
        )
        fileDownload(res.data, `annotated_${selectedInstance.service_date}.pdf`)
      } catch (err) {
        console.error('Failed to export annotated:', err)
        toast('error', 'Erreur export annotÃ©')
      }
    }
    input.click()
  }

  async function exportComplete() {
    if (!selectedInstance) return
    try {
      const res = await api.get(`/api/floorplan/instances/${selectedInstance.id}/export-pdf`, {
        responseType: 'blob'
      })
      fileDownload(res.data, `plan_${selectedInstance.service_date}.pdf`)
    } catch (err) {
      console.error('Failed to export complete:', err)
      toast('error', 'Erreur export PDF')
    }
  }

  function addTable(kind: 'fixed' | 'rect' | 'round' | 'sofa' | 'standing', capacity: number) {
    if (!currentData) return
    const newId = crypto.randomUUID()
    let newTable: any
    if (kind === 'round') {
      newTable = { id: newId, kind, capacity, x: 100, y: 100, r: 50 }
    } else if (kind === 'sofa') {
      newTable = { id: newId, kind, capacity, x: 100, y: 100, w: 180, h: 80 }
    } else if (kind === 'standing') {
      newTable = { id: newId, kind, capacity, x: 100, y: 100, r: 40 }
    } else {
      newTable = { id: newId, kind, capacity, x: 100, y: 100, w: 120, h: 60 }
    }
    const updated = { ...currentData, tables: [...currentData.tables, newTable] }
    if (editMode === 'template') {
      setBaseTemplate(prev => prev ? { ...prev, data: updated } : prev)
    } else {
      setSelectedInstance(prev => prev ? { ...prev, data: updated } : prev)
    }
  }

  function addFixture(shape: 'rect' | 'round') {
    const target = editMode === 'template' ? baseTemplate : selectedInstance
    if (!target) return
    const fixtures = (target.data.fixtures || []) as any[]
    const id = `fx_${Date.now()}_${Math.random().toString(36).slice(2,7)}`
    let newFixture: any = { id, x: 200, y: 200 }
    if (shape === 'round') {
      newFixture.r = 30
    } else {
      newFixture.w = 60
      newFixture.h = 20
    }
    const updated = { ...target.data, fixtures: [...fixtures, newFixture] }
    if (editMode === 'template') {
      setBaseTemplate({ ...baseTemplate!, data: updated })
    } else {
      setSelectedInstance({ ...selectedInstance!, data: updated })
    }
  }

  function handleBaseChange(data: FloorPlanData) {
    if (baseTemplate) {
      setBaseTemplate({ ...baseTemplate, data })
    }
  }

  function handleInstanceChange(data: FloorPlanData) {
    if (selectedInstance) {
      setSelectedInstance({ ...selectedInstance, data })
    }
  }

  function toast(type: Toast['type'], message: string) {
    const id = Math.random().toString(36).slice(2)
    setToasts(prev => [...prev.slice(-2), { id, type, message }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000)
  }

  function clearDrawModes() {
    setDrawNoGoMode(false)
    setDrawRoundOnlyMode(false)
    setDrawRectOnlyMode(false)
    setDrawZoneMode(null)
  }

  const labelService = (label: string) => label === 'lunch' ? 'Midi' : label === 'dinner' ? 'Soir' : label === 'brunch' ? 'Brunch' : label

  const currentData = editMode === 'template' ? baseTemplate?.data : selectedInstance?.data
  const currentView = editMode === 'instance' && selectedInstance ? viewByInstance[selectedInstance.id] : undefined
  const instanceHasReservations = !!(selectedInstance?.reservations && Array.isArray((selectedInstance as any).reservations?.items) && (selectedInstance as any).reservations.items.length > 0)
  const instanceAssignmentsCount = Object.keys(selectedInstance?.assignments?.tables || {}).length
  const instanceReservationsCount = (selectedInstance?.reservations && Array.isArray((selectedInstance as any).reservations?.items)) ? (selectedInstance as any).reservations.items.length : 0
  const instanceDynamicTables = (selectedInstance?.data?.tables || []).filter((t: any) => t && (t as any).dynamic).length

  return (
    <div className="fp-layout">

      {/* Barre superieure */}
      <div className="fp-topbar">
        <div className="fp-topbar-left">
          <button className="fp-sidebar-toggle" onClick={() => setSidebarOpen(v => !v)} title="Sidebar">&#9776;</button>
          <div className="join">
            <button className={`btn btn-sm join-item ${editMode === 'template' ? 'btn-primary' : 'btn-outline'}`} onClick={() => { setEditMode('template'); clearDrawModes() }}>Plan de base</button>
            <button className={`btn btn-sm join-item ${editMode === 'instance' ? 'btn-primary' : 'btn-outline'}`} onClick={() => { setEditMode('instance'); clearDrawModes() }}><Calendar className="w-4 h-4" /> Services</button>
          </div>
        </div>
        <div className="fp-topbar-center">
          {editMode === 'template' ? (
            <span className="fp-plan-name">{baseTemplate?.name || 'Plan de base'}</span>
          ) : (
            <div className="flex items-center gap-2">
              <select className="input input-sm" style={{ minWidth: 200 }} value={selectedInstance?.id || ''} onChange={(e) => { const inst = instances.find(i => i.id === e.target.value); setSelectedInstance(inst || null); clearDrawModes() }}>
                <option value="">— Selectionner un service —</option>
                {instances.map(i => (<option key={i.id} value={i.id}>{i.service_date} · {labelService(i.service_label || 'lunch')}</option>))}
              </select>
              <button className="btn btn-sm btn-outline" onClick={() => setShowCreateModal(true)} title="Creer"><Plus className="w-4 h-4" /></button>
            </div>
          )}
        </div>
        <div className="fp-topbar-right">
          {editMode === 'instance' && selectedInstance && (
            <>
              <span className="fp-stat-badge">{instanceReservationsCount} res.</span>
              <span className="fp-stat-badge">{instanceAssignmentsCount} tables</span>
              <span className="fp-stat-badge">{instanceDynamicTables} dyn.</span>
            </>
          )}
          <button className="btn btn-sm btn-success" onClick={editMode === 'template' ? saveBase : saveInstance} disabled={!currentData}><Save className="w-4 h-4" /> Sauvegarder</button>
          <button className="btn btn-sm btn-outline" onClick={() => setResetViewTick(t => t + 1)} title="Recentrer">&#8632;</button>
        </div>
      </div>

      {/* Corps */}
      <div className="fp-body">

        {/* Sidebar */}
        {sidebarOpen && (
          <aside className="fp-sidebar">
            {editMode === 'template' && (
              <div className="fp-tabs">
                <button className={`fp-tab-btn${templateTab === 'elements' ? ' active' : ''}`} onClick={() => setTemplateTab('elements')}>Elements &amp; Zones</button>
                <button className={`fp-tab-btn${templateTab === 'config' ? ' active' : ''}`} onClick={() => setTemplateTab('config')}>Config</button>
              </div>
            )}
            {editMode === 'instance' && (
              <div className="fp-tabs">
                <button className={`fp-tab-btn${instanceTab === 'reservations' ? ' active' : ''}`} onClick={() => setInstanceTab('reservations')}>Reservations</button>
                <button className={`fp-tab-btn${instanceTab === 'plan' ? ' active' : ''}`} onClick={() => setInstanceTab('plan')}>Plan</button>
              </div>
            )}
            <div className="fp-sidebar-scroll">

              {/* TEMPLATE — Elements & Zones */}
              {editMode === 'template' && templateTab === 'elements' && (
                <div className="fp-tab-content">
                  <p className="fp-group-label">Tables</p>
                  <div className="fp-btn-grid">
                    <button onClick={() => addTable('fixed', 4)} className="btn btn-sm fp-add-btn"><span className="fp-table-dot" style={{ background: '#2ca' }}></span> Fixe (4)</button>
                    <button onClick={() => addTable('rect', 6)} className="btn btn-sm fp-add-btn"><span className="fp-table-dot" style={{ background: '#39f' }}></span> Rect (6-8)</button>
                    <button onClick={() => addTable('round', 10)} className="btn btn-sm fp-add-btn"><span className="fp-table-dot" style={{ background: '#f93' }}></span> Ronde (10)</button>
                    <button onClick={() => addTable('sofa', 5)} className="btn btn-sm fp-add-btn"><span className="fp-table-dot" style={{ background: '#9c27b0' }}></span> Canape (5)</button>
                    <button onClick={() => addTable('standing', 8)} className="btn btn-sm fp-add-btn"><span className="fp-table-dot" style={{ background: '#ff5722' }}></span> Debout (8)</button>
                  </div>
                  <p className="fp-group-label mt-2">Objets</p>
                  <div className="fp-btn-grid">
                    <button className="btn btn-sm btn-outline" onClick={() => addFixture('rect')}>Mur</button>
                    <button className="btn btn-sm btn-outline" onClick={() => addFixture('round')}>Colonne</button>
                  </div>
                  <div className="fp-divider" />
                  <p className="fp-group-label">Zones nommees</p>
                  {(currentData?.zones || []).length === 0 && <p className="fp-hint">Aucune zone. Creez-en une ci-dessous.</p>}
                  <div className="space-y-1 mb-2">
                    {(currentData?.zones || []).map(z => (
                      <div key={z.id} className="fp-zone-row">
                        <span className="fp-zone-chip" style={{ background: z.color + '22', borderColor: z.color, color: z.color }}>{z.label}</span>
                        <button className={`btn btn-xs ${drawZoneMode?.label === z.label ? 'btn-primary' : 'btn-outline'}`} onClick={() => { if (drawZoneMode?.label === z.label) clearDrawModes(); else { clearDrawModes(); setDrawZoneMode({ label: z.label, color: z.color || '#3b82f6' }) } }}>{drawZoneMode?.label === z.label ? 'Stop' : 'Dessiner'}</button>
                        <button className="btn btn-xs btn-ghost text-red-400" onClick={() => { if (!currentData) return; handleBaseChange({ ...currentData, zones: (currentData.zones || []).filter(zz => zz.id !== z.id) }) }}>Suppr.</button>
                      </div>
                    ))}
                  </div>
                  <div className="fp-zone-presets">
                    {ZONE_PRESETS.map(p => (<button key={p.label} className="fp-zone-preset-btn" style={{ borderColor: p.color, color: p.color }} onClick={() => { clearDrawModes(); setDrawZoneMode({ label: p.label, color: p.color }) }}>{p.label}</button>))}
                  </div>
                  <div className="flex gap-2 items-center mt-2">
                    <input className="input input-sm flex-1" placeholder="Nom (ex: VIP)" value={newZoneLabel} onChange={(e) => setNewZoneLabel(e.target.value)} />
                    <input type="color" className="w-8 h-8 rounded cursor-pointer border border-gray-300" value={newZoneColor} onChange={(e) => setNewZoneColor(e.target.value)} />
                    <button className="btn btn-xs btn-primary" disabled={!newZoneLabel.trim()} onClick={() => { if (!newZoneLabel.trim()) return; clearDrawModes(); setDrawZoneMode({ label: newZoneLabel.trim(), color: newZoneColor }); setNewZoneLabel('') }}>+</button>
                  </div>
                  {drawZoneMode && (
                    <div className="fp-draw-hint mt-2" style={{ borderColor: drawZoneMode.color }}>
                      <span style={{ color: drawZoneMode.color }}>Dessin : <b>{drawZoneMode.label}</b></span>
                      <button className="btn btn-xs btn-ghost" onClick={() => setDrawZoneMode(null)}>Annuler</button>
                    </div>
                  )}
                  <div className="fp-divider" />
                  <p className="fp-group-label">Zones speciales</p>
                  <p className="fp-hint">Contraintes pour le placement auto.</p>
                  <div className="space-y-1">
                    <button className={`btn btn-sm w-full ${drawNoGoMode ? 'btn-error' : 'btn-outline'}`} onClick={() => { setDrawNoGoMode(!drawNoGoMode); setDrawRoundOnlyMode(false); setDrawRectOnlyMode(false); setDrawZoneMode(null) }}>Zone interdite{drawNoGoMode ? ' (actif)' : ''}</button>
                    <button className={`btn btn-sm w-full ${drawRoundOnlyMode ? 'btn-primary' : 'btn-outline'}`} onClick={() => { setDrawRoundOnlyMode(!drawRoundOnlyMode); setDrawNoGoMode(false); setDrawRectOnlyMode(false); setDrawZoneMode(null) }}>Rondes seul.{drawRoundOnlyMode ? ' (actif)' : ''}</button>
                    <button className={`btn btn-sm w-full ${drawRectOnlyMode ? 'btn-success' : 'btn-outline'}`} onClick={() => { setDrawRectOnlyMode(!drawRectOnlyMode); setDrawNoGoMode(false); setDrawRoundOnlyMode(false); setDrawZoneMode(null) }}>Rect seul.{drawRectOnlyMode ? ' (actif)' : ''}</button>
                  </div>
                </div>
              )}

              {/* TEMPLATE — Config */}
              {editMode === 'template' && templateTab === 'config' && (
                <div className="fp-tab-content">
                  <p className="fp-group-label">Numerotation</p>
                  <button className="btn btn-sm w-full mb-2" onClick={numberTables}>Numeroter tout</button>
                  {selectedTableIds.length > 0 ? (
                    <div className="mb-2">
                      <p className="fp-hint mb-1">Renuméroter {selectedTableIds.length} table(s) :</p>
                      <div className="flex gap-2">
                        <input className="input input-sm flex-1" value={renumberPrefix} onChange={(e) => setRenumberPrefix(e.target.value)} placeholder="Préfixe" />
                        <input className="input input-sm w-16" type="number" value={renumberStart} onChange={(e) => setRenumberStart(parseInt(e.target.value) || 1)} />
                        <button className="btn btn-sm btn-outline" onClick={renumberSelectedTables}>OK</button>
                      </div>
                    </div>
                  ) : <p className="fp-hint mb-2">Selectionnez des tables sur le plan.</p>}
                  <div className="fp-divider" />
                  <p className="fp-group-label">Stock dynamique</p>
                  <p className="fp-hint">Tables creeees automatiquement lors du placement.</p>
                  <div className="space-y-2 mt-1">
                    <label className="flex items-center justify-between text-sm">
                      <span>Rect (6-8 pax)</span>
                      <input type="number" min="0" max="50" className="input input-sm w-16" value={baseTemplate?.data?.max_dynamic_tables?.rect ?? 10} onChange={(e) => { if (!baseTemplate) return; const val = parseInt(e.target.value) || 0; setBaseTemplate({ ...baseTemplate, data: { ...baseTemplate.data, max_dynamic_tables: { ...baseTemplate.data?.max_dynamic_tables, rect: val } } }) }} />
                    </label>
                    <label className="flex items-center justify-between text-sm">
                      <span>Rondes (10 pax)</span>
                      <input type="number" min="0" max="50" className="input input-sm w-16" value={baseTemplate?.data?.max_dynamic_tables?.round ?? 5} onChange={(e) => { if (!baseTemplate) return; const val = parseInt(e.target.value) || 0; setBaseTemplate({ ...baseTemplate, data: { ...baseTemplate.data, max_dynamic_tables: { ...baseTemplate.data?.max_dynamic_tables, round: val } } }) }} />
                    </label>
                  </div>
                  <div className="fp-divider" />
                  <label className="flex items-center gap-2 text-sm cursor-pointer mb-3">
                    <input type="checkbox" checked={showGrid} onChange={(e) => setShowGrid(e.target.checked)} />
                    Afficher la grille
                  </label>
                  <button className="btn btn-sm w-full" onClick={exportBase} disabled={!baseTemplate}><Download className="w-4 h-4" /> Exporter PDF</button>
                </div>
              )}

              {/* INSTANCE — Reservations */}
              {editMode === 'instance' && instanceTab === 'reservations' && (
                <div className="fp-tab-content">
                  {!selectedInstance ? (
                    <p className="fp-hint">Selectionnez un service dans la barre du haut.</p>
                  ) : (
                    <>
                      <div className="fp-stats-grid mb-3">
                        <div className="fp-stat-card"><div className="fp-stat-value">{instanceReservationsCount}</div><div className="fp-stat-label">Res.</div></div>
                        <div className="fp-stat-card"><div className="fp-stat-value">{instanceAssignmentsCount}</div><div className="fp-stat-label">Tables</div></div>
                        <div className="fp-stat-card"><div className="fp-stat-value">{instanceDynamicTables}</div><div className="fp-stat-label">Dyn.</div></div>
                      </div>
                      <div className="space-y-2">
                        <button className="btn btn-sm w-full" onClick={importPDF} disabled={uploadingPDF}><Upload className="w-4 h-4" /> {uploadingPDF ? 'Import...' : 'Importer PDF'}</button>
                        <button className="btn btn-sm btn-primary w-full" onClick={autoAssign} disabled={uploadingPDF || !instanceHasReservations}>Placement automatique</button>
                        <button className="btn btn-sm btn-outline w-full" onClick={compareWithPDF}>Comparer au PDF</button>
                        <button className="btn btn-sm w-full" onClick={exportAnnotated}><Download className="w-4 h-4" /> PDF annote</button>
                      </div>
                      <div className="fp-divider" />
                      {!confirmDelete ? (
                        <button className="btn btn-xs btn-outline text-red-500 w-full" onClick={() => setConfirmDelete(true)}><Trash2 className="w-3 h-3" /> Supprimer ce service</button>
                      ) : (
                        <div className="flex gap-2">
                          <button className="btn btn-xs btn-error flex-1" onClick={deleteInstance}>Confirmer</button>
                          <button className="btn btn-xs btn-outline flex-1" onClick={() => setConfirmDelete(false)}>Annuler</button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* INSTANCE — Plan */}
              {editMode === 'instance' && instanceTab === 'plan' && (
                <div className="fp-tab-content">
                  <p className="fp-group-label">Tables</p>
                  <div className="fp-btn-grid mb-2">
                    <button onClick={() => addTable('fixed', 4)} className="btn btn-sm fp-add-btn"><span className="fp-table-dot" style={{ background: '#2ca' }}></span> Fixe (4)</button>
                    <button onClick={() => addTable('rect', 6)} className="btn btn-sm fp-add-btn"><span className="fp-table-dot" style={{ background: '#39f' }}></span> Rect (6-8)</button>
                    <button onClick={() => addTable('round', 10)} className="btn btn-sm fp-add-btn"><span className="fp-table-dot" style={{ background: '#f93' }}></span> Ronde (10)</button>
                    <button onClick={() => addTable('sofa', 5)} className="btn btn-sm fp-add-btn"><span className="fp-table-dot" style={{ background: '#9c27b0' }}></span> Canape (5)</button>
                    <button onClick={() => addTable('standing', 8)} className="btn btn-sm fp-add-btn"><span className="fp-table-dot" style={{ background: '#ff5722' }}></span> Debout (8)</button>
                    <button className="btn btn-sm btn-outline" onClick={() => addFixture('rect')}>Mur</button>
                    <button className="btn btn-sm btn-outline" onClick={() => addFixture('round')}>Colonne</button>
                  </div>
                  <div className="fp-divider" />
                  <p className="fp-group-label">Zones nommees</p>
                  {(currentData?.zones || []).length === 0 && <p className="fp-hint">Aucune zone.</p>}
                  <div className="space-y-1 mb-2">
                    {(currentData?.zones || []).map(z => (
                      <div key={z.id} className="fp-zone-row">
                        <span className="fp-zone-chip" style={{ background: z.color + '22', borderColor: z.color, color: z.color }}>{z.label}</span>
                        <button className={`btn btn-xs ${drawZoneMode?.label === z.label ? 'btn-primary' : 'btn-outline'}`} onClick={() => { if (drawZoneMode?.label === z.label) clearDrawModes(); else { clearDrawModes(); setDrawZoneMode({ label: z.label, color: z.color || '#3b82f6' }) } }}>{drawZoneMode?.label === z.label ? 'Stop' : 'Dessin'}</button>
                        <button className="btn btn-xs btn-ghost text-red-400" onClick={() => { if (!currentData) return; handleInstanceChange({ ...currentData, zones: (currentData.zones || []).filter(zz => zz.id !== z.id) }) }}>Suppr.</button>
                      </div>
                    ))}
                  </div>
                  <div className="fp-zone-presets mb-1">
                    {ZONE_PRESETS.map(p => (<button key={p.label} className="fp-zone-preset-btn" style={{ borderColor: p.color, color: p.color }} onClick={() => { clearDrawModes(); setDrawZoneMode({ label: p.label, color: p.color }) }}>{p.label}</button>))}
                  </div>
                  {drawZoneMode && (
                    <div className="fp-draw-hint" style={{ borderColor: drawZoneMode.color }}>
                      <span style={{ color: drawZoneMode.color }}>Dessin : <b>{drawZoneMode.label}</b></span>
                      <button className="btn btn-xs btn-ghost" onClick={() => setDrawZoneMode(null)}>Annuler</button>
                    </div>
                  )}
                  <p className="fp-group-label mt-2">Zones speciales</p>
                  <div className="space-y-1 mb-2">
                    <button className={`btn btn-sm w-full ${drawNoGoMode ? 'btn-error' : 'btn-outline'}`} onClick={() => { setDrawNoGoMode(!drawNoGoMode); setDrawRoundOnlyMode(false); setDrawRectOnlyMode(false); setDrawZoneMode(null) }}>Zone interdite{drawNoGoMode ? ' (actif)' : ''}</button>
                    <button className={`btn btn-sm w-full ${drawRoundOnlyMode ? 'btn-primary' : 'btn-outline'}`} onClick={() => { setDrawRoundOnlyMode(!drawRoundOnlyMode); setDrawNoGoMode(false); setDrawRectOnlyMode(false); setDrawZoneMode(null) }}>Rondes seul.{drawRoundOnlyMode ? ' (actif)' : ''}</button>
                    <button className={`btn btn-sm w-full ${drawRectOnlyMode ? 'btn-success' : 'btn-outline'}`} onClick={() => { setDrawRectOnlyMode(!drawRectOnlyMode); setDrawNoGoMode(false); setDrawRoundOnlyMode(false); setDrawZoneMode(null) }}>Rect seul.{drawRectOnlyMode ? ' (actif)' : ''}</button>
                  </div>
                  <div className="fp-divider" />
                  <p className="fp-group-label">Numerotation</p>
                  {selectedTableIds.length > 0 ? (
                    <div className="flex gap-2 mb-2">
                      <input className="input input-sm flex-1" value={renumberPrefix} onChange={(e) => setRenumberPrefix(e.target.value)} placeholder="Prefixe" />
                      <input className="input input-sm w-16" type="number" value={renumberStart} onChange={(e) => setRenumberStart(parseInt(e.target.value) || 1)} />
                      <button className="btn btn-sm btn-outline" onClick={renumberSelectedTables} disabled={!selectedInstance}>OK</button>
                    </div>
                  ) : <p className="fp-hint mb-2">Selectionnez des tables pour les renuméroter.</p>}
                  <div className="fp-divider" />
                  <p className="fp-group-label">Actions</p>
                  <div className="space-y-1 mb-2">
                    <button className="btn btn-sm btn-success w-full" onClick={saveInstance} disabled={!selectedInstance}><Save className="w-4 h-4" /> Sauvegarder</button>
                    <button className="btn btn-sm w-full" onClick={numberTables} disabled={!selectedInstance}>Numeroter</button>
                    <button className="btn btn-sm w-full" onClick={exportComplete} disabled={!selectedInstance}><Download className="w-4 h-4" /> Exporter PDF</button>
                    <button className="btn btn-sm btn-outline w-full" onClick={() => setResetViewTick(t => t + 1)}>Recentrer</button>
                    <button className="btn btn-sm btn-outline w-full" onClick={resetInstanceAction} disabled={!selectedInstance}>Reinitialiser</button>
                  </div>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={showGrid} onChange={(e) => setShowGrid(e.target.checked)} />
                    Afficher la grille
                  </label>
                </div>
              )}

            </div>
          </aside>
        )}

        {/* Canvas */}
        <main className="fp-canvas-area">
          {uiAlerts.length > 0 && (
            <div className="fp-ui-alerts">
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-yellow-800 text-sm">Alertes de placement</span>
                <button className="btn btn-xs btn-outline" onClick={() => setUiAlerts([])}>Effacer</button>
              </div>
              <ul className="list-disc pl-4 text-xs text-yellow-900 space-y-0.5 max-h-24 overflow-auto">
                {uiAlerts.map((a, idx) => <li key={idx}>{a}</li>)}
              </ul>
            </div>
          )}
          <div className="fp-toast-stack">
            {toasts.map(t => (
              <div key={t.id} className={`fp-toast fp-toast-${t.type}`}>
                {t.message}
              </div>
            ))}
          </div>
          {currentData ? (
            <FloorCanvas
              key={editMode === 'instance' ? (selectedInstance?.id || 'no-instance') : 'template'}
              data={currentData}
              assignments={editMode === 'instance' ? selectedInstance?.assignments : undefined}
              editable={true}
              showGrid={showGrid}
              className="w-full h-full"
              onChange={editMode === 'template' ? handleBaseChange : handleInstanceChange}
              drawNoGoMode={drawNoGoMode}
              drawRoundOnlyMode={drawRoundOnlyMode}
              drawRectOnlyMode={drawRectOnlyMode}
              drawZoneMode={drawZoneMode || undefined}
              initialScale={currentView?.scale}
              initialOffset={currentView?.offset}
              resetTrigger={resetViewTick}
              onSelectionChange={(ids) => setSelectedTableIds(ids)}
              onViewChange={(v) => { if (!selectedInstance) return; setViewByInstance(prev => ({ ...prev, [selectedInstance.id]: v })) }}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-3">
              <Layers className="w-12 h-12 opacity-30" />
              <p className="text-lg font-medium">{editMode === 'instance' ? 'Selectionnez ou creez un service' : 'Plan de base non disponible'}</p>
            </div>
          )}
        </main>
      </div>

      {/* Modal comparaison */}
      {showCompareModal && compareResult && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowCompareModal(false)}>
          <div className="bg-white rounded-xl p-6 max-w-2xl w-full mx-4 shadow-2xl max-h-[90vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-4">Comparaison placement vs PDF</h3>
            <div className="flex gap-6 text-sm mb-4">
              <span>Reservations : <b>{compareResult.counts?.reservations || 0}</b></span>
              <span>Assignees : <b>{compareResult.counts?.assigned_tables || 0}</b></span>
              <span>Orphelines : <b>{compareResult.counts?.orphan_assignments || 0}</b></span>
            </div>
            {(compareResult.reservations || []).filter((r: any) => !r.coverage_ok || r.assigned_tables_count === 0).length > 0 && (
              <div>
                <div className="font-semibold mb-2 text-sm">Reservations problematiques</div>
                <table className="table w-full text-xs">
                  <thead><tr><th>Heure</th><th>Client</th><th>Pax</th><th>Assigne</th><th>Tables</th></tr></thead>
                  <tbody>
                    {(compareResult.reservations || []).filter((r: any) => !r.coverage_ok || r.assigned_tables_count === 0).map((r: any) => (
                      <tr key={r.id} className={!r.coverage_ok ? 'bg-red-50' : 'bg-yellow-50'}>
                        <td>{r.arrival_time}</td><td className="font-medium">{r.client_name}</td><td>{r.pax}</td><td>{r.assigned_pax}</td>
                        <td>{r.labels?.length ? r.labels.join(', ') : <span className="text-gray-400">—</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <button className="btn btn-primary w-full mt-4" onClick={() => setShowCompareModal(false)}>Fermer</button>
          </div>
        </div>
      )}

      {/* Modal creation service */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowCreateModal(false)}>
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-4">Creer un service</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Date du service</label>
                <input type="date" className="input w-full" value={newInstanceDate} onChange={(e) => setNewInstanceDate(e.target.value)} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Periode</label>
                <select className="input w-full" value={newInstanceLabel} onChange={(e) => setNewInstanceLabel(e.target.value)}>
                  <option value="lunch">Midi</option>
                  <option value="dinner">Soir</option>
                  <option value="brunch">Brunch</option>
                </select>
              </div>
              <div className="flex gap-2 justify-end">
                <button className="btn btn-outline" onClick={() => setShowCreateModal(false)}>Annuler</button>
                <button className="btn btn-primary" onClick={createInstance}>Creer</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

