import { useEffect, useState, useCallback } from 'react'
import { Trash2, Plus, Download, Save, ChevronRight, Receipt, Tag } from 'lucide-react'
import { api, fileDownload } from '../lib/api'
import type { Reservation, ReservationItem } from '../types'

// ---- Local types ----
type BillingForm = {
  company_name: string
  address_line1: string
  address_line2: string
  zip_code: string
  city: string
  country: string
  vat_number: string
  email: string
  phone: string
  payment_terms: string
  notes: string
}

type Supplement = {
  id: string
  reservation_id: string
  description: string
  quantity: number
  sort_order: number
  created_at: string
}

type Preset = {
  id: string
  name: string
  default_quantity: number
  created_at: string
}

// ---- Helpers ----
function deduceFormula(items: ReservationItem[]): string {
  const norm = (s: string) => s.toLowerCase().trim().replace(/é/g, 'e').replace(/è/g, 'e')
  const types = new Set(items.map(i => norm(i.type)))
  const hasEntree = types.has('entree') || types.has('entrees')
  const hasPlat = types.has('plat') || types.has('plats')
  const hasDessert = types.has('dessert') || types.has('desserts')
  if (hasEntree && hasPlat && hasDessert) return '3 services (Entrée - Plat - Dessert)'
  if (hasEntree && hasPlat) return '2 services (Entrée - Plat)'
  if (hasPlat && hasDessert) return '2 services (Plat - Dessert)'
  if (hasPlat) return '1 service (Plat)'
  return '-'
}

function formatDate(d: string) {
  if (!d) return '-'
  try {
    return new Date(d).toLocaleDateString('fr-BE', { day: '2-digit', month: '2-digit', year: 'numeric' })
  } catch { return d }
}

const EMPTY_BILLING: BillingForm = {
  company_name: '', address_line1: '', address_line2: '',
  zip_code: '', city: '', country: 'Belgique',
  vat_number: '', email: '', phone: '',
  payment_terms: 'Paiement à 30 jours', notes: '',
}

