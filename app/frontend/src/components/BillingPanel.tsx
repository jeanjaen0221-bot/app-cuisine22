import { useCallback, useEffect, useState } from 'react'
import { Plus, Receipt, Save, Tag, Trash2 } from 'lucide-react'
import { api, fileDownload } from '../lib/api'
import type { Reservation, ReservationItem } from '../types'

// ---- Types ----
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

type Props = {
  reservationId: string
  reservation?: Reservation | null
}

// ---- Helpers ----
const EMPTY_BILLING: BillingForm = {
  company_name: '', address_line1: '', address_line2: '',
  zip_code: '', city: '', country: 'Belgique',
  vat_number: '', email: '', phone: '',
  payment_terms: 'Paiement à 30 jours', notes: '',
}

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
    return new Date(d + 'T00:00').toLocaleDateString('fr-BE', { day: '2-digit', month: 'long', year: 'numeric' })
  } catch { return d }
}

// ---- Component ----
export default function BillingPanel({ reservationId, reservation }: Props) {
  const [billing, setBilling] = useState<BillingForm>(EMPTY_BILLING)
  const [billingExists, setBillingExists] = useState(false)
  const [supplements, setSupplements] = useState<Supplement[]>([])
  const [presets, setPresets] = useState<Preset[]>([])
  const [newSupDesc, setNewSupDesc] = useState('')
  const [newSupQty, setNewSupQty] = useState(1)
  const [editQty, setEditQty] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Load data when reservationId changes
  useEffect(() => {
    if (!reservationId) return
    setLoading(true)
    setError(null)
    setSaveMsg(null)
    Promise.allSettled([
      api.get(`/api/reservations/${reservationId}/billing`),
      api.get(`/api/reservations/${reservationId}/supplements`),
    ]).then(([billRes, supRes]) => {
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
      setSupplements(supRes.status === 'fulfilled' ? supRes.value.data : [])
    }).finally(() => setLoading(false))
  }, [reservationId])

  // Load presets once
  const loadPresets = useCallback(() => {
    api.get('/api/supplement-presets').then(r => setPresets(r.data)).catch(() => {})
  }, [])
  useEffect(() => { loadPresets() }, [loadPresets])

  // Ctrl+S
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        saveBilling()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [billing, billingExists, reservationId])

  function setB<K extends keyof BillingForm>(k: K, v: string) {
    setBilling(prev => ({ ...prev, [k]: v }))
  }

  async function saveBilling() {
    if (!reservationId) return
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
        await api.put(`/api/reservations/${reservationId}/billing`, payload)
      } else {
        await api.post(`/api/reservations/${reservationId}/billing`, payload)
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

  async function addSupplement(desc: string, qty: number) {
    if (!reservationId || !desc.trim()) return
    try {
      const r = await api.post(`/api/reservations/${reservationId}/supplements`, {
        description: desc.trim(), quantity: qty, sort_order: supplements.length,
      })
      setSupplements(prev => [...prev, r.data])
    } catch (e: any) {
      setError(e?.userMessage || 'Erreur')
    }
  }

  async function deleteSupplement(supId: string) {
    try {
      await api.delete(`/api/reservations/${reservationId}/supplements/${supId}`)
      setSupplements(prev => prev.filter(s => s.id !== supId))
    } catch (e: any) {
      setError(e?.userMessage || 'Erreur')
    }
  }

  async function updateSupplementQty(sup: Supplement, qty: number) {
    try {
      const r = await api.put(`/api/reservations/${reservationId}/supplements/${sup.id}`, { quantity: qty })
      setSupplements(prev => prev.map(s => s.id === sup.id ? r.data : s))
    } catch {
      setEditQty(prev => ({ ...prev, [sup.id]: String(sup.quantity) }))
    }
  }

  const formula = reservation
    ? (reservation.menu_formula || deduceFormula(reservation.items))
    : '—'

  return (
    <div className="billing-panel-layout">

      {error && (
        <div className="mx-6 mt-4 p-2 rounded bg-red-50 text-red-700 border border-red-200 text-sm">{error}</div>
      )}
      {saveMsg && (
        <div className="mx-6 mt-4 p-2 rounded bg-green-50 text-green-700 border border-green-200 text-sm">{saveMsg}</div>
      )}
      {loading && !saveMsg && !error && (
        <div className="mx-6 mt-4 text-sm text-gray-500">Chargement…</div>
      )}

      <div className="billing-panel-body">

        {/* ── Résumé réservation ── */}
        {reservation && (
          <section>
            <h3 className="facturation-section-title">Résumé de la réservation</h3>
            <div className="facturation-summary-grid">
              <div className="facturation-summary-row">
                <span className="facturation-summary-label">Date</span>
                <span className="facturation-summary-value font-semibold">{formatDate(reservation.service_date)}</span>
              </div>
              <div className="facturation-summary-row">
                <span className="facturation-summary-label">Nombre de pax</span>
                <span className="facturation-summary-value font-semibold">{reservation.pax}</span>
              </div>
              <div className="facturation-summary-row">
                <span className="facturation-summary-label">Formule repas</span>
                <span className="facturation-summary-value">{formula}</span>
              </div>
              <div className="facturation-summary-row">
                <span className="facturation-summary-label">Formule boisson</span>
                <span className="facturation-summary-value">{reservation.drink_formula || '—'}</span>
              </div>
            </div>
          </section>
        )}

        {/* ── Informations de facturation ── */}
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

        {/* ── Suppléments ── */}
        <section>
          <h3 className="facturation-section-title">Suppléments</h3>

          {presets.length > 0 && (
            <div className="mb-3">
              <p className="text-xs text-gray-500 mb-2 flex items-center gap-1">
                <Tag className="w-3.5 h-3.5" /> Ajout rapide depuis la bibliothèque :
              </p>
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

          {supplements.length === 0 && (
            <p className="text-sm text-gray-400 mb-3">Aucun supplément ajouté.</p>
          )}

          <div className="facturation-add-sup">
            <input
              className="input flex-1"
              placeholder="Description du supplément…"
              value={newSupDesc}
              onChange={e => setNewSupDesc(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') { addSupplement(newSupDesc, newSupQty); setNewSupDesc(''); setNewSupQty(1) }
              }}
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

      </div>

      {/* ── Barre d'actions sticky ── */}
      <div className="billing-panel-footer">
        {billingExists && (
          <button className="btn btn-outline flex items-center gap-1.5" onClick={() => fileDownload(`/api/reservations/${reservationId}/invoice-pdf`)}>
            <Receipt className="w-4 h-4" /> Télécharger la facture
          </button>
        )}
        <div className="flex items-center gap-2 ml-auto">
          <button className="btn btn-primary flex items-center gap-1.5" onClick={saveBilling} disabled={loading} title="Enregistrer (Ctrl+S)">
            <Save className="w-4 h-4" /> Enregistrer
          </button>
          <span className="text-xs text-gray-400 select-none hidden sm:inline">Ctrl+S</span>
        </div>
      </div>
    </div>
  )
}
