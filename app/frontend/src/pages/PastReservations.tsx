import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, fileDownload } from '../lib/api'
import { Reservation } from '../types'
import { CalendarDays, Package, Printer, Pencil, Receipt, Search, Trash2, Users } from 'lucide-react'
import ConfirmDeleteModal from '../components/ConfirmDeleteModal'

type AllergenMeta = { key: string; label: string; icon_url?: string }
type PeriodPreset = 'current_month' | 'last_30' | 'last_90' | 'current_year' | 'custom'

const DAY_MS = 24 * 60 * 60 * 1000

const parseDate = (s: string) => {
  if (!s) return null
  const d = new Date(`${s}T00:00:00`)
  return Number.isNaN(d.getTime()) ? null : d
}

const formatInputDate = (d: Date) => {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const formatDate = (s: string) => {
  if (!s) return ''
  const d = parseDate(s)
  if (!d) return s
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

const formatShortDate = (d: Date) =>
  d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })

const formatLongDate = (d: Date) =>
  d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' })

const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
const endOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 59, 999)
const addDays = (d: Date, days: number) => {
  const next = new Date(d)
  next.setDate(next.getDate() + days)
  return next
}
const startOfWeek = (d: Date) => {
  const date = startOfDay(d)
  const day = (date.getDay() + 6) % 7
  date.setDate(date.getDate() - day)
  return date
}

const formatTime = (s: string) => (s || '').slice(0, 5)

const normalizeText = (s: string) =>
  s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()

const formatItemType = (raw?: string) => {
  const value = normalizeText(raw || '')
  if (!value) return 'Autre'
  if (value.startsWith('entree')) return 'Entrée'
  if (value.startsWith('plat')) return 'Plat'
  if (value.startsWith('dessert')) return 'Dessert'
  if (value.startsWith('supplement')) return 'Supplément'
  if (value.startsWith('boisson') || value.startsWith('drink')) return 'Boisson'
  return raw || 'Autre'
}

const isValidItem = (item?: Reservation['items'][number]) => {
  if (!item) return false
  const name = (item.name || '').trim()
  const qty = item.quantity || 0
  return Boolean(name) && qty > 0
}

const hasValidItems = (items: Reservation['items']) =>
  Array.isArray(items) && items.some(isValidItem)

const deduceMenuServices = (items: Reservation['items']) => {
  if (!Array.isArray(items) || items.length === 0) return '—'
  const types = new Set<string>()
  items.forEach(item => {
    if (!isValidItem(item)) return
    const type = normalizeText(item.type || '')
    if (!type || type.startsWith('supplement') || type.startsWith('boisson') || type.startsWith('drink')) return
    if (type.startsWith('entree')) types.add('entree')
    if (type.startsWith('plat')) types.add('plat')
    if (type.startsWith('dessert')) types.add('dessert')
  })
  const count = types.size
  if (count >= 3) return '3 services'
  if (count === 2) return '2 services'
  if (count === 1) return '1 service'
  return '—'
}

const allergenFallback: Record<string, string> = {
  gl: 'Gluten', la: 'Lait', oe: 'Oeufs', ar: 'Arachide', so: 'Soja',
  fr: 'Fruits à coque', se: 'Sésame', su: 'Sulfites', po: 'Poisson',
  cr: 'Crustacés', mo: 'Mollusques', ce: 'Céleri', lu: 'Lupin', mu: 'Moutarde', ai: 'Ail',
}

