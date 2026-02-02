import { useEffect, useState } from 'react'
import { api, fileDownload } from '../lib/api'
import FloorCanvas from '../components/FloorCanvas'
import { FloorPlanData, FloorPlanBase, FloorPlanInstance } from '../types'
import { Plus, Save, Trash2, Download, Upload, Calendar } from 'lucide-react'

export default function FloorPlanPage() {
  const [templates, setTemplates] = useState<FloorPlanBase[]>([])
  const [instances, setInstances] = useState<FloorPlanInstance[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<FloorPlanBase | null>(null)
  const [selectedInstance, setSelectedInstance] = useState<FloorPlanInstance | null>(null)
  const [editMode, setEditMode] = useState<'template' | 'instance'>('template')
  const [showGrid, setShowGrid] = useState(true)
  const [drawNoGoMode, setDrawNoGoMode] = useState(false)
  const [drawRoundOnlyMode, setDrawRoundOnlyMode] = useState(false)
  const [drawRectOnlyMode, setDrawRectOnlyMode] = useState(false)

  useEffect(() => {
    loadTemplates()
    loadInstances()
  }, [])

  async function loadTemplates() {
    try {
      const res = await api.get('/api/floorplan/templates')
      setTemplates(res.data)
      if (res.data.length > 0 && !selectedTemplate) {
        setSelectedTemplate(res.data[0])
      }
    } catch (err) {
      console.error('Failed to load templates:', err)
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

  async function createTemplate() {
    const name = prompt('Nom du nouveau plan:')
    if (!name) return
    try {
      const res = await api.post('/api/floorplan/templates', {
        name,
        data: {
          room: { width: 1200, height: 800, grid: 50 },
          tables: [],
          walls: [],
          columns: [],
          no_go: [],
          fixtures: []
        }
      })
      await loadTemplates()
      setSelectedTemplate(res.data)
    } catch (err) {
      console.error('Failed to create template:', err)
    }
  }

  async function saveTemplate() {
    if (!selectedTemplate) return
    try {
      await api.put(`/api/floorplan/templates/${selectedTemplate.id}`, {
        name: selectedTemplate.name,
        data: selectedTemplate.data
      })
      alert('Plan sauvegardé')
      await loadTemplates()
    } catch (err) {
      console.error('Failed to save template:', err)
      alert('Erreur lors de la sauvegarde')
    }
  }

  async function deleteTemplate() {
    if (!selectedTemplate) return
    if (!confirm(`Supprimer le plan "${selectedTemplate.name}" ?`)) return
    try {
      await api.delete(`/api/floorplan/templates/${selectedTemplate.id}`)
      setSelectedTemplate(null)
      await loadTemplates()
    } catch (err) {
      console.error('Failed to delete template:', err)
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

  function handleTemplateChange(data: FloorPlanData) {
    if (selectedTemplate) {
      setSelectedTemplate({ ...selectedTemplate, data })
    }
  }

  function handleInstanceChange(data: FloorPlanData) {
    if (selectedInstance) {
      setSelectedInstance({ ...selectedInstance, data })
    }
  }

  const currentData = editMode === 'template' ? selectedTemplate?.data : selectedInstance?.data

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
                <select
                  className="input"
                  value={selectedTemplate?.id || ''}
                  onChange={(e) => {
                    const t = templates.find(t => t.id === e.target.value)
                    setSelectedTemplate(t || null)
                  }}
                >
                  <option value="">Sélectionner un plan</option>
                  {templates.map(t => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
                <button className="btn btn-sm btn-primary" onClick={createTemplate}>
                  <Plus className="w-4 h-4" /> Nouveau
                </button>
                <button className="btn btn-sm btn-success" onClick={saveTemplate} disabled={!selectedTemplate}>
                  <Save className="w-4 h-4" /> Sauvegarder
                </button>
                <button className="btn btn-sm btn-danger" onClick={deleteTemplate} disabled={!selectedTemplate}>
                  <Trash2 className="w-4 h-4" /> Supprimer
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
            onChange={editMode === 'template' ? handleTemplateChange : handleInstanceChange}
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
