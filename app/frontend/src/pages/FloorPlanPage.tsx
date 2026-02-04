import { useEffect, useState } from 'react'
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

  useEffect(() => {
    loadBase()
    loadInstances()
  }, [])

  async function loadBase() {
    try {
      const data = await getFloorBase()
      setBaseTemplate(data)
    } catch (err) {
      console.error('Failed to load base template:', err)
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
      
      console.log('[AUTO-ASSIGN] Résultat:', {
        assigned,
        tablesBefore,
        tablesAfter,
        newTablesCreated,
        instanceData: res.data
      })
      
      if (newTablesCreated > 0) {
        alert(`${assigned} tables assignées (${newTablesCreated} nouvelle(s) table(s) créée(s))`)
      } else {
        alert(`${assigned} tables assignées`)
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

  function addTable(kind: 'fixed' | 'rect' | 'round') {
    const target = editMode === 'template' ? baseTemplate : selectedInstance
    if (!target) return
    const tables = target.data.tables || []
    const id = `t_${Date.now()}_${Math.random().toString(36).slice(2,7)}`
    const capacity = kind === 'fixed' ? 4 : kind === 'rect' ? 6 : 10
    let newTable: any = { id, kind, x: 100, y: 100, capacity }
    if (kind === 'round') {
      newTable.r = 50
    } else {
      newTable.w = kind === 'fixed' ? 80 : 120
      newTable.h = kind === 'fixed' ? 80 : 60
    }
    const updated = { ...target.data, tables: [...tables, newTable] }
    if (editMode === 'template') {
      setBaseTemplate({ ...baseTemplate!, data: updated })
    } else {
      setSelectedInstance({ ...selectedInstance!, data: updated })
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

  return (
    <div className="space-y-6">
      <div className="card">
        <div className="card-body">
          <div className="flex flex-wrap gap-4 items-center justify-between">
            <div className="flex gap-2">
              <button
                className={`btn btn-sm ${editMode === 'template' ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => setEditMode('template')}
              >
                Plans de base
              </button>
              <button
                className={`btn btn-sm ${editMode === 'instance' ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => setEditMode('instance')}
              >
                <Calendar className="w-4 h-4" /> Instances
              </button>
            </div>

            {editMode === 'template' && (
              <div className="flex flex-col gap-2 w-full">
                <div className="flex gap-2">
                  <div className="input bg-gray-100 cursor-not-allowed">
                    {baseTemplate?.name || 'Plan de base'}
                  </div>
                  <button className="btn btn-sm btn-success" onClick={saveBase} disabled={!baseTemplate}>
                    <Save className="w-4 h-4" /> Sauvegarder
                  </button>
                </div>
                <div className="flex gap-4 items-center text-sm">
                  <span className="font-semibold text-gray-700">📦 Stock tables disponibles:</span>
                  <label className="flex items-center gap-2">
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
                  <label className="flex items-center gap-2">
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
                  <span className="text-xs text-gray-500">(Tables créées automatiquement si besoin lors de l'auto-assign)</span>
                </div>
              </div>
            )}

            {editMode === 'instance' && (
              <div className="flex flex-col gap-2 w-full">
                <div className="flex gap-2">
                  <select
                    className="input flex-1"
                    value={selectedInstance?.id || ''}
                    onChange={(e) => {
                      const i = instances.find(i => i.id === e.target.value)
                      setSelectedInstance(i || null)
                    }}
                  >
                    <option value="">Sélectionner une instance</option>
                    {instances.map(i => (
                      <option key={i.id} value={i.id}>
                        {i.service_date} - {i.service_label || 'Service'}
                      </option>
                    ))}
                  </select>
                  <button className="btn btn-sm btn-primary" onClick={() => setShowCreateModal(true)}>
                    <Plus className="w-4 h-4" /> Créer
                  </button>
                  <button className="btn btn-sm btn-success" onClick={saveInstance} disabled={!selectedInstance}>
                    <Save className="w-4 h-4" /> Sauvegarder
                  </button>
                  <button className="btn btn-sm btn-danger" onClick={deleteInstance} disabled={!selectedInstance}>
                    <Trash2 className="w-4 h-4" /> Supprimer
                  </button>
                </div>
                {selectedInstance && (
                  <div className="flex gap-2 flex-wrap">
                    <button className="btn btn-sm" onClick={importPDF} disabled={uploadingPDF}>
                      <Upload className="w-4 h-4" /> {uploadingPDF ? 'Import...' : 'Import PDF'}
                    </button>
                    <button className="btn btn-sm" onClick={autoAssign}>
                      🎯 Auto-Assign
                    </button>
                    <button className="btn btn-sm" onClick={exportAnnotated}>
                      <Download className="w-4 h-4" /> Export Annoté
                    </button>
                    <button className="btn btn-sm" onClick={exportComplete}>
                      <Download className="w-4 h-4" /> Export Complet
                    </button>
                    <button className="btn btn-sm" onClick={numberTables}>
                      🔢 Numéroter
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-2 mt-4">
            <div className="flex flex-wrap gap-2 items-center">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={showGrid}
                  onChange={(e) => setShowGrid(e.target.checked)}
                />
                <span className="text-sm">Grille</span>
              </label>
              <div className="border-l border-gray-300 h-6 mx-2"></div>
              <span className="text-xs font-semibold text-gray-600">Ajouter:</span>
              <button className="btn btn-sm btn-outline" onClick={() => addTable('fixed')}>
                ➕ Table Fixe (4 pax)
              </button>
              <button className="btn btn-sm btn-outline" onClick={() => addTable('rect')}>
                ➕ Table Rect (6-8 pax)
              </button>
              <button className="btn btn-sm btn-outline" onClick={() => addTable('round')}>
                ➕ Table Ronde (10 pax)
              </button>
              <button className="btn btn-sm btn-outline" onClick={() => addFixture('rect')}>
                ➕ Mur
              </button>
              <button className="btn btn-sm btn-outline" onClick={() => addFixture('round')}>
                ➕ Colonne
              </button>
              {(editMode === 'template' || selectedInstance) && (
                <button className="btn btn-sm" onClick={numberTables}>
                  🔢 Numéroter tables
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2 items-center">
              <span className="text-xs font-semibold text-gray-600">Dessiner zones:</span>
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

      <div className="card" style={{ height: 'calc(100vh - 300px)' }}>
        {currentData ? (
          <FloorCanvas
            data={currentData}
            assignments={editMode === 'instance' ? selectedInstance?.assignments : undefined}
            editable={true}
            showGrid={showGrid}
            onChange={editMode === 'template' ? handleBaseChange : handleInstanceChange}
            drawNoGoMode={drawNoGoMode}
            drawRoundOnlyMode={drawRoundOnlyMode}
            drawRectOnlyMode={drawRectOnlyMode}
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
