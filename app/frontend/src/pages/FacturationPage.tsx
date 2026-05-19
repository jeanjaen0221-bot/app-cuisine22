import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Trash2, Plus, ChevronRight, Receipt, Tag, Search, ExternalLink, CheckCircle2, Circle } from 'lucide-react'
import { api } from '../lib/api'
import type { Reservation, ReservationItem } from '../types'

// ---- Local types ----
type Preset = {
  id: string
  name: string
  default_quantity: number
  created_at: string
}

type BillingStatus = { exists: boolean; loaded: boolean }

// ---- Helpers ----
function deduceFormula(items: ReservationItem[]): string {
  const norm = (s: string) => s.toLowerCase().trim().replace(/é/g, 'e').replace(/è/g, 'e')
  const types = new Set(items.map(i => norm(i.type)))
  const hasEntree = types.has('entree') || types.has('entrees')
  const hasPlat = types.has('plat') || types.has('plats')
  const hasDessert = types.has('dessert') || types.has('desserts')
  if (hasEntree && hasPlat && hasDessert) return '3 services (Entrée · Plat · Dessert)'
  if (hasEntree && hasPlat) return '2 services (Entrée · Plat)'
  if (hasPlat && hasDessert) return '2 services (Plat · Dessert)'
  if (hasPlat) return '1 service (Plat)'
  return '—'
}

function formatDate(d: string) {
  if (!d) return '—'
  try {
    return new Date(d + 'T00:00').toLocaleDateString('fr-BE', { day: '2-digit', month: '2-digit', year: 'numeric' })
  } catch { return d }
}

