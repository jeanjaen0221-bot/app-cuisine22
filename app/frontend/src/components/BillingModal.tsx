import { useEffect, useState } from 'react'
import { api, fileDownload } from '../lib/api'

export type BillingInfo = {
  reservation_id: string
  company_name: string
  address_line1: string
  address_line2?: string
  zip_code: string
  city: string
  country?: string
  vat_number?: string
  email?: string
  phone?: string
  payment_terms?: string
  notes?: string
  created_at?: string
  updated_at?: string
}

type Props = {
  reservationId: string
  open: boolean
  onClose: () => void
}

export default function BillingModal({ reservationId, open, onClose }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [exists, setExists] = useState(false)
  const [form, setForm] = useState<BillingInfo>({
    reservation_id: reservationId,
    company_name: '',
    address_line1: '',
    address_line2: '',
    zip_code: '',
    city: '',
    country: 'Belgique',
    vat_number: '',
    email: '',
    phone: '',
    payment_terms: 'Paiement à 30 jours',
    notes: ''
  })

  useEffect(() => {
    if (!open || !reservationId) return
    setLoading(true)
    setError(null)
    api.get(`/api/reservations/${reservationId}/billing`)
      .then(r => { setForm({ ...form, ...r.data }); setExists(true) })
      .catch(() => { setExists(false) })
      .finally(()=> setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, reservationId])

  function set<K extends keyof BillingInfo>(key: K, val: BillingInfo[K]) {
    setForm(prev => ({ ...prev, [key]: val }))
  }

  async function save() {
    setError(null)
    setLoading(true)
    try {
      const payload = {
        company_name: form.company_name.trim(),
        address_line1: form.address_line1.trim(),
        address_line2: (form.address_line2||'').trim() || undefined,
        zip_code: form.zip_code.trim(),
        city: form.city.trim(),
        country: (form.country||'').trim() || undefined,
        vat_number: (form.vat_number||'').trim() || undefined,
        email: (form.email||'').trim() || undefined,
        phone: (form.phone||'').trim() || undefined,
        payment_terms: (form.payment_terms||'').trim() || undefined,
        notes: (form.notes||'').trim() || undefined,
      }
      if (exists) await api.put(`/api/reservations/${reservationId}/billing`, payload)
      else await api.post(`/api/reservations/${reservationId}/billing`, payload)
      setExists(true)
      onClose()
    } catch (e: any) {
      setError(e?.userMessage || 'Erreur lors de la sauvegarde')
    } finally {
      setLoading(false)
    }
  }

  function downloadInvoice() {
    if (!reservationId) return
    fileDownload(`/api/reservations/${reservationId}/invoice-pdf`)
  }

  if (!open) return null

  return (
    <div className="modal-overlay">
      <div className="card modal-card">
        <div className="card-header">
          <h3 className="text-lg font-semibold">Facturation</h3>
          <div className="flex items-center gap-2">
            {exists && (
              <button className="btn btn-outline" onClick={downloadInvoice}>PDF Facture</button>
            )}
            <button className="btn" onClick={onClose}>Fermer</button>
          </div>
        </div>
        <div className="card-body space-y-3">
          {error && <div className="p-2 rounded bg-red-50 text-red-700 border border-red-200 text-sm">{error}</div>}
          {loading && <div className="text-gray-600 text-sm">Chargement…</div>}
          <div className="grid grid-cols-12 gap-2">
            <div className="col-span-12">
              <label className="label">Raison sociale</label>
              <input className="input w-full" value={form.company_name} onChange={e=>set('company_name', e.target.value)} placeholder="Société / Nom du client"/>
            </div>
            <div className="col-span-12">
              <label className="label">Adresse (ligne 1)</label>
              <input className="input w-full" value={form.address_line1} onChange={e=>set('address_line1', e.target.value)} placeholder="Rue et numéro"/>
            </div>
            <div className="col-span-12">
              <label className="label">Adresse (ligne 2)</label>
              <input className="input w-full" value={form.address_line2||''} onChange={e=>set('address_line2', e.target.value)} placeholder="Complément (facultatif)"/>
            </div>
            <div className="col-span-6 md:col-span-3">
              <label className="label">Code postal</label>
              <input className="input w-full" value={form.zip_code} onChange={e=>set('zip_code', e.target.value)} />
            </div>
            <div className="col-span-6 md:col-span-5">
              <label className="label">Ville</label>
              <input className="input w-full" value={form.city} onChange={e=>set('city', e.target.value)} />
            </div>
            <div className="col-span-12 md:col-span-4">
              <label className="label">Pays</label>
              <input className="input w-full" value={form.country||''} onChange={e=>set('country', e.target.value)} />
            </div>
            <div className="col-span-12 md:col-span-4">
              <label className="label">N° TVA</label>
              <input className="input w-full" value={form.vat_number||''} onChange={e=>set('vat_number', e.target.value)} placeholder="BE..., FR..., etc."/>
            </div>
            <div className="col-span-12 md:col-span-4">
              <label className="label">Email</label>
              <input className="input w-full" value={form.email||''} onChange={e=>set('email', e.target.value)} />
            </div>
            <div className="col-span-12 md:col-span-4">
              <label className="label">Téléphone</label>
              <input className="input w-full" value={form.phone||''} onChange={e=>set('phone', e.target.value)} />
            </div>
            <div className="col-span-12">
              <label className="label">Conditions de paiement</label>
              <input className="input w-full" value={form.payment_terms||''} onChange={e=>set('payment_terms', e.target.value)} placeholder="Ex: Paiement à 30 jours"/>
            </div>
            <div className="col-span-12">
              <label className="label">Notes</label>
              <textarea className="input w-full h-24" value={form.notes||''} onChange={e=>set('notes', e.target.value)} />
            </div>
          </div>
        </div>
        <div className="card-footer flex items-center justify-end gap-2">
          {exists && <button className="btn btn-outline" onClick={downloadInvoice}>PDF Facture</button>}
          <button className="btn btn-primary" onClick={save} disabled={loading}>Enregistrer</button>
        </div>
      </div>
    </div>
  )
}
