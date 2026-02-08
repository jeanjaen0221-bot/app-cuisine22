import React, { useEffect, useState } from 'react'
import { api, fileDownload, getFloorBase, updateFloorBase } from '../lib/api'
import FloorCanvas from '../components/FloorCanvas'
import { FloorPlanData, FloorPlanBase, FloorPlanInstance } from '../types'
import { Plus, Save, Trash2, Download, Upload, Calendar } from 'lucide-react'

export default function FloorPlanPage() {
  const [baseTemplate, setBaseTemplate] = useState<FloorPlanBase | null>(null)
  const [instances, setInstances] = useState<FloorPlanInstance[]>([])
  const [selectedInstance, setSelectedInstance] = useState<FloorPlanInstance | null>(null)
  const [editMode, setEditMode] = useState<'template' | 'instance'>('template')
  const [showGrid, setShowGrid] = useState(true)
  const [drawNoGoMode, setDrawNoGoMode] = useState(false)
  const [drawRoundOnlyMode, setDrawRoundOnlyMode] = useState(false)
  const [drawRectOnlyMode, setDrawRectOnlyMode] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newInstanceDate, setNewInstanceDate] = useState('')
  const [newInstanceLabel, setNewInstanceLabel] = useState('lunch')
  const [uploadingPDF, setUploadingPDF] = useState(false)
  const [viewByInstance, setViewByInstance] = useState<Record<string, { scale: number; offset: { x: number; y: number } }>>({})
  const [compareResult, setCompareResult] = useState<any | null>(null)
  const [showCompareModal, setShowCompareModal] = useState(false)
  const [showStock, setShowStock] = useState(true)
  const [uiAlerts, setUiAlerts] = useState<string[]>([])
  const [resetViewTick, setResetViewTick] = useState(0)
  const [selectedTableIds, setSelectedTableIds] = useState<string[]>([])
  const [renumberPrefix, setRenumberPrefix] = useState('')
  const [renumberStart, setRenumberStart] = useState(1)

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
      alert('Instance réinitialisée')
    } catch (err) {
      console.error('Failed to reset instance:', err)
      alert('Erreur réinitialisation')
    }
  }

  async function compareWithPDF() {
    if (!selectedInstance) {
      alert('Sélectionnez d\'abord une instance')
      return
    }
    try {
      const res = await api.get(`/api/floorplan/instances/${selectedInstance.id}/compare`)
      setCompareResult(res.data)
      setShowCompareModal(true)
    } catch (err) {
      console.error('Failed to compare instance:', err)
      alert('Erreur comparaison')
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
      await updateFloorBase({
        name: baseTemplate.name,
        data: baseTemplate.data
      })
      alert('Plan de base sauvegardé')
      await loadBase()
    } catch (err) {
      console.error('Failed to save base:', err)
      alert('Erreur lors de la sauvegarde')
    }
  }

  async function saveInstance() {
    if (!selectedInstance) return
    try {
      await api.put(`/api/floorplan/instances/${selectedInstance.id}`, {
        data: selectedInstance.data,
        assignments: selectedInstance.assignments
      })
      alert('Instance sauvegardée')
      await loadInstances()
    } catch (err) {
      console.error('Failed to save instance:', err)
      alert('Erreur lors de la sauvegarde')
    }
  }

  async function createInstance() {
    if (!newInstanceDate) {
      alert('Veuillez sélectionner une date')
      return
    }
    try {
      await api.post('/api/floorplan/instances', {
        service_date: newInstanceDate,
        service_label: newInstanceLabel
      })
      alert('Instance créée')
      setShowCreateModal(false)
      setNewInstanceDate('')
      await loadInstances()
    } catch (err: any) {
      console.error('Failed to create instance:', err)
      alert('Erreur: ' + (err.response?.data?.detail || 'Création échouée'))
    }
  }

  async function deleteInstance() {
    if (!selectedInstance) return
    if (!confirm(`Supprimer l'instance ${selectedInstance.service_date} ${selectedInstance.service_label}?`)) return
    try {
      await api.delete(`/api/floorplan/instances/${selectedInstance.id}`)
      setSelectedInstance(null)
      alert('Instance supprimée')
      await loadInstances()
    } catch (err) {
      console.error('Failed to delete instance:', err)
      alert('Erreur lors de la suppression')
    }
  }

  async function importPDF() {
    if (!selectedInstance) {
      alert('Sélectionnez d\'abord une instance')
      return
    }
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
        console.log('[IMPORT-PDF] Résultat:', res.data)
        alert(`${count} réservations importées`)
        await loadInstances()
        // Reload selected instance
        const updated = await api.get(`/api/floorplan/instances/${selectedInstance.id}`)
        setSelectedInstance(updated.data)
      } catch (err: any) {
        console.error('Failed to import PDF:', err)
        alert('Erreur import: ' + (err.response?.data?.detail || 'Échec'))
      } finally {
        setUploadingPDF(false)
      }
    }
    input.click()
  }

  async function autoAssign() {
    if (!selectedInstance) {
      alert('Sélectionnez d\'abord une instance')
      return
    }
    try {
      // Capturer AVANT l'appel API (évite bug de référence)
      const tablesBefore = selectedInstance?.data?.tables?.length || 0
      const res = await api.post(`/api/floorplan/instances/${selectedInstance.id}/auto-assign`)
      const assigned = Object.keys(res.data.assignments?.tables || {}).length
      const tablesAfter = res.data?.data?.tables?.length || 0
      const newTablesCreated = tablesAfter - tablesBefore
      const alerts: string[] = Array.isArray(res.data?.assignments?.alerts) ? res.data.assignments.alerts : []
      
      console.log('[AUTO-ASSIGN] Résultat:', {
        assigned,
        tablesBefore,
        tablesAfter,
        newTablesCreated,
        instanceData: res.data
      })
      
      if (alerts.length > 0) {
        const head = alerts.slice(0, 5).join('\n- ')
        const more = alerts.length > 5 ? `\n(+${alerts.length - 5} autres)` : ''
        alert(`${assigned} tables assignées${newTablesCreated > 0 ? ` (${newTablesCreated} nouvelles)` : ''}\n\nAlerte(s):\n- ${head}${more}`)
        setUiAlerts(alerts)
      } else {
        if (newTablesCreated > 0) {
          alert(`${assigned} tables assignées (${newTablesCreated} nouvelle(s) table(s) créée(s))`)
        } else {
          alert(`${assigned} tables assignées`)
        }
      }
      setSelectedInstance(res.data)
    } catch (err: any) {
      console.error('Failed to auto-assign:', err)
      alert('Erreur: ' + (err.response?.data?.detail || 'Auto-assign échoué'))
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
      alert('Tables numérotées')
    } catch (err) {
      console.error('Failed to number tables:', err)
      alert('Erreur numérotation')
    }
  }

  async function renumberSelectedTables() {
    const ids = selectedTableIds
    if (!ids.length) {
      alert('Sélectionnez d\'abord des tables')
      return
    }
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
      alert('Numérotation appliquée')
    } catch (err: any) {
      console.error('Failed to renumber tables:', err)
      alert('Erreur renumérotation: ' + (err.response?.data?.detail || 'Échec'))
    }
  }

  async function exportAnnotated() {
    if (!selectedInstance) {
      alert('Sélectionnez d\'abord une instance')
      return
    }
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
        alert('Erreur export')
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
      alert('Erreur export')
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

  const currentData = editMode === 'template' ? baseTemplate?.data : selectedInstance?.data
  const currentView = editMode === 'instance' && selectedInstance ? viewByInstance[selectedInstance.id] : undefined
  const instanceHasReservations = !!(selectedInstance?.reservations && Array.isArray((selectedInstance as any).reservations?.items) && (selectedInstance as any).reservations.items.length > 0)
  const instanceAssignmentsCount = Object.keys(selectedInstance?.assignments?.tables || {}).length
  const instanceHasAssignments = instanceAssignmentsCount > 0
  const instanceReservationsCount = (selectedInstance?.reservations && Array.isArray((selectedInstance as any).reservations?.items)) ? (selectedInstance as any).reservations.items.length : 0
  const instanceDynamicTables = (selectedInstance?.data?.tables || []).filter((t: any) => t && (t as any).dynamic).length

  return (
    <div className="space-y-6">
      <div className="card sticky top-0 z-10 bg-white/90 backdrop-blur shadow-sm">
        <div className="card-body">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="join">
                <button
                  className={`btn btn-sm join-item ${editMode === 'template' ? 'btn-primary' : 'btn-outline'}`}
                  onClick={() => setEditMode('template')}
                  title="Éditer le plan de base"
                >
                  Plans de base
                </button>
                <button
                  className={`btn btn-sm join-item ${editMode === 'instance' ? 'btn-primary' : 'btn-outline'}`}
                  onClick={() => setEditMode('instance')}
                  title="Gérer une instance (service)"
                >
                  <Calendar className="w-4 h-4" /> Instances
                </button>
              </div>

              {editMode === 'instance' && selectedInstance && (
                <div className="hidden lg:flex items-center gap-2 text-xs">
                  <span className="px-2 py-1 bg-gray-100 rounded text-gray-700" title="Nombre de réservations importées">Res: <b>{instanceReservationsCount}</b></span>
                  <span className="px-2 py-1 bg-gray-100 rounded text-gray-700" title="Nombre de tables assignées (côté plan)">Assign: <b>{instanceAssignmentsCount}</b></span>
                  <span className="px-2 py-1 bg-gray-100 rounded text-gray-700" title="Tables dynamiques présentes dans le plan">Dyn: <b>{instanceDynamicTables}</b></span>
                </div>
              )}
            </div>

            {editMode === 'template' && (
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-1 gap-2 lg:grid-cols-[1fr_auto] lg:items-center">
                  <div className="input bg-gray-100 cursor-not-allowed w-full">
                    {baseTemplate?.name || 'Plan de base'}
                  </div>

                  <div className="flex flex-wrap gap-2 lg:justify-end">
                    <button className="btn btn-sm btn-success" onClick={saveBase} disabled={!baseTemplate} title="Sauvegarder le plan de base">
                      <Save className="w-4 h-4" /> Sauvegarder
                    </button>
                    <button className="btn btn-sm" onClick={numberTables} title="Numéroter les tables du plan de base (1.., T.., R..)">
                      🔢 Numéroter
                    </button>
                  </div>
                </div>

                <div className="flex flex-col gap-2 rounded-xl border border-gray-200 bg-white p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm text-gray-700">
                      Sélection: <span className="inline-flex items-center px-2 py-0.5 rounded bg-gray-100"><b>{selectedTableIds.length}</b></span>
                    </div>
                    <input
                      className="input input-sm w-24"
                      value={renumberPrefix}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRenumberPrefix(e.target.value)}
                      placeholder="Préfixe"
                      title="Préfixe (ex: T, R, C, D ou vide)"
                    />
                    <input
                      className="input input-sm w-20"
                      type="number"
                      value={renumberStart}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRenumberStart(parseInt(e.target.value) || 1)}
                      title="Numéro de départ"
                    />
                    <button
                      className="btn btn-sm btn-outline"
                      onClick={renumberSelectedTables}
                      disabled={selectedTableIds.length === 0}
                      title="Appliquer une renumérotation sur les tables sélectionnées"
                    >
                      ✍️ Renuméroter sélection
                    </button>
                    <div className="ml-auto">
                      <button className="btn btn-xs btn-outline" onClick={() => setShowStock(s => !s)} title="Afficher/Masquer le stock de tables dynamiques">
                        {showStock ? '▼' : '►'} Stock dynamiques
                      </button>
                    </div>
                  </div>

                  {showStock && (
                    <div className="grid grid-cols-1 gap-2 lg:grid-cols-[auto_auto_1fr] lg:items-center text-sm">
                      <span className="font-semibold text-gray-700">📦 Stock tables disponibles:</span>
                      <label className="flex items-center gap-2" title="Nombre maximum de tables rectangulaires dynamiques créables">
                        <span>Tables rect (6-8 pax):</span>
                        <input
                          type="number"
                          min="0"
                          max="50"
                          className="input input-sm w-20"
                          value={baseTemplate?.data?.max_dynamic_tables?.rect || 10}
                          onChange={(e) => {
                            if (!baseTemplate) return
                            const val = parseInt(e.target.value) || 0
                            setBaseTemplate({
                              ...baseTemplate,
                              data: {
                                ...baseTemplate.data,
                                max_dynamic_tables: {
                                  ...baseTemplate.data?.max_dynamic_tables,
                                  rect: val
                                }
                              }
                            })
                          }}
                        />
                      </label>
                      <label className="flex items-center gap-2" title="Nombre maximum de tables rondes dynamiques créables">
                        <span>Tables rondes (10 pax):</span>
                        <input
                          type="number"
                          min="0"
                          max="50"
                          className="input input-sm w-20"
                          value={baseTemplate?.data?.max_dynamic_tables?.round || 5}
                          onChange={(e) => {
                            if (!baseTemplate) return
                            const val = parseInt(e.target.value) || 0
                            setBaseTemplate({
                              ...baseTemplate,
                              data: {
                                ...baseTemplate.data,
                                max_dynamic_tables: {
                                  ...baseTemplate.data?.max_dynamic_tables,
                                  round: val
                                }
                              }
                            })
                          }}
                        />
                      </label>
                      <span className="text-xs text-gray-500 lg:col-span-3">(Tables créées automatiquement si besoin lors de l'auto-assign)</span>
                    </div>
                  )}
                </div>
              </div>
            )}

      {/* Modal comparaison */}
      {showCompareModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowCompareModal(false)}>
          <div className="bg-white rounded-lg p-6 max-w-3xl w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-4">Comparaison placement ↔ PDF</h3>
            {compareResult ? (
              <div className="space-y-4 max-h-[70vh] overflow-auto">
                <div className="text-sm text-gray-700">
                  <div><b>Réservations</b>: {compareResult.counts?.reservations || 0}</div>
                  <div><b>Tables assignées</b>: {compareResult.counts?.assigned_tables || 0}</div>
                  <div><b>Assignations orphelines</b>: {compareResult.counts?.orphan_assignments || 0}</div>
                </div>

                <div>
                  <div className="font-semibold mb-2">Réservations problématiques</div>
                  <table className="table w-full text-sm">
                    <thead>
                      <tr>
                        <th>Heure</th>
                        <th>Client</th>
                        <th>Pax</th>
                        <th>Attribué</th>
                        <th>Tables</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(compareResult.reservations || []).filter((r:any) => !r.coverage_ok || r.assigned_tables_count === 0).map((r:any) => (
                        <tr key={r.id} className={!r.coverage_ok ? 'bg-red-50' : 'bg-yellow-50'}>
                          <td>{r.arrival_time}</td>
                          <td className="font-medium">{r.client_name}</td>
                          <td>{r.pax}</td>
                          <td>{r.assigned_pax}</td>
                          <td>{r.labels && r.labels.length ? r.labels.join(', ') : <span className="text-gray-500">—</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {compareResult.orphan_assignments && compareResult.orphan_assignments.length > 0 && (
                  <div>
                    <div className="font-semibold mb-2">Assignations orphelines (table → res_id inconnu)</div>
                    <table className="table w-full text-sm">
                      <thead>
                        <tr>
                          <th>Table</th>
                          <th>res_id</th>
                          <th>Client</th>
                          <th>Pax</th>
                        </tr>
                      </thead>
                      <tbody>
                        {compareResult.orphan_assignments.map((o:any, idx:number) => (
                          <tr key={idx}>
                            <td>{o.label || o.table_id}</td>
                            <td className="text-xs text-gray-600">{o.res_id}</td>
                            <td>{o.name}</td>
                            <td>{o.pax}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <div className="flex justify-end gap-2">
                  <button className="btn" onClick={() => setShowCompareModal(false)}>Fermer</button>
                </div>
              </div>
            ) : (
              <div className="text-gray-600">Aucune donnée</div>
            )}
          </div>
        </div>
      )}

            {editMode === 'instance' && (
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-1 gap-2 lg:grid-cols-[1fr_auto] lg:items-center">
                  <select
                    className="input w-full"
                    value={selectedInstance?.id || ''}
                    onChange={(e) => {
                      const i = instances.find(i => i.id === e.target.value)
                      setSelectedInstance(i || null)
                    }}
                    title="Choisir l'instance (service)"
                  >
                    <option value="">Sélectionner une instance</option>
                    {instances.map(i => (
                      <option key={i.id} value={i.id}>
                        {i.service_date} - {i.service_label || 'Service'}
                      </option>
                    ))}
                  </select>

                  <div className="flex flex-wrap gap-2 lg:justify-end">
                    <button className="btn btn-sm btn-primary" onClick={() => setShowCreateModal(true)} title="Créer une nouvelle instance (service)">
                      <Plus className="w-4 h-4" /> Créer
                    </button>
                    <button className="btn btn-sm btn-success" onClick={saveInstance} disabled={!selectedInstance} title="Sauvegarder l'instance">
                      <Save className="w-4 h-4" /> Sauvegarder
                    </button>
                    <button className="btn btn-sm btn-danger" onClick={deleteInstance} disabled={!selectedInstance} title="Supprimer l'instance">
                      <Trash2 className="w-4 h-4" /> Supprimer
                    </button>
                  </div>
                </div>

                {selectedInstance && (
                  <div className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-3">
                    <div className="text-xs font-semibold text-gray-600">Actions</div>
                    <div className="-mx-3 px-3 pb-1 overflow-x-auto">
                      <div className="flex gap-2 whitespace-nowrap">
                      <button className="btn btn-sm" onClick={importPDF} disabled={uploadingPDF} title="Importer le PDF de réservations pour cette instance">
                        <Upload className="w-4 h-4" /> {uploadingPDF ? 'Import...' : 'Import PDF'}
                      </button>
                      <button className="btn btn-sm btn-outline" onClick={resetInstanceAction} title="Vider l'instance (supprime tables dynamiques et assignations)">
                        ♻️ Réinitialiser
                      </button>
                      <button className="btn btn-sm" onClick={numberTables} title="Numéroter les tables de l'instance affichée">
                        🔢 Numéroter
                      </button>
                      <button className="btn btn-sm" onClick={compareWithPDF} title="Comparer placement ↔ PDF (diagnostic)">
                        🔎 Comparer PDF
                      </button>
                      <button className="btn btn-sm btn-outline" onClick={() => setResetViewTick(t => t + 1)} title="Recentrer et adapter la vue à la salle">
                        ⤾ Reset vue
                      </button>
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-xs font-semibold text-gray-600 lg:hidden w-full">Sélection</div>
                        <div className="text-sm text-gray-700">
                          Sélection: <span className="inline-flex items-center px-2 py-0.5 rounded bg-gray-100"><b>{selectedTableIds.length}</b></span>
                        </div>
                        <input
                          className="input input-sm w-24"
                          value={renumberPrefix}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRenumberPrefix(e.target.value)}
                          placeholder="Préfixe"
                          title="Préfixe (ex: T, R, C, D ou vide)"
                        />
                        <input
                          className="input input-sm w-20"
                          type="number"
                          value={renumberStart}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRenumberStart(parseInt(e.target.value) || 1)}
                          title="Numéro de départ"
                        />
                        <button
                          className="btn btn-sm btn-outline"
                          onClick={renumberSelectedTables}
                          disabled={!selectedInstance || selectedTableIds.length === 0}
                          title="Appliquer une renumérotation sur les tables sélectionnées"
                        >
                          ✍️ Renuméroter sélection
                        </button>
                      </div>

                      <div className="lg:hidden flex items-center gap-2 text-xs">
                        <span className="px-2 py-1 bg-gray-100 rounded text-gray-700" title="Nombre de réservations importées">Res: <b>{instanceReservationsCount}</b></span>
                        <span className="px-2 py-1 bg-gray-100 rounded text-gray-700" title="Nombre de tables assignées (côté plan)">Assign: <b>{instanceAssignmentsCount}</b></span>
                        <span className="px-2 py-1 bg-gray-100 rounded text-gray-700" title="Tables dynamiques présentes dans le plan">Dyn: <b>{instanceDynamicTables}</b></span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-2 mt-4">
            <div className="flex flex-col gap-2 rounded-xl border border-gray-200 bg-white p-3">
              <div className="flex flex-wrap gap-3 items-center">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={showGrid}
                  onChange={(e) => setShowGrid(e.target.checked)}
                />
                <span className="text-sm">Grille</span>
              </label>
              </div>

              <div className="flex flex-col gap-2">
                <div className="text-xs font-semibold text-gray-600">Ajouter</div>
                <div className="-mx-3 px-3 pb-1 overflow-x-auto">
                  <div className="flex gap-2 whitespace-nowrap">
                    <button onClick={() => addTable('fixed', 4)} className="btn btn-sm">+ Table fixe (4)</button>
                    <button onClick={() => addTable('rect', 6)} className="btn btn-sm">+ Rect (6→8)</button>
                    <button onClick={() => addTable('round', 10)} className="btn btn-sm">+ Ronde (10)</button>
                    <button onClick={() => addTable('sofa', 5)} className="btn btn-sm btn-sofa">+ Canapé (5)</button>
                    <button onClick={() => addTable('standing', 8)} className="btn btn-sm btn-standing">+ Mange-debout (8)</button>
                    <button className="btn btn-sm btn-outline" onClick={() => addFixture('rect')}>
                      ➕ Mur
                    </button>
                    <button className="btn btn-sm btn-outline" onClick={() => addFixture('round')}>
                      ➕ Colonne
                    </button>
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <div className="text-xs font-semibold text-gray-600">Dessiner zones</div>
                <div className="-mx-3 px-3 pb-1 overflow-x-auto">
                  <div className="flex gap-2 whitespace-nowrap">
              <button
                className={`btn btn-sm ${drawNoGoMode ? 'btn-danger' : 'btn-outline'}`}
                onClick={() => {
                  setDrawNoGoMode(!drawNoGoMode)
                  setDrawRoundOnlyMode(false)
                  setDrawRectOnlyMode(false)
                }}
              >
                🚫 Zone interdite
              </button>
              <button
                className={`btn btn-sm ${drawRoundOnlyMode ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => {
                  setDrawRoundOnlyMode(!drawRoundOnlyMode)
                  setDrawNoGoMode(false)
                  setDrawRectOnlyMode(false)
                }}
              >
                🔵 Zone R (rondes)
              </button>
              <button
                className={`btn btn-sm ${drawRectOnlyMode ? 'btn-success' : 'btn-outline'}`}
                onClick={() => {
                  setDrawRectOnlyMode(!drawRectOnlyMode)
                  setDrawNoGoMode(false)
                  setDrawRoundOnlyMode(false)
                }}
              >
                🟢 Zone T (rectangulaires)
              </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="card floorplan-canvas-card">
        {uiAlerts.length > 0 && (
          <div className="card mb-4 border border-yellow-300 bg-yellow-50">
            <div className="card-body">
              <div className="flex items-center justify-between mb-2">
                <div className="font-semibold text-yellow-800">Alerte(s) de placement</div>
                <button className="btn btn-xs btn-outline" onClick={() => setUiAlerts([])}>Effacer</button>
              </div>
              <ul className="list-disc pl-5 text-sm text-yellow-900 space-y-1">
                {uiAlerts.map((a, idx) => (
                  <li key={idx}>{a}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
        {currentData ? (
          <FloorCanvas
            key={editMode === 'instance' ? (selectedInstance?.id || 'template') : 'template'}
            data={currentData}
            assignments={editMode === 'instance' ? selectedInstance?.assignments : undefined}
            editable={true}
            showGrid={showGrid}
            onChange={editMode === 'template' ? handleBaseChange : handleInstanceChange}
            drawNoGoMode={drawNoGoMode}
            drawRoundOnlyMode={drawRoundOnlyMode}
            drawRectOnlyMode={drawRectOnlyMode}
            initialScale={currentView?.scale}
            initialOffset={currentView?.offset}
            resetTrigger={resetViewTick}
            onSelectionChange={(ids) => setSelectedTableIds(ids)}
            onViewChange={(v) => {
              if (!selectedInstance) return
              setViewByInstance(prev => ({ ...prev, [selectedInstance.id]: v }))
            }}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            Sélectionnez ou créez un plan
          </div>
        )}
      </div>

      {/* Modal création instance */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowCreateModal(false)}>
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-4">Créer une instance de service</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Date du service</label>
                <input
                  type="date"
                  className="input w-full"
                  value={newInstanceDate}
                  onChange={(e) => setNewInstanceDate(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Période</label>
                <select
                  className="input w-full"
                  value={newInstanceLabel}
                  onChange={(e) => setNewInstanceLabel(e.target.value)}
                >
                  <option value="lunch">Midi</option>
                  <option value="dinner">Soir</option>
                  <option value="brunch">Brunch</option>
                </select>
              </div>
              <div className="flex gap-2 justify-end">
                <button className="btn btn-outline" onClick={() => setShowCreateModal(false)}>Annuler</button>
                <button className="btn btn-primary" onClick={createInstance}>Créer</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