// ---- Component ----
export default function FacturationPage() {
  const [reservations, setReservations] = useState<Reservation[]>([])
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selected, setSelected] = useState<Reservation | null>(null)

  const [billing, setBilling] = useState<BillingForm>(EMPTY_BILLING)
  const [billingExists, setBillingExists] = useState(false)
  const [supplements, setSupplements] = useState<Supplement[]>([])
  const [presets, setPresets] = useState<Preset[]>([])

  const [newSupDesc, setNewSupDesc] = useState('')
  const [newSupQty, setNewSupQty] = useState(1)
  const [editQty, setEditQty] = useState<Record<string, string>>({})  // local qty edits
  const [newPresetName, setNewPresetName] = useState('')
  const [newPresetQty, setNewPresetQty] = useState(1)

  const [tab, setTab] = useState<'facture' | 'presets'>('facture')
  const [loading, setLoading] = useState(false)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

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

  // Select reservation → load billing + supplements
  async function selectReservation(res: Reservation) {
    setSelectedId(res.id)
    setSelected(res)
    setError(null)
    setSaveMsg(null)
    setLoading(true)
    try {
      const [billRes, supRes] = await Promise.allSettled([
        api.get(`/api/reservations/${res.id}/billing`),
        api.get(`/api/reservations/${res.id}/supplements`),
      ])
      if (billRes.status === 'fulfilled') {
        const b = billRes.value.data
        setBilling({
          company_name: b.company_name || '',
          address_line1: b.address_line1 || '',
          address_line2: b.address_line2 || '',
          zip_code: b.zip_code || '',
          city: b.city || '',
          country: b.country || 'Belgique',
          vat_number: b.vat_number || '',
          email: b.email || '',
          phone: b.phone || '',
          payment_terms: b.payment_terms || 'Paiement à 30 jours',
          notes: b.notes || '',
        })
        setBillingExists(true)
      } else {
        setBilling({ ...EMPTY_BILLING })
        setBillingExists(false)
      }
      if (supRes.status === 'fulfilled') {
        setSupplements(supRes.value.data)
      } else {
        setSupplements([])
      }
    } finally {
      setLoading(false)
    }
  }

  function setB<K extends keyof BillingForm>(k: K, v: string) {
    setBilling(prev => ({ ...prev, [k]: v }))
  }

  async function saveBilling() {
    if (!selectedId) return
    setError(null); setSaveMsg(null); setLoading(true)
    try {
      const payload = {
        company_name: billing.company_name.trim(),
        address_line1: billing.address_line1.trim(),
        address_line2: billing.address_line2.trim() || undefined,
        zip_code: billing.zip_code.trim(),
        city: billing.city.trim(),
        country: billing.country.trim() || undefined,
        vat_number: billing.vat_number.trim() || undefined,
        email: billing.email.trim() || undefined,
        phone: billing.phone.trim() || undefined,
        payment_terms: billing.payment_terms.trim() || undefined,
        notes: billing.notes.trim() || undefined,
      }
      if (billingExists) {
        await api.put(`/api/reservations/${selectedId}/billing`, payload)
      } else {
        await api.post(`/api/reservations/${selectedId}/billing`, payload)
        setBillingExists(true)
      }
      setSaveMsg('Sauvegardé ✓')
      setTimeout(() => setSaveMsg(null), 3000)
    } catch (e: any) {
      setError(e?.userMessage || 'Erreur lors de la sauvegarde')
    } finally {
      setLoading(false)
    }
  }

  async function downloadPDF() {
    if (!selectedId) return
    fileDownload(`/api/reservations/${selectedId}/invoice-pdf`)
  }

  async function addSupplement(desc: string, qty: number) {
    if (!selectedId || !desc.trim()) return
    try {
      const r = await api.post(`/api/reservations/${selectedId}/supplements`, {
        description: desc.trim(), quantity: qty, sort_order: supplements.length,
      })
      setSupplements(prev => [...prev, r.data])
    } catch (e: any) {
      setError(e?.userMessage || 'Erreur')
    }
  }

  async function deleteSupplement(supId: string) {
    if (!selectedId) return
    try {
      await api.delete(`/api/reservations/${selectedId}/supplements/${supId}`)
      setSupplements(prev => prev.filter(s => s.id !== supId))
    } catch (e: any) {
      setError(e?.userMessage || 'Erreur')
    }
  }

  async function updateSupplementQty(sup: Supplement, qty: number) {
    if (!selectedId) return
    try {
      const r = await api.put(`/api/reservations/${selectedId}/supplements/${sup.id}`, { quantity: qty })
      setSupplements(prev => prev.map(s => s.id === sup.id ? r.data : s))
    } catch {
      // revert local edit on error
      setEditQty(prev => ({ ...prev, [sup.id]: String(sup.quantity) }))
    }
  }

  async function createPreset() {
    if (!newPresetName.trim()) return
    try {
      const r = await api.post('/api/supplement-presets', { name: newPresetName.trim(), default_quantity: newPresetQty })
      setPresets(prev => [...prev, r.data])
      setNewPresetName(''); setNewPresetQty(1)
    } catch (e: any) {
      setError(e?.userMessage || 'Erreur')
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

  const formula = selected ? deduceFormula(selected.items) : '-'

  return (
    <div className="facturation-layout">
      {/* ===== LEFT: Reservation list ===== */}
      <div className="facturation-sidebar">
        <div className="facturation-sidebar-header">
          <Receipt className="w-5 h-5 text-violet-600" />
          <span className="font-semibold text-gray-800">Facturation</span>
        </div>
        <div className="p-3 border-b border-gray-100">
          <input
            className="input w-full"
            placeholder="Rechercher client ou date…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
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
                  {deduceFormula(res.items)} · {res.drink_formula || '-'}
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

      {/* ===== RIGHT: Editor ===== */}
      <div className="facturation-editor">
        {!selected ? (
          <div className="facturation-empty">
            <Receipt className="w-12 h-12 text-gray-300 mb-3" />
            <p className="text-gray-400">Sélectionnez une réservation pour gérer sa facture</p>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="facturation-editor-header">
              <div>
                <h2 className="text-lg font-semibold text-gray-800">{selected.client_name}</h2>
                <p className="text-sm text-gray-500">
                  {formatDate(selected.service_date)} · {selected.arrival_time}
                </p>
              </div>
              <div className="flex gap-2">
                {billingExists && (
                  <button className="btn btn-outline flex items-center gap-1.5" onClick={downloadPDF}>
                    <Download className="w-4 h-4" /> PDF Facture
                  </button>
                )}
                <button className="btn btn-primary flex items-center gap-1.5" onClick={saveBilling} disabled={loading}>
                  <Save className="w-4 h-4" /> Enregistrer
                </button>
              </div>
            </div>

            {error && <div className="mx-6 mt-3 p-2 rounded bg-red-50 text-red-700 border border-red-200 text-sm">{error}</div>}
            {saveMsg && <div className="mx-6 mt-3 p-2 rounded bg-green-50 text-green-700 border border-green-200 text-sm">{saveMsg}</div>}

            {/* Tabs */}
            <div className="facturation-tabs">
              <button
                className={`facturation-tab ${tab === 'facture' ? 'facturation-tab--active' : ''}`}
                onClick={() => setTab('facture')}
              >
                Facture
              </button>
              <button
                className={`facturation-tab ${tab === 'presets' ? 'facturation-tab--active' : ''}`}
                onClick={() => setTab('presets')}
              >
                <Tag className="w-3.5 h-3.5" /> Bibliothèque suppléments
              </button>
            </div>

            {tab === 'facture' && (
              <div className="facturation-editor-body">
                {/* Reservation summary (read-only) */}
                <section>
                  <h3 className="facturation-section-title">Résumé de la réservation</h3>
                  <div className="facturation-summary-grid">
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
                      <span className="facturation-summary-value">{selected.drink_formula || '-'}</span>
                    </div>
                  </div>
                </section>

                {/* Billing info */}
                <section>
                  <h3 className="facturation-section-title">Informations de facturation</h3>
                  <div className="billing-grid">
                    <div>
                      <label className="label">Raison sociale *</label>
                      <input className="input w-full" value={billing.company_name}
                        onChange={e => setB('company_name', e.target.value)} placeholder="Société / Nom du client" />
                    </div>
                    <div>
                      <label className="label">Adresse (ligne 1) *</label>
                      <input className="input w-full" value={billing.address_line1}
                        onChange={e => setB('address_line1', e.target.value)} placeholder="Rue et numéro" />
                    </div>
                    <div>
                      <label className="label">Adresse (ligne 2)</label>
                      <input className="input w-full" value={billing.address_line2}
                        onChange={e => setB('address_line2', e.target.value)} placeholder="Complément (facultatif)" />
                    </div>
                    <div className="billing-row-3">
                      <div>
                        <label className="label">Code postal *</label>
                        <input className="input w-full" value={billing.zip_code}
                          onChange={e => setB('zip_code', e.target.value)} />
                      </div>
                      <div>
                        <label className="label">Ville *</label>
                        <input className="input w-full" value={billing.city}
                          onChange={e => setB('city', e.target.value)} />
                      </div>
                      <div>
                        <label className="label">Pays</label>
                        <input className="input w-full" value={billing.country}
                          onChange={e => setB('country', e.target.value)} />
                      </div>
                    </div>
                    <div className="billing-row-3">
                      <div>
                        <label className="label">N° TVA</label>
                        <input className="input w-full" value={billing.vat_number}
                          onChange={e => setB('vat_number', e.target.value)} placeholder="BE…" />
                      </div>
                      <div>
                        <label className="label">Email</label>
                        <input className="input w-full" value={billing.email}
                          onChange={e => setB('email', e.target.value)} />
                      </div>
                      <div>
                        <label className="label">Téléphone</label>
                        <input className="input w-full" value={billing.phone}
                          onChange={e => setB('phone', e.target.value)} />
                      </div>
                    </div>
                    <div>
                      <label className="label">Conditions de paiement</label>
                      <input className="input w-full" value={billing.payment_terms}
                        onChange={e => setB('payment_terms', e.target.value)} placeholder="Ex: Paiement à 30 jours" />
                    </div>
                    <div>
                      <label className="label">Notes</label>
                      <textarea className="input w-full h-20" value={billing.notes}
                        onChange={e => setB('notes', e.target.value)} />
                    </div>
                  </div>
                </section>

                {/* Supplements */}
                <section>
                  <h3 className="facturation-section-title">Suppléments</h3>

                  {/* Preset quick-add buttons */}
                  {presets.length > 0 && (
                    <div className="mb-3">
                      <p className="text-xs text-gray-500 mb-2">Ajouter depuis la bibliothèque :</p>
                      <div className="flex flex-wrap gap-2">
                        {presets.map(p => (
                          <button
                            key={p.id}
                            className="facturation-preset-chip"
                            onClick={() => addSupplement(p.name, p.default_quantity)}
                          >
                            <Plus className="w-3 h-3" /> {p.name} ×{p.default_quantity}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Current supplements list */}
                  {supplements.length > 0 && (
                    <div className="facturation-sup-list mb-3">
                      {supplements.map(s => (
                        <div key={s.id} className="facturation-sup-row">
                          <span className="flex-1 text-sm text-gray-800">{s.description}</span>
                          <input
                            type="number" min={1}
                            className="input w-16 text-center text-sm"
                            value={editQty[s.id] ?? String(s.quantity)}
                            onChange={e => setEditQty(prev => ({ ...prev, [s.id]: e.target.value }))}
                            onBlur={e => {
                              const qty = Math.max(1, parseInt(e.target.value) || 1)
                              setEditQty(prev => ({ ...prev, [s.id]: String(qty) }))
                              updateSupplementQty(s, qty)
                            }}
                          />
                          <button className="btn-icon text-red-500 hover:text-red-700" onClick={() => deleteSupplement(s.id)}>
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Add custom supplement */}
                  <div className="facturation-add-sup">
                    <input
                      className="input flex-1"
                      placeholder="Description du supplément…"
                      value={newSupDesc}
                      onChange={e => setNewSupDesc(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') { addSupplement(newSupDesc, newSupQty); setNewSupDesc(''); setNewSupQty(1) } }}
                    />
                    <input
                      type="number" min={1}
                      className="input w-16 text-center"
                      value={newSupQty}
                      onChange={e => setNewSupQty(Math.max(1, parseInt(e.target.value) || 1))}
                    />
                    <button
                      className="btn btn-outline flex items-center gap-1"
                      onClick={() => { addSupplement(newSupDesc, newSupQty); setNewSupDesc(''); setNewSupQty(1) }}
                      disabled={!newSupDesc.trim()}
                    >
                      <Plus className="w-4 h-4" /> Ajouter
                    </button>
                  </div>
                </section>

                {/* Footer actions */}
                <div className="facturation-editor-footer">
                  {billingExists && (
                    <button className="btn btn-outline flex items-center gap-1.5" onClick={downloadPDF}>
                      <Download className="w-4 h-4" /> Télécharger PDF
                    </button>
                  )}
                  <button className="btn btn-primary flex items-center gap-1.5" onClick={saveBilling} disabled={loading}>
                    <Save className="w-4 h-4" /> Enregistrer la facture
                  </button>
                </div>
              </div>
            )}

            {tab === 'presets' && (
              <div className="facturation-editor-body">
                <section>
                  <h3 className="facturation-section-title">Bibliothèque de suppléments prédéfinis</h3>
                  <p className="text-sm text-gray-500 mb-4">
                    Ces suppléments apparaissent en accès rapide sur toutes les factures.
                  </p>

                  {/* Add preset */}
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

                  {/* Presets list */}
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
            )}
          </>
        )}
      </div>
    </div>
  )
}
