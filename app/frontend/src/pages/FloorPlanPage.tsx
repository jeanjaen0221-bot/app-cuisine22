import { useEffect, useState } from 'react'
import {
  getFloorBase,
  updateFloorBase,
  numberBaseTables,
  exportBasePdf,
  listFloorInstances,
  createFloorInstance,
  getFloorInstance,
  updateFloorInstance as updateFloorInstanceApi,
  numberInstanceTables,
  exportInstancePdf,
  exportInstanceAnnotatedPdf,
  autoAssignInstance,
  importReservationsPdf,
  setSalleDebug,
  getDebugLog,
} from '../lib/api'
import FloorCanvas from '../components/FloorCanvas'
import { FloorPlanData, FloorPlanBase, FloorPlanInstance } from '../types'
import { Plus, Save, Download, Upload, Calendar, Bug, Hash } from 'lucide-react'

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
  const [debugEnabled, setDebugEnabled] = useState(false)
  const [debugLines, setDebugLines] = useState<Array<{ id: number; ts: string; lvl: string; msg: string }>>([])
  const [lastDebugId, setLastDebugId] = useState<number | undefined>(undefined)
  const [serviceDate, setServiceDate] = useState<string>('')
  const [serviceLabel, setServiceLabel] = useState<string>('lunch')
  const [importPdfFile, setImportPdfFile] = useState<File | null>(null)
  const [annotatePdfFile, setAnnotatePdfFile] = useState<File | null>(null)
  const [viewTime, setViewTime] = useState<string>('')

  useEffect(() => {
    loadTemplates()
    loadInstances()
  }, [])

  async function loadTemplates() {
    try {
      const base = await getFloorBase()
      setTemplates([base])
      if (!selectedTemplate) setSelectedTemplate(base)
    } catch (err) {
      console.error('Failed to load base plan:', err)
    }
  }

  async function loadInstances() {
    try {
      const res = await listFloorInstances()
      setInstances(res)
    } catch (err) {
      console.error('Failed to load instances:', err)
    }
  }

  async function createInstance() {
    if (!serviceDate) {
      alert('Sélectionnez une date de service')
      return
    }
    try {
      const res = await createFloorInstance({ service_date: serviceDate, service_label: serviceLabel || null })
      await loadInstances()
      setSelectedInstance(res)
    } catch (err: any) {
      console.error('Failed to create instance:', err)
      alert(err?.userMessage || 'Erreur lors de la création de l\'instance')
    }
  }

  async function saveTemplate() {
    if (!selectedTemplate) return
    try {
      await updateFloorBase({ name: selectedTemplate.name, data: selectedTemplate.data })
      alert('Plan de base sauvegardé')
      await loadTemplates()
    } catch (err) {
      console.error('Failed to save base plan:', err)
      alert('Erreur lors de la sauvegarde')
    }
  }

  async function numberBase() {
    try {
      await numberBaseTables()
      await loadTemplates()
    } catch (err) {
      console.error('Failed to number base tables:', err)
      alert('Erreur de numérotation')
    }
  }

  async function exportBase() {
    try {
      await exportBasePdf()
    } catch (err) {
      console.error('Failed to export base PDF:', err)
      alert('Erreur export PDF base')
    }
  }

  async function saveInstance() {
    if (!selectedInstance) return
    try {
      await updateFloorInstanceApi(selectedInstance.id, {
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

  async function numberInstance() {
    if (!selectedInstance) return
    try {
      const res = await numberInstanceTables(selectedInstance.id)
      setSelectedInstance(res)
    } catch (err) {
      console.error('Failed to number instance tables:', err)
    }
  }

  async function doAutoAssign() {
    if (!selectedInstance) return
    try {
      const res = await autoAssignInstance(selectedInstance.id)
      setSelectedInstance(res)
    } catch (err: any) {
      console.error('Failed auto-assign:', err)
      alert(err?.userMessage || 'Erreur auto-assign')
    }
  }

  async function doImportPdf() {
    try {
      if (!importPdfFile) {
        alert('Sélectionnez un fichier PDF à importer')
        return
      }
      if (!serviceDate) {
        alert('Saisissez la date de service (pour associer l\'import à l\'instance)')
        return
      }
      await importReservationsPdf(importPdfFile, serviceDate, serviceLabel || null)
      alert('PDF importé (réservations stockées dans l\'instance)')
    } catch (err) {
      console.error('Failed to import PDF:', err)
      alert('Erreur import PDF')
    }
  }

  async function doExportInstance() {
    if (!selectedInstance) return
    try { await exportInstancePdf(selectedInstance.id, viewTime ? { at: viewTime } : undefined) } catch (err) {
      console.error('Failed to export instance PDF:', err)
    }
  }

  async function doExportAnnotated() {
    if (!selectedInstance) return
    if (!annotatePdfFile) { alert('Sélectionnez le PDF original à annoter'); return }
    try { await exportInstanceAnnotatedPdf(selectedInstance.id, annotatePdfFile) } catch (err) {
      console.error('Failed to export annotated PDF:', err)
      alert('Erreur export PDF annoté')
    }
  }

  useEffect(() => {
    if (!debugEnabled) return
    setSalleDebug(true)
    let cancelled = false
    const tick = async () => {
      try {
        const r = await getDebugLog(lastDebugId, 200)
        if (!cancelled && r && r.lines && r.lines.length) {
          setDebugLines(prev => [...prev, ...r.lines])
          setLastDebugId(r.last)
        }
      } catch {}
    }
    const id = setInterval(tick, 1500)
    return () => { cancelled = true; clearInterval(id); setSalleDebug(false) }
  }, [debugEnabled, lastDebugId])

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
                  {templates.map(t => (
                    <option key={t.id} value={t.id}>{t.name || 'Plan de base'}</option>
                  ))}
                </select>
                <button className="btn btn-sm btn-success" onClick={saveTemplate} disabled={!selectedTemplate}>
                  <Save className="w-4 h-4" /> Sauvegarder
                </button>
                <button className="btn btn-sm btn-outline" onClick={numberBase} disabled={!selectedTemplate}>
                  <Hash className="w-4 h-4" /> Numéroter
                </button>
                <button className="btn btn-sm btn-outline" onClick={exportBase} disabled={!selectedTemplate}>
                  <Download className="w-4 h-4" /> Export PDF
                </button>
              </div>
            )}

            {editMode === 'instance' && (
              <div className="flex flex-wrap gap-2 items-center">
                <input type="date" className="input" value={serviceDate} onChange={e => setServiceDate(e.target.value)} />
                <select className="input" value={serviceLabel} onChange={e => setServiceLabel(e.target.value)}>
                  <option value="lunch">lunch</option>
                  <option value="dinner">dinner</option>
                </select>
                <input type="time" className="input" value={viewTime} onChange={e => setViewTime(e.target.value)} />
                <button className="btn btn-sm btn-primary" onClick={createInstance}>
                  <Plus className="w-4 h-4" /> Créer instance
                </button>
                <select
                  className="input"
                  value={selectedInstance?.id || ''}
                  onChange={async (e) => {
                    const i = instances.find(i => i.id === e.target.value)
                    if (i) {
                      const row = await getFloorInstance(i.id)
                      setSelectedInstance(row)
                    } else {
                      setSelectedInstance(null)
                    }
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
                <button className="btn btn-sm btn-outline" onClick={numberInstance} disabled={!selectedInstance}>
                  <Download className="w-4 h-4" /> Numéroter
                </button>
                <label className="btn btn-sm btn-outline cursor-pointer">
                  <Upload className="w-4 h-4" /> Import PDF
                  <input type="file" accept="application/pdf" className="hidden" onChange={e => setImportPdfFile(e.target.files?.[0] || null)} />
                </label>
                <button className="btn btn-sm btn-outline" onClick={doImportPdf}>
                  Lancer import
                </button>
                <button className="btn btn-sm btn-outline" onClick={doAutoAssign} disabled={!selectedInstance}>
                  Auto-assign
                </button>
                <button className="btn btn-sm btn-outline" onClick={doExportInstance} disabled={!selectedInstance}>
                  <Download className="w-4 h-4" /> Export PDF
                </button>
                <label className="btn btn-sm btn-outline cursor-pointer">
                  <Upload className="w-4 h-4" /> PDF à annoter
                  <input type="file" accept="application/pdf" className="hidden" onChange={e => setAnnotatePdfFile(e.target.files?.[0] || null)} />
                </label>
                <button className="btn btn-sm btn-outline" onClick={doExportAnnotated} disabled={!selectedInstance}>
                  Export annoté
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
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={debugEnabled}
                onChange={(e) => { setDebugEnabled(e.target.checked); if (!e.target.checked) { setDebugLines([]); setLastDebugId(undefined) } }}
              />
              <span className="text-sm flex items-center gap-1"><Bug className="w-4 h-4" /> Debug salle</span>
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
            viewTime={editMode === 'instance' ? (viewTime || undefined) : undefined}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            Sélectionnez ou créez un plan
          </div>
        )}
      </div>

      {debugEnabled && (
        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between mb-2">
              <div className="font-semibold">Logs salle</div>
              <button className="btn btn-xs btn-outline" onClick={() => { setDebugLines([]); setLastDebugId(undefined) }}>Effacer</button>
            </div>
            <div className="h-40 overflow-auto border rounded p-2 bg-gray-50 text-xs font-mono">
              {debugLines.map(l => (
                <div key={l.id}>
                  <span className="text-gray-500">[{l.ts}]</span> <span className={`font-semibold ${l.lvl === 'ERROR' ? 'text-red-600' : l.lvl === 'WARNING' ? 'text-yellow-700' : 'text-gray-700'}`}>{l.lvl}</span> {l.msg}
                </div>
              ))}
              {debugLines.length === 0 && <div className="text-gray-400">Aucun log (activez une action pour voir les événements)</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
