import { useState, useEffect } from 'react'
import { Upload, Calendar, Users, Clock, Zap, Grid } from 'lucide-react'
import type { SalleService, SalleReservation } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export default function SallePage() {
  const [services, setServices] = useState<SalleService[]>([])
  const [selectedService, setSelectedService] = useState<SalleService | null>(null)
  const [uploading, setUploading] = useState(false)
  const [assigning, setAssigning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showPlan, setShowPlan] = useState(false)

  useEffect(() => {
    loadServices()
  }, [])

  async function loadServices() {
    try {
      const res = await fetch(`${API_BASE}/api/salle/services`)
      if (!res.ok) throw new Error('Failed to load services')
      const data = await res.json()
      setServices(data)
      
      // Auto-select most recent
      if (data.length > 0 && !selectedService) {
        setSelectedService(data[0])
      }
    } catch (err) {
      console.error('Load services error:', err)
      setError('Erreur de chargement des services')
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('service_label', 'brunch')

      const res = await fetch(`${API_BASE}/api/salle/import-pdf`, {
        method: 'POST',
        body: formData
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Import failed')
      }

      const data = await res.json()
      console.log('Import success:', data)

      // Reload services
      await loadServices()

      // Find and select the imported service
      const imported = services.find(s => s.id === data.service_id)
      if (imported) {
        setSelectedService(imported)
      }

      alert(`✅ Import réussi: ${data.reservations} réservations, ${data.total_covers} couverts`)
    } catch (err: any) {
      console.error('Upload error:', err)
      setError(err.message || 'Erreur d\'import PDF')
    } finally {
      setUploading(false)
      e.target.value = '' // Reset input
    }
  }

  async function handleAutoAssign() {
    if (!selectedService) return

    setAssigning(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/api/salle/services/${selectedService.id}/auto-assign`, {
        method: 'POST'
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Auto-assign failed')
      }

      const data = await res.json()
      console.log('Auto-assign success:', data)

      // Update selected service
      setSelectedService(data)

      // Update in services list
      setServices(prev => prev.map(s => s.id === data.id ? data : s))

      setShowPlan(true)
      alert(`✅ Attribution automatique réussie!`)
    } catch (err: any) {
      console.error('Auto-assign error:', err)
      setError(err.message || 'Erreur d\'attribution automatique')
    } finally {
      setAssigning(false)
    }
  }

  const reservations = selectedService?.reservations?.items || []
  const totalCovers = reservations.reduce((sum, r) => sum + r.pax, 0)
  const tables = selectedService?.plan_data?.tables || []
  const assignments = selectedService?.assignments?.tables || {}

  // Group by time
  const byTime = reservations.reduce((acc, r) => {
    const time = r.arrival_time
    if (!acc[time]) acc[time] = []
    acc[time].push(r)
    return acc
  }, {} as Record<string, SalleReservation[]>)

  const times = Object.keys(byTime).sort()

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Plan de Salle</h1>
        <div className="flex gap-2">
          <label className="btn btn-primary cursor-pointer">
            <Upload className="w-4 h-4" />
            {uploading ? 'Import...' : 'Importer PDF'}
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>
          {selectedService && reservations.length > 0 && (
            <>
              <button
                onClick={handleAutoAssign}
                disabled={assigning}
                className="btn btn-secondary"
              >
                <Zap className="w-4 h-4" />
                {assigning ? 'Attribution...' : 'Auto-Attribuer'}
              </button>
              {tables.length > 0 && (
                <button
                  onClick={() => setShowPlan(!showPlan)}
                  className="btn"
                >
                  <Grid className="w-4 h-4" />
                  {showPlan ? 'Masquer Plan' : 'Voir Plan'}
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Services List */}
        <div className="lg:col-span-1">
          <div className="card">
            <h2 className="text-lg font-semibold mb-3">Services</h2>
            <div className="space-y-2">
              {services.length === 0 && (
                <p className="text-sm text-gray-500">Aucun service</p>
              )}
              {services.map(service => (
                <button
                  key={service.id}
                  onClick={() => setSelectedService(service)}
                  className={`w-full text-left px-3 py-2 rounded transition ${
                    selectedService?.id === service.id
                      ? 'bg-violet-100 border border-violet-300'
                      : 'bg-gray-50 hover:bg-gray-100'
                  }`}
                >
                  <div className="font-medium">{service.service_date}</div>
                  <div className="text-sm text-gray-600">{service.service_label}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {service.reservations?.items?.length || 0} réservations
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Reservations */}
        <div className="lg:col-span-3">
          {!selectedService ? (
            <div className="card text-center py-12">
              <Calendar className="w-12 h-12 mx-auto text-gray-400 mb-3" />
              <p className="text-gray-500">Sélectionnez un service ou importez un PDF</p>
            </div>
          ) : (
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold">
                  {selectedService.service_date} - {selectedService.service_label}
                </h2>
                <div className="flex gap-4 text-sm">
                  <div className="flex items-center gap-1">
                    <Users className="w-4 h-4 text-gray-500" />
                    <span className="font-semibold">{reservations.length}</span>
                    <span className="text-gray-500">réservations</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Users className="w-4 h-4 text-gray-500" />
                    <span className="font-semibold">{totalCovers}</span>
                    <span className="text-gray-500">couverts</span>
                  </div>
                </div>
              </div>

              {/* Floor Plan Visual */}
              {showPlan && tables.length > 0 && (
                <div className="mb-6 p-4 bg-gray-50 rounded border border-gray-200">
                  <h3 className="font-semibold mb-3">Plan de Salle ({tables.length} tables)</h3>
                  <div className="relative bg-white border-2 border-gray-300 rounded" style={{ width: '100%', height: '400px', overflow: 'auto' }}>
                    <svg width="1000" height="600" className="border border-gray-200">
                      {/* Tables */}
                      {tables.map((table: any) => {
                        const assignment = assignments[table.id]
                        const isAssigned = !!assignment
                        const isFixed = table.kind === 'fixed'
                        const isRect = table.kind === 'rect'
                        
                        return (
                          <g key={table.id}>
                            {/* Table shape */}
                            <rect
                              x={table.x}
                              y={table.y}
                              width={table.w || 80}
                              height={table.h || 80}
                              fill={isAssigned ? '#10b981' : (isFixed ? '#e5e7eb' : '#fef3c7')}
                              stroke={isAssigned ? '#059669' : '#9ca3af'}
                              strokeWidth="2"
                              rx="4"
                            />
                            {/* Label */}
                            <text
                              x={table.x + (table.w || 80) / 2}
                              y={table.y + (table.h || 80) / 2 - 10}
                              textAnchor="middle"
                              fontSize="14"
                              fontWeight="bold"
                              fill={isAssigned ? '#fff' : '#374151'}
                            >
                              {table.label || '?'}
                            </text>
                            {/* Assignment info */}
                            {isAssigned && (
                              <>
                                <text
                                  x={table.x + (table.w || 80) / 2}
                                  y={table.y + (table.h || 80) / 2 + 5}
                                  textAnchor="middle"
                                  fontSize="10"
                                  fill="#fff"
                                >
                                  {assignment.name.substring(0, 12)}
                                </text>
                                <text
                                  x={table.x + (table.w || 80) / 2}
                                  y={table.y + (table.h || 80) / 2 + 18}
                                  textAnchor="middle"
                                  fontSize="10"
                                  fill="#fff"
                                >
                                  {assignment.pax} pax
                                </text>
                              </>
                            )}
                          </g>
                        )
                      })}
                    </svg>
                  </div>
                  <div className="mt-3 flex gap-4 text-sm">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-gray-200 border border-gray-400 rounded"></div>
                      <span>Tables fixes</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-yellow-100 border border-gray-400 rounded"></div>
                      <span>Tables rect créées</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-green-500 border border-green-600 rounded"></div>
                      <span>Assignées</span>
                    </div>
                  </div>
                </div>
              )}

              {reservations.length === 0 ? (
                <p className="text-gray-500 text-center py-8">Aucune réservation</p>
              ) : (
                <div className="space-y-6">
                  {times.map(time => (
                    <div key={time}>
                      <div className="flex items-center gap-2 mb-2">
                        <Clock className="w-4 h-4 text-gray-500" />
                        <h3 className="font-semibold">{time}</h3>
                        <span className="text-sm text-gray-500">
                          ({byTime[time].reduce((sum, r) => sum + r.pax, 0)} couverts)
                        </span>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                        {byTime[time].map(res => (
                          <div
                            key={res.id}
                            className="bg-gray-50 border border-gray-200 rounded px-3 py-2"
                          >
                            <div className="font-medium">{res.client_name}</div>
                            <div className="text-sm text-gray-600">
                              {res.pax} {res.pax > 1 ? 'personnes' : 'personne'}
                            </div>
                            {res.notes && (
                              <div className="text-xs text-gray-500 mt-1">{res.notes}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
