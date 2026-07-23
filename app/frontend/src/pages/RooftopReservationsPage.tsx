import { FormEvent, useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, Plus, Users, X } from 'lucide-react'
import { api } from '../lib/api'
import { Reservation } from '../types'

const paymentMethods = ['Sur place', 'Facture', 'Acompte', 'Lien de paiement']
const statuses = [{ value: 'draft', label: 'Option' }, { value: 'confirmed', label: 'Confirmée' }, { value: 'printed', label: 'Terminée' }]
const dayLabel = new Intl.DateTimeFormat('fr-BE', { weekday: 'short', day: 'numeric', month: 'short' })
const iso = (date: Date) => date.toISOString().slice(0, 10)
function mondayOf(date: Date) { const result = new Date(date); result.setDate(result.getDate() - ((result.getDay() + 6) % 7)); return result }

export default function RooftopReservationsPage() {
  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()))
  const [reservations, setReservations] = useState<Reservation[]>([])
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ client_name: '', company: '', pax: 2, service_date: iso(new Date()), arrival_time: '19:00', contact: '', payment_method: 'Sur place', special_requests: '', occasion: '', status: 'draft' })
  const days = useMemo(() => Array.from({ length: 7 }, (_, index) => { const date = new Date(weekStart); date.setDate(date.getDate() + index); return date }), [weekStart])

  async function load() {
    const response = await api.get('/api/reservations/rooftop', { params: { date_from: iso(days[0]), date_to: iso(days[6]) } })
    setReservations(response.data)
  }
  useEffect(() => { void load() }, [weekStart])

  async function submit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError('')
    try {
      await api.post('/api/reservations', { ...form, is_rooftop: true, drink_formula: '', menu_formula: '', notes: '', allergens: '', final_version: false, on_invoice: form.payment_method === 'Facture', items: [] })
      setShowForm(false); setForm(value => ({ ...value, client_name: '', company: '', contact: '', special_requests: '', occasion: '' })); await load()
    } catch (err: any) { setError(err.userMessage || 'La réservation n’a pas pu être enregistrée.') } finally { setSaving(false) }
  }

  return <div className="rooftop-page container">
    <header className="rooftop-hero"><div><p className="eyebrow">Albert Rooftop</p><h1>Réservations</h1><p>Une vue claire de la semaine, sans tableur à remplir.</p></div><button className="btn btn-primary" onClick={() => setShowForm(true)}><Plus size={18} /> Nouvelle réservation</button></header>
    <section className="rooftop-toolbar card"><button className="btn btn-outline btn-icon" aria-label="Semaine précédente" onClick={() => setWeekStart(date => { const next = new Date(date); next.setDate(next.getDate() - 7); return next })}><ChevronLeft /></button><div><strong>Planning de la semaine</strong><span>{dayLabel.format(days[0])} — {dayLabel.format(days[6])}</span></div><button className="btn btn-outline btn-icon" aria-label="Semaine suivante" onClick={() => setWeekStart(date => { const next = new Date(date); next.setDate(next.getDate() + 7); return next })}><ChevronRight /></button><button className="btn btn-ghost rooftop-today" onClick={() => setWeekStart(mondayOf(new Date()))}>Aujourd’hui</button></section>
    <section className="rooftop-grid">{days.map(day => { const bookings = reservations.filter(r => r.service_date === iso(day)); return <article className="rooftop-day" key={iso(day)}><header><span>{dayLabel.format(day)}</span><b>{bookings.reduce((sum, booking) => sum + booking.pax, 0)} couverts</b></header><div className="rooftop-bookings">{bookings.length === 0 ? <button className="rooftop-empty" onClick={() => { setForm(value => ({ ...value, service_date: iso(day) })); setShowForm(true) }}>+ Ajouter</button> : bookings.map(booking => <div className={`rooftop-booking ${booking.status}`} key={booking.id}><div className="rooftop-booking-top"><b>{booking.arrival_time.slice(0, 5)} · {booking.client_name}</b><span><Users size={13} /> {booking.pax}</span></div>{booking.company && <small>{booking.company}</small>}<small>{booking.payment_method || 'Paiement à préciser'}{booking.occasion ? ` · ${booking.occasion}` : ''}</small>{booking.special_requests && <p>{booking.special_requests}</p>}</div>)}</div></article> })}</section>
    {showForm && <div className="rooftop-modal-backdrop" role="presentation"><form className="rooftop-form card" onSubmit={submit}><header><div><p className="eyebrow">Nouvelle réservation</p><h2>Rooftop</h2></div><button type="button" className="btn btn-ghost btn-icon" aria-label="Fermer" onClick={() => setShowForm(false)}><X /></button></header><div className="rooftop-form-grid"><label>Nom du client<input className="input" value={form.client_name} onChange={e => setForm({ ...form, client_name: e.target.value })} required autoFocus /></label><label>Société <input className="input" value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} /></label><label>Date<input className="input" type="date" value={form.service_date} onChange={e => setForm({ ...form, service_date: e.target.value })} required /></label><label>Arrivée<input className="input" type="time" value={form.arrival_time} onChange={e => setForm({ ...form, arrival_time: e.target.value })} required /></label><label>Couverts<input className="input" type="number" min="1" max="500" value={form.pax} onChange={e => setForm({ ...form, pax: Number(e.target.value) })} required /></label><label>Contact<input className="input" placeholder="Téléphone ou e-mail" value={form.contact} onChange={e => setForm({ ...form, contact: e.target.value })} /></label><label>Paiement<select className="input" value={form.payment_method} onChange={e => setForm({ ...form, payment_method: e.target.value })}>{paymentMethods.map(method => <option key={method}>{method}</option>)}</select></label><label>Statut<select className="input" value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}>{statuses.map(status => <option key={status.value} value={status.value}>{status.label}</option>)}</select></label><label>Occasion<input className="input" placeholder="Anniversaire, entreprise…" value={form.occasion} onChange={e => setForm({ ...form, occasion: e.target.value })} /></label><label className="rooftop-full">Demandes spéciales<textarea className="input" rows={3} placeholder="Allergies, décoration, budget, emplacement…" value={form.special_requests} onChange={e => setForm({ ...form, special_requests: e.target.value })} /></label></div>{error && <p className="auth-error">{error}</p>}<footer><button type="button" className="btn btn-outline" onClick={() => setShowForm(false)}>Annuler</button><button className="btn btn-primary" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer la réservation'}</button></footer></form></div>}
  </div>
}