// ---- Component ----
export default function FacturationPage() {
  const navigate = useNavigate()
  const [reservations, setReservations] = useState<Reservation[]>([])
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selected, setSelected] = useState<Reservation | null>(null)
  const [billingStatus, setBillingStatus] = useState<BillingStatus>({ exists: false, loaded: false })

  const [presets, setPresets] = useState<Preset[]>([])
  const [newPresetName, setNewPresetName] = useState('')
  const [newPresetQty, setNewPresetQty] = useState(1)
  const [presetError, setPresetError] = useState<string | null>(null)

  // Load reservations list
  useEffect(() => {
    api.get('/api/reservations').then(r => {
      const sorted = (r.data as Reservation[]).sort((a, b) =>
        new Date(b.service_date).getTime() - new Date(a.service_date).getTime()
      )
      setReservations(sorted)
    }).catch(() => {})
  }, [])

  // Load presets
  const loadPresets = useCallback(() => {
    api.get('/api/supplement-presets').then(r => setPresets(r.data)).catch(() => {})
  }, [])
  useEffect(() => { loadPresets() }, [loadPresets])

  // Select reservation → probe billing status (lightweight)
  async function selectReservation(res: Reservation) {
    setSelectedId(res.id)
    setSelected(res)
    setBillingStatus({ exists: false, loaded: false })
    try {
      await api.get(`/api/reservations/${res.id}/billing`)
      setBillingStatus({ exists: true, loaded: true })
    } catch {
      setBillingStatus({ exists: false, loaded: true })
    }
  }

  async function createPreset() {
    if (!newPresetName.trim()) return
    setPresetError(null)
    try {
      const r = await api.post('/api/supplement-presets', { name: newPresetName.trim(), default_quantity: newPresetQty })
      setPresets(prev => [...prev, r.data])
      setNewPresetName(''); setNewPresetQty(1)
    } catch (e: any) {
      setPresetError(e?.userMessage || 'Erreur')
    }
  }

  async function deletePreset(id: string) {
    try {
      await api.delete(`/api/supplement-presets/${id}`)
      setPresets(prev => prev.filter(p => p.id !== id))
    } catch {}
  }

  const filtered = reservations.filter(r =>
    !search || r.client_name.toLowerCase().includes(search.toLowerCase()) ||
    r.service_date.includes(search)
  )

  const formula = selected ? deduceFormula(selected.items) : '—'

  return (
    <div className="facturation-layout">
      {/* ===== LEFT: Reservation list ===== */}
      <div className="facturation-sidebar">
        <div className="facturation-sidebar-header">
          <Receipt className="w-5 h-5 text-violet-600" />
          <span className="font-semibold text-gray-800">Facturation</span>
        </div>
        <div className="p-3 border-b border-gray-100">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
            <input
              className="input w-full pl-8"
              placeholder="Rechercher client ou date…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        </div>
        <div className="facturation-list">
          {filtered.length === 0 && (
            <div className="p-4 text-gray-400 text-sm text-center">Aucune réservation</div>
          )}
          {filtered.map(res => {
            const active = res.id === selectedId
            return (
              <button
                key={res.id}
                onClick={() => selectReservation(res)}
                className={`facturation-list-item ${active ? 'facturation-list-item--active' : ''}`}
              >
                <div className="flex items-start justify-between gap-1">
                  <span className="font-medium text-sm text-gray-800 truncate">{res.client_name}</span>
                  <ChevronRight className="w-4 h-4 text-gray-400 shrink-0 mt-0.5" />
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {formatDate(res.service_date)} · {res.pax} pax
                </div>
                <div className="text-xs text-gray-400 mt-0.5 truncate">
                  {deduceFormula(res.items)} · {res.drink_formula || '—'}
                </div>
                {res.on_invoice && (
                  <span className="inline-block mt-1 px-1.5 py-0.5 rounded text-xs bg-green-50 text-green-700 border border-green-200">
                    Facturé
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* ===== RIGHT: Navigator panel ===== */}
      <div className="facturation-editor">
        {!selected ? (
          <div className="facturation-empty">
            <Receipt className="w-12 h-12 text-gray-300 mb-3" />
            <p className="text-gray-400 text-center">Sélectionnez une réservation<br />pour accéder à sa facturation</p>
          </div>
        ) : (
          <div className="facturation-editor-body">

            {/* ── Carte résumé ── */}
            <section>
              <div className="facturation-editor-header">
                <div>
                  <h2 className="text-lg font-semibold text-gray-800">{selected.client_name}</h2>
                  <p className="text-sm text-gray-500">
                    {formatDate(selected.service_date)} · {selected.arrival_time}
                  </p>
                </div>
              </div>

              <div className="facturation-summary-grid mt-3">
                <div className="facturation-summary-row">
                  <span className="facturation-summary-label">Nombre de pax</span>
                  <span className="facturation-summary-value font-semibold">{selected.pax}</span>
                </div>
                <div className="facturation-summary-row">
                  <span className="facturation-summary-label">Formule repas</span>
                  <span className="facturation-summary-value">{formula}</span>
                </div>
                <div className="facturation-summary-row">
                  <span className="facturation-summary-label">Formule boisson</span>
                  <span className="facturation-summary-value">{selected.drink_formula || '—'}</span>
                </div>
                <div className="facturation-summary-row">
                  <span className="facturation-summary-label">Infos de facturation</span>
                  <span className="facturation-summary-value">
                    {!billingStatus.loaded ? (
                      <span className="text-gray-400 text-xs">…</span>
                    ) : billingStatus.exists ? (
                      <span className="inline-flex items-center gap-1 text-green-700 text-xs font-medium">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Enregistrées
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-gray-400 text-xs">
                        <Circle className="w-3.5 h-3.5" /> Non renseignées
                      </span>
                    )}
                  </span>
                </div>
              </div>
            </section>

            {/* ── Bouton principal ── */}
            <section>
              <button
                className="btn btn-primary w-full flex items-center justify-center gap-2 py-3 text-base"
                onClick={() => navigate(`/reservation/${selected.id}?tab=facturation`)}
              >
                <ExternalLink className="w-4 h-4" />
                Ouvrir la facturation dans la fiche
              </button>
              <p className="text-xs text-gray-400 text-center mt-2">
                Infos de facturation · Suppléments · PDF
              </p>
            </section>

          </div>
        )}

        {/* ===== Bibliothèque suppléments (section globale) ===== */}
        <div className="facturation-editor-body border-t border-gray-100 mt-4">
          <section>
            <h3 className="facturation-section-title flex items-center gap-2">
              <Tag className="w-4 h-4 text-violet-500" /> Bibliothèque de suppléments prédéfinis
            </h3>
            <p className="text-sm text-gray-500 mb-4">
              Ces raccourcis apparaissent dans toutes les fiches, onglet Facturation.
            </p>

            {presetError && (
              <div className="mb-3 p-2 rounded bg-red-50 text-red-700 border border-red-200 text-sm">{presetError}</div>
            )}

            <div className="facturation-add-sup mb-4">
              <input
                className="input flex-1"
                placeholder="Nom du supplément (ex: Pain artisanal)"
                value={newPresetName}
                onChange={e => setNewPresetName(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') createPreset() }}
              />
              <input
                type="number" min={1}
                className="input w-20 text-center"
                value={newPresetQty}
                title="Quantité par défaut"
                onChange={e => setNewPresetQty(Math.max(1, parseInt(e.target.value) || 1))}
              />
              <button
                className="btn btn-primary flex items-center gap-1"
                onClick={createPreset}
                disabled={!newPresetName.trim()}
              >
                <Plus className="w-4 h-4" /> Créer
              </button>
            </div>

            {presets.length === 0 && (
              <div className="text-gray-400 text-sm text-center py-6">
                Aucun supplément prédéfini. Ajoutez-en un ci-dessus.
              </div>
            )}
            <div className="facturation-sup-list">
              {presets.map(p => (
                <div key={p.id} className="facturation-sup-row">
                  <Tag className="w-4 h-4 text-violet-400 shrink-0" />
                  <span className="flex-1 text-sm text-gray-800">{p.name}</span>
                  <span className="text-sm text-gray-500 w-16 text-center">×{p.default_quantity}</span>
                  <button className="btn-icon text-red-500 hover:text-red-700" onClick={() => deletePreset(p.id)}>
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </section>
        </div>

      </div>
    </div>
  )
}
