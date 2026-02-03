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
              <div className="flex gap-2">
                <div className="input bg-gray-100 cursor-not-allowed">
                  {baseTemplate?.name || 'Plan de base'}
                </div>
                <button className="btn btn-sm btn-success" onClick={saveBase} disabled={!baseTemplate}>
                  <Save className="w-4 h-4" /> Sauvegarder
                </button>
              </div>
            )}

            {editMode === 'instance' && (
              <div className="flex gap-2">
                <select
                  className="input"
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
                <button className="btn btn-sm btn-success" onClick={saveInstance} disabled={!selectedInstance}>
                  <Save className="w-4 h-4" /> Sauvegarder
                </button>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2 mt-4">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={showGrid}
                onChange={(e) => setShowGrid(e.target.checked)}
              />
              <span className="text-sm">Grille</span>
            </label>
            <button
              className={`btn btn-sm ${drawNoGoMode ? 'btn-danger' : 'btn-outline'}`}
              onClick={() => {
                setDrawNoGoMode(!drawNoGoMode)
                setDrawRoundOnlyMode(false)
                setDrawRectOnlyMode(false)
              }}
            >
              Zone interdite
            </button>
            <button
              className={`btn btn-sm ${drawRoundOnlyMode ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => {
                setDrawRoundOnlyMode(!drawRoundOnlyMode)
                setDrawNoGoMode(false)
                setDrawRectOnlyMode(false)
              }}
            >
              Zone R (rondes)
            </button>
            <button
              className={`btn btn-sm ${drawRectOnlyMode ? 'btn-success' : 'btn-outline'}`}
              onClick={() => {
                setDrawRectOnlyMode(!drawRectOnlyMode)
                setDrawNoGoMode(false)
                setDrawRoundOnlyMode(false)
              }}
            >
              Zone T (rectangulaires)
            </button>
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
    </div>
  )
}
