import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Trash2, Plus, ChevronRight, Receipt, Tag, Search, CheckCircle2, Circle, ExternalLink } from 'lucide-react'
import { api } from '../lib/api'
import BillingPanel from '../components/BillingPanel'
import type { Reservation } from '../types'
import { deduceFormula } from '../lib/utils'

// ---- Local types ----
type Preset = {
  id: string
  name: string
  default_quantity: number
  created_at: string
}

type BillingStatus = { exists: boolean; loaded: boolean }

// ---- Helpers ----

function formatDate(d: string) {
  if (!d) return '—'
  try {
    return new Date(d + 'T00:00').toLocaleDateString('fr-BE', { day: '2-digit', month: '2-digit', year: 'numeric' })
  } catch { return d }
}

// ---- Component ----
export default function FacturationPage() {
  const [reservations, setReservations] = useState<Reservation[]>([])
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selected, setSelected] = useState<Reservation | null>(null)
  const [billingStatus, setBillingStatus] = useState<BillingStatus>({ exists: false, loaded: false })

  const [presets, setPresets] = useState<Preset[]>([])
  const [newPresetName, setNewPresetName] = useState('')
  const [newPresetQty, setNewPresetQty] = useState(1)
  const [presetError, setPresetError] = useState<string | null>(null)
  const [showPresets, setShowPresets] = useState(false)

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
    r.on_invoice &&
    (!search || r.client_name.toLowerCase().includes(search.toLowerCase()) ||
    r.service_date.includes(search))
  )

  return (
    <div className="facturation-layout">
      {/* ===== LEFT: Reservation list ===== */}
      <div className="facturation-sidebar">
        <div className="facturation-sidebar-header">
          <Receipt className="w-5 h-5 text-violet-600" />
          <span className="font-semibold text-gray-800">Facturation</span>
          <button
            className={`ml-auto text-xs px-2 py-1 rounded border transition-colors ${showPresets ? 'bg-violet-50 border-violet-300 text-violet-700' : 'border-gray-200 text-gray-500 hover:bg-gray-50'}`}
            onClick={() => setShowPresets(v => !v)}
            title="Bibliothèque de suppléments"
          >
            <Tag className="w-3.5 h-3.5 inline mr-1" />Suppléments
          </button>
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
            <div className="p-4 text-gray-400 text-sm text-center">Aucune réservation avec facturation</div>
          )}
          {filtered.map(res => {
            const active = res.id === selectedId
            const hasBilling = active && billingStatus.loaded && billingStatus.exists
            const noBilling = active && billingStatus.loaded && !billingStatus.exists
            return (
              <button
                key={res.id}
                onClick={() => selectReservation(res)}
                className={`facturation-list-item ${active ? 'facturation-list-item--active' : ''}`}
              >
                <div className="flex items-start justify-between gap-1">
                  <span className="font-medium text-sm text-gray-800 truncate">{res.client_name}</span>
                  <div className="flex items-center gap-1 shrink-0">
                    {hasBilling && <span title="Billing enregistré"><CheckCircle2 className="w-3.5 h-3.5 text-green-500" /></span>}
                    {noBilling && <span title="Pas de billing"><Circle className="w-3.5 h-3.5 text-gray-300" /></span>}
                    <ChevronRight className="w-4 h-4 text-gray-400" />
                  </div>
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {formatDate(res.service_date)} · {res.pax} pax
                </div>
                <div className="text-xs text-gray-400 mt-0.5 truncate">
                  {res.menu_formula || deduceFormula(res.items)} · {res.drink_formula || '—'}
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

      {/* ===== RIGHT: BillingPanel or empty state ===== */}
      <div className="facturation-editor">
        {showPresets ? (
          /* ── Bibliothèque suppléments ── */
          <div className="facturation-editor-body">
            <section>
              <div className="flex items-center justify-between mb-1">
                <h3 className="facturation-section-title flex items-center gap-2 mb-0">
                  <Tag className="w-4 h-4 text-violet-500" /> Bibliothèque de suppléments prédéfinis
                </h3>
                <button className="btn btn-sm btn-outline" onClick={() => setShowPresets(false)}>← Retour</button>
              </div>
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
        ) : !selected ? (
          <div className="facturation-empty">
            <Receipt className="w-12 h-12 text-gray-300 mb-3" />
            <p className="text-gray-400 text-center">Sélectionnez une réservation<br />pour accéder à sa facturation</p>
          </div>
        ) : (
          /* ── BillingPanel embarqué directement ── */
          <div className="flex flex-col h-full">
            <div className="flex items-center justify-between px-6 pt-4 pb-2 border-b border-gray-100">
              <div>
                <h2 className="text-lg font-semibold text-gray-800">{selected.client_name}</h2>
                <p className="text-sm text-gray-500">{formatDate(selected.service_date)} · {selected.pax} pax</p>
              </div>
              <Link
                to={`/reservation/${selected.id}?tab=facturation`}
                className="btn btn-sm btn-outline flex items-center gap-1.5 text-xs"
                title="Ouvrir la fiche complète"
              >
                <ExternalLink className="w-3.5 h-3.5" /> Fiche
              </Link>
            </div>
            <div className="flex-1 overflow-auto">
              <BillingPanel
                key={selected.id}
                reservationId={selected.id}
                reservation={selected}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