export default function PastReservations() {
  const [rows, setRows] = useState<Reservation[]>([])
  const [q, setQ] = useState('')
  const [activeTab, setActiveTab] = useState<'list' | 'analytics'>('list')
  const [periodPreset, setPeriodPreset] = useState<PeriodPreset>('current_month')
  const [customStart, setCustomStart] = useState(() => {
    const now = new Date()
    return formatInputDate(new Date(now.getFullYear(), now.getMonth(), 1))
  })
  const [customEnd, setCustomEnd] = useState(() => formatInputDate(new Date()))
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [allergenMeta, setAllergenMeta] = useState<Record<string, AllergenMeta>>({})
  const [toDelete, setToDelete] = useState<{ id: string; name: string } | null>(null)
  const navigate = useNavigate()

  async function confirmDelete() {
    if (!toDelete) return
    try {
      await api.delete(`/api/reservations/${toDelete.id}`)
      setRows(prev => prev.filter(r => r.id !== toDelete.id))
    } catch (err: any) {
      alert(`Erreur lors de la suppression: ${err?.response?.data?.detail || err.message}`)
    } finally {
      setToDelete(null)
    }
  }

  async function load() {
    setLoading(true)
    setLoadError(null)
    try {
      const perPage = 200
      const all: Reservation[] = []
      let page = 1
      while (true) {
        const res = await api.get('/api/reservations/past', { params: { page, per_page: perPage } })
        const batch = Array.isArray(res.data) ? (res.data as Reservation[]) : []
        all.push(...batch)
        if (batch.length < perPage) break
        page += 1
      }
      setRows(all)
    } catch (err: any) {
      setLoadError(err?.userMessage || err?.message || 'Erreur lors du chargement')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    api.get('/api/allergens').then(r => {
      const map: Record<string, AllergenMeta> = {}
      for (const a of (Array.isArray(r.data) ? r.data : [])) {
        if (a?.key) map[a.key] = { key: a.key, label: a.label || a.key, icon_url: a.icon_url }
      }
      setAllergenMeta(map)
    }).catch(() => {})
  }, [])

  const friendlyAllergen = (key: string) =>
    allergenMeta[key]?.label || allergenFallback[key] || key

  const periodRange = useMemo(() => {
    const now = new Date()
    let start = startOfDay(now)
    let end = endOfDay(now)

    if (periodPreset === 'current_month') {
      start = new Date(now.getFullYear(), now.getMonth(), 1)
    } else if (periodPreset === 'last_30') {
      start = addDays(startOfDay(now), -29)
    } else if (periodPreset === 'last_90') {
      start = addDays(startOfDay(now), -89)
    } else if (periodPreset === 'current_year') {
      start = new Date(now.getFullYear(), 0, 1)
    } else if (periodPreset === 'custom') {
      const customStartDate = parseDate(customStart)
      const customEndDate = parseDate(customEnd)
      if (customStartDate) start = startOfDay(customStartDate)
      if (customEndDate) end = endOfDay(customEndDate)
    }

    if (start > end) {
      const swapped = start
      start = end
      end = swapped
    }

    return {
      start,
      end,
      label: `${formatLongDate(start)} → ${formatLongDate(end)}`,
    }
  }, [periodPreset, customStart, customEnd])

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (!s) return rows
    return rows.filter(r => r.client_name.toLowerCase().includes(s))
  }, [rows, q])

  const analyticsRows = useMemo(() => {
    return rows.filter(r =>
      (r.status === 'confirmed' || r.status === 'printed')
      && hasValidItems(r.items)
    )
  }, [rows])

  const periodRows = useMemo(() => {
    return analyticsRows.filter(r => {
      const d = parseDate(r.service_date)
      if (!d) return false
      return d >= periodRange.start && d <= periodRange.end
    })
  }, [analyticsRows, periodRange])

  const periodTotals = useMemo(() => {
    let paxTotal = 0
    let itemTotal = 0
    const clientSet = new Set<string>()
    const statusCounts = { draft: 0, confirmed: 0, printed: 0 }

    periodRows.forEach(r => {
      paxTotal += r.pax || 0
      const clientKey = r.client_name.trim().toLowerCase()
      if (clientKey) clientSet.add(clientKey)
      if (r.status === 'confirmed') statusCounts.confirmed += 1
      else if (r.status === 'printed') statusCounts.printed += 1
      else statusCounts.draft += 1
      r.items?.forEach(item => {
        if (!isValidItem(item)) return
        itemTotal += item.quantity || 0
      })
    })

    return {
      paxTotal,
      itemTotal,
      uniqueClients: clientSet.size,
      statusCounts,
    }
  }, [periodRows])

  const volumeSeries = useMemo(() => {
    const totalDays = Math.ceil((periodRange.end.getTime() - periodRange.start.getTime()) / DAY_MS) + 1
    const useWeekly = totalDays > 45
    const counts = new Map<string, number>()

    periodRows.forEach(r => {
      const date = parseDate(r.service_date)
      if (!date) return
      const bucketDate = useWeekly ? startOfWeek(date) : startOfDay(date)
      const key = formatInputDate(bucketDate)
      counts.set(key, (counts.get(key) || 0) + 1)
    })

    const buckets: Array<{ key: string; label: string; value: number }> = []
    if (useWeekly) {
      let cursor = startOfWeek(periodRange.start)
      while (cursor <= periodRange.end) {
        const key = formatInputDate(cursor)
        buckets.push({
          key,
          label: formatShortDate(cursor),
          value: counts.get(key) || 0,
        })
        cursor = addDays(cursor, 7)
      }
    } else {
      let cursor = startOfDay(periodRange.start)
      while (cursor <= periodRange.end) {
        const key = formatInputDate(cursor)
        buckets.push({
          key,
          label: formatShortDate(cursor),
          value: counts.get(key) || 0,
        })
        cursor = addDays(cursor, 1)
      }
    }

    return { buckets, useWeekly }
  }, [periodRange, periodRows])

  const hourlySeries = useMemo(() => {
    const counts = Array.from({ length: 24 }, () => 0)
    periodRows.forEach(r => {
      const hour = Number.parseInt((r.arrival_time || '').slice(0, 2), 10)
      if (!Number.isNaN(hour) && hour >= 0 && hour < 24) counts[hour] += 1
    })
    return counts.map((value, hour) => ({ label: `${hour}h`, value }))
  }, [periodRows])

  const topItems = useMemo(() => {
    const map = new Map<string, { name: string; type: string; qty: number }>()
    periodRows.forEach(r => {
      r.items?.forEach(item => {
        if (!isValidItem(item)) return
        const name = (item.name || '').trim()
        const type = formatItemType(item.type)
        const key = `${type}|${normalizeText(name)}`
        const current = map.get(key)
        const qty = (item.quantity || 0) + (current?.qty || 0)
        map.set(key, { name, type, qty })
      })
    })
    return [...map.values()].sort((a, b) => b.qty - a.qty).slice(0, 6)
  }, [periodRows])

  const topDrinkFormulas = useMemo(() => {
    const map = new Map<string, { label: string; count: number }>()
    periodRows.forEach(r => {
      const label = (r.drink_formula || '—').trim() || '—'
      const key = normalizeText(label)
      map.set(key, { label, count: (map.get(key)?.count || 0) + 1 })
    })
    return [...map.values()].sort((a, b) => b.count - a.count).slice(0, 4)
  }, [periodRows])

  const topMenuFormulas = useMemo(() => {
    const map = new Map<string, { label: string; count: number }>()
    periodRows.forEach(r => {
      const label = deduceMenuServices(r.items)
      const key = normalizeText(label)
      map.set(key, { label, count: (map.get(key)?.count || 0) + 1 })
    })
    return [...map.values()].sort((a, b) => b.count - a.count).slice(0, 4)
  }, [periodRows])

  const statusSegments = useMemo(() => {
    const total = periodRows.length || 1
    return [
      { key: 'confirmed', label: 'Confirmée', value: periodTotals.statusCounts.confirmed, color: 'status-confirmed' },
      { key: 'printed', label: 'Imprimée', value: periodTotals.statusCounts.printed, color: 'status-printed' },
      { key: 'draft', label: 'Brouillon', value: periodTotals.statusCounts.draft, color: 'status-draft' },
    ].map(segment => ({
      ...segment,
      percent: Math.round((segment.value / total) * 100),
    }))
  }, [periodTotals.statusCounts, periodRows.length])

  const activeCount = activeTab === 'list' ? filtered.length : periodRows.length

  return (
    <div className="space-y-4 past-reservations-page">
      <div className="card card-static">
        <div className="card-header past-reservations-header">
          <div className="past-reservations-header-main">
            <h2 className="text-base font-semibold">Réservations passées
              <span className="ml-2 text-sm font-normal text-gray-400">({activeCount})</span>
            </h2>
            <div className="past-reservations-tabs">
              <button
                className={`past-reservations-tab ${activeTab === 'list' ? 'is-active' : ''}`}
                onClick={() => setActiveTab('list')}
              >Liste</button>
              <button
                className={`past-reservations-tab ${activeTab === 'analytics' ? 'is-active' : ''}`}
                onClick={() => setActiveTab('analytics')}
              >Analytique</button>
            </div>
          </div>
          {activeTab === 'list' && (
            <div className="relative">
              <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
              <input
                className="input pl-8 w-56"
                placeholder="Rechercher un client…"
                value={q}
                onChange={e => setQ(e.target.value)}
              />
            </div>
          )}
        </div>
      </div>

      {activeTab === 'list' ? (
        <div className="card">
          <div className="card-body overflow-auto p-0">
            <table className="table w-full">
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Date</th>
                  <th>Heure</th>
                  <th>Couverts</th>
                  <th>Statut</th>
                  <th>Allergènes</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading && filtered.length === 0 && (
                  <tr><td colSpan={7} className="p-6 text-center text-gray-500">Chargement des réservations…</td></tr>
                )}
                {!loading && loadError && (
                  <tr><td colSpan={7} className="p-6 text-center text-red-500">{loadError}</td></tr>
                )}
                {!loading && !loadError && filtered.length === 0 && (
                  <tr><td colSpan={7} className="p-6 text-center text-gray-500">Aucune réservation trouvée</td></tr>
                )}
                {filtered.map(r => {
                  const allergenKeys = r.allergens ? r.allergens.split(',').map(s => s.trim()).filter(Boolean) : []
                  return (
                    <tr
                      key={r.id}
                      className="cursor-pointer"
                      onClick={() => navigate(`/reservation/${r.id}`)}
                    >
                      <td className="capitalize font-medium">{r.client_name}</td>
                      <td>{formatDate(r.service_date)}</td>
                      <td>{formatTime(r.arrival_time)}</td>
                      <td>{r.pax}</td>
                      <td>
                        <span className={`status-badge ${
                          r.status === 'confirmed' ? 'is-confirmed' :
                          r.status === 'printed' ? 'is-printed' :
                          'is-draft'
                        }`}>
                          {r.status === 'confirmed' ? 'Confirmée' : r.status === 'printed' ? 'Imprimée' : 'Brouillon'}
                        </span>
                      </td>
                      <td>
                        {allergenKeys.length === 0
                          ? <span className="text-gray-400 text-xs">—</span>
                          : <div className="flex flex-wrap gap-1">
                              {allergenKeys.map(a => (
                                <span key={a} className="inline-block bg-red-50 text-red-700 text-xs px-1.5 py-0.5 rounded">
                                  {friendlyAllergen(a)}
                                </span>
                              ))}
                            </div>
                        }
                      </td>
                      <td onClick={e => e.stopPropagation()}>
                        <div className="flex justify-end gap-2">
                          <button
                            className="btn btn-sm btn-primary"
                            onClick={e => { e.stopPropagation(); navigate(`/reservation/${r.id}`) }}
                          ><Pencil className="h-3.5 w-3.5" /> Modifier</button>
                          <button
                            className="btn btn-sm btn-outline"
                            title="Télécharger la fiche PDF"
                            onClick={e => { e.stopPropagation(); fileDownload(`/api/reservations/${r.id}/pdf`) }}
                          ><Printer className="h-3.5 w-3.5" /></button>
                          <button
                            className="btn btn-sm btn-outline res-delete-btn"
                            title="Supprimer"
                            onClick={e => { e.stopPropagation(); setToDelete({ id: r.id, name: r.client_name }) }}
                          ><Trash2 className="h-3.5 w-3.5" /></button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="card analytics-panel">
            <div className="analytics-controls">
              <div className="analytics-control">
                <label className="label text-xs uppercase tracking-wide">Période</label>
                <div className="analytics-control-row">
                  <CalendarDays className="w-4 h-4 text-gray-400" />
                  <select
                    className="input"
                    value={periodPreset}
                    onChange={e => setPeriodPreset(e.target.value as PeriodPreset)}
                  >
                    <option value="current_month">Mois en cours</option>
                    <option value="last_30">30 derniers jours</option>
                    <option value="last_90">90 derniers jours</option>
                    <option value="current_year">Année en cours</option>
                    <option value="custom">Personnalisé</option>
                  </select>
                </div>
              </div>
              {periodPreset === 'custom' && (
                <div className="analytics-control analytics-control--range">
                  <label className="label text-xs uppercase tracking-wide">Dates</label>
                  <div className="analytics-range">
                    <input
                      type="date"
                      className="input"
                      value={customStart}
                      onChange={e => setCustomStart(e.target.value)}
                    />
                    <span className="text-gray-400 text-sm">→</span>
                    <input
                      type="date"
                      className="input"
                      value={customEnd}
                      onChange={e => setCustomEnd(e.target.value)}
                    />
                  </div>
                </div>
              )}
              <div className="analytics-control analytics-summary">
                <span className="text-xs text-gray-500">Période sélectionnée</span>
                <span className="text-sm font-medium text-gray-700">{periodRange.label}</span>
              </div>
              <div className="analytics-control analytics-summary">
                <span className="text-xs text-gray-500">Réservations incluses</span>
                <span className="text-sm font-medium text-gray-700">{periodRows.length}</span>
              </div>
            </div>
          </div>

          {loading ? (
            <div className="card analytics-empty">Chargement des statistiques…</div>
          ) : loadError ? (
            <div className="card analytics-empty text-red-500">{loadError}</div>
          ) : periodRows.length === 0 ? (
            <div className="card analytics-empty">Aucune réservation sur cette période.</div>
          ) : (
            <>
              <div className="analytics-kpis">
                <div className="analytics-kpi">
                  <div className="analytics-kpi-label">Réservations</div>
                  <div className="analytics-kpi-value">
                    <Receipt className="w-4 h-4" /> {periodRows.length}
                  </div>
                </div>
                <div className="analytics-kpi">
                  <div className="analytics-kpi-label">Couverts servis</div>
                  <div className="analytics-kpi-value">
                    <Users className="w-4 h-4" /> {periodTotals.paxTotal}
                  </div>
                </div>
                <div className="analytics-kpi">
                  <div className="analytics-kpi-label">Moyenne couverts / réservation</div>
                  <div className="analytics-kpi-value">
                    {periodRows.length ? (periodTotals.paxTotal / periodRows.length).toFixed(1) : '0'}
                  </div>
                </div>
                <div className="analytics-kpi">
                  <div className="analytics-kpi-label">Clients uniques</div>
                  <div className="analytics-kpi-value">
                    {periodTotals.uniqueClients}
                  </div>
                </div>
                <div className="analytics-kpi">
                  <div className="analytics-kpi-label">Articles servis</div>
                  <div className="analytics-kpi-value">
                    <Package className="w-4 h-4" /> {periodTotals.itemTotal}
                  </div>
                </div>
              </div>

              <div className="analytics-grid">
                <div className="card analytics-chart">
                  <div className="analytics-chart-header">
                    <div>
                      <h3 className="analytics-chart-title">Volume {volumeSeries.useWeekly ? 'par semaine' : 'par jour'}</h3>
                      <p className="analytics-chart-subtitle">Réservations sur la période</p>
                    </div>
                  </div>
                  <div className="analytics-chart-body">
                    <div className="analytics-bars">
                      {volumeSeries.buckets.map(bucket => (
                        <div key={bucket.key} className="analytics-bar-item" title={`${bucket.label} · ${bucket.value}`}>
                          <div
                            className="analytics-bar"
                            style={{ height: `${(bucket.value / Math.max(1, ...volumeSeries.buckets.map(b => b.value))) * 100}%` }}
                          />
                          <span className="analytics-bar-label">{bucket.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="card analytics-chart">
                  <div className="analytics-chart-header">
                    <div>
                      <h3 className="analytics-chart-title">Statuts</h3>
                      <p className="analytics-chart-subtitle">Répartition des réservations</p>
                    </div>
                  </div>
                  <div className="analytics-chart-body">
                    <div className="analytics-status-bar">
                      {statusSegments.map(segment => (
                        <div
                          key={segment.key}
                          className={`analytics-status-segment ${segment.color}`}
                          style={{ width: `${segment.percent}%` }}
                          title={`${segment.label} · ${segment.value}`}
                        />
                      ))}
                    </div>
                    <div className="analytics-legend">
                      {statusSegments.map(segment => (
                        <div key={segment.key} className="analytics-legend-item">
                          <span className={`analytics-legend-dot ${segment.color}`} />
                          <span className="analytics-legend-label">{segment.label}</span>
                          <span className="analytics-legend-value">{segment.percent}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="card analytics-chart">
                  <div className="analytics-chart-header">
                    <div>
                      <h3 className="analytics-chart-title">Heures d'arrivée</h3>
                      <p className="analytics-chart-subtitle">Distribution par heure</p>
                    </div>
                  </div>
                  <div className="analytics-chart-body">
                    <div className="analytics-bars">
                      {hourlySeries.map(bucket => (
                        <div key={bucket.label} className="analytics-bar-item" title={`${bucket.label} · ${bucket.value}`}>
                          <div
                            className="analytics-bar analytics-bar--accent"
                            style={{ height: `${(bucket.value / Math.max(1, ...hourlySeries.map(b => b.value))) * 100}%` }}
                          />
                          <span className="analytics-bar-label">{bucket.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="card analytics-chart">
                  <div className="analytics-chart-header">
                    <div>
                      <h3 className="analytics-chart-title">Top plats & suppléments</h3>
                      <p className="analytics-chart-subtitle">Quantités servies</p>
                    </div>
                  </div>
                  <div className="analytics-chart-body">
                    {topItems.length === 0 ? (
                      <div className="analytics-empty">Aucun item saisi pour cette période.</div>
                    ) : (
                      <div className="analytics-top-list">
                        {topItems.map(item => (
                          <div key={`${item.type}-${item.name}`} className="analytics-top-item">
                            <div className="analytics-top-name">
                              <span>{item.name}</span>
                              <span className="analytics-top-meta">{item.type}</span>
                            </div>
                            <span className="analytics-top-qty">×{item.qty}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <div className="card analytics-chart">
                  <div className="analytics-chart-header">
                    <div>
                      <h3 className="analytics-chart-title">Formules boissons</h3>
                      <p className="analytics-chart-subtitle">Top formules</p>
                    </div>
                  </div>
                  <div className="analytics-chart-body">
                    <div className="analytics-top-list">
                      {topDrinkFormulas.map(item => (
                        <div key={item.label} className="analytics-top-item">
                          <div className="analytics-top-name">
                            <span>{item.label}</span>
                          </div>
                          <span className="analytics-top-qty">{item.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="card analytics-chart">
                  <div className="analytics-chart-header">
                    <div>
                      <h3 className="analytics-chart-title">Formules menu</h3>
                      <p className="analytics-chart-subtitle">Top formules</p>
                    </div>
                  </div>
                  <div className="analytics-chart-body">
                    <div className="analytics-top-list">
                      {topMenuFormulas.map(item => (
                        <div key={item.label} className="analytics-top-item">
                          <div className="analytics-top-name">
                            <span>{item.label}</span>
                          </div>
                          <span className="analytics-top-qty">{item.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      <ConfirmDeleteModal
        open={toDelete !== null}
        clientName={toDelete?.name || ''}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      />
    </div>
  )
}
