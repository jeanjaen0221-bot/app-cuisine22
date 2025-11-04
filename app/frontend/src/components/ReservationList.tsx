import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fileDownload } from '../lib/api'
import { Reservation } from '../types'
import { Plus, Printer, Pencil, Filter, Search, User, CalendarDays, Clock, Users } from 'lucide-react'

// Fonction pour formater la date au format français
const formatDate = (dateString: string) => {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  });
};

// Fonction pour formater l'heure
const formatTime = (timeString: string) => {
  if (!timeString) return '';
  const [hours, minutes] = timeString.split(':');
  return `${hours}:${minutes}`;
};

export default function ReservationList() {
  const [rows, setRows] = useState<Reservation[]>([])
  const [q, setQ] = useState('')
  const [date, setDate] = useState<string>('')

  async function load() {
    const params: any = {}
    if (q) params.q = q
    // Fetch only upcoming on server; apply date filter client-side
    const res = await api.get('/api/reservations/upcoming', { params })
    const all: Reservation[] = res.data
    const filtered = date ? all.filter(r => String(r.service_date).slice(0,10) === date) : all
    setRows(filtered)
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    const t = setTimeout(() => { load() }, 300)
    return () => clearTimeout(t)
  }, [q, date])

  return (
    <div className="container space-y-6">
      {/* Barre de filtres */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <input className="input" placeholder="Rechercher un client" value={q} onChange={e=>setQ(e.target.value)} />
            <input type="date" className="input" value={date} onChange={e=>setDate(e.target.value)} />
            <button className="btn" onClick={load}><Filter className="h-4 w-4"/> Filtrer</button>
          </div>
          <div className="flex items-center gap-2">
            <Link to={date ? `/reservation/new?date=${encodeURIComponent(date)}` : "/reservation/new"} className="btn"><Plus className="h-4 w-4"/> Nouvelle fiche</Link>
            <button className="btn" onClick={() => { if (!date) { alert('Sélectionnez une date'); return } fileDownload(`/api/reservations/day/${date}/pdf`) }}><Printer className="h-4 w-4"/> Export PDF du jour</button>
          </div>
        </div>
      </div>

      {/* Grille des réservations */}
      {rows.length === 0 ? (
        <div className="card">
          <div className="text-center p-4 text-gray-700">Aucune réservation trouvée</div>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-6">
          {rows.map(r => (
            <div key={r.id} className="card card-hoverable">
              <div className="card-header">
                <h3 className="text-lg font-medium flex items-center gap-2">
                  <User className="w-4 h-4 text-gray-600" />
                  {r.client_name}
                </h3>
                <span className={`status-badge ${
                  r.status === 'confirmed' ? 'is-confirmed' :
                  r.status === 'printed' ? 'is-printed' :
                  'is-draft'
                }`}>
                  {r.status === 'confirmed' ? 'Confirmée' : r.status === 'printed' ? 'Imprimée' : 'Brouillon'}
                </span>
              </div>
              <div className="card-body">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-gray-700">
                    <CalendarDays className="w-4 h-4 text-gray-500" />
                    <span>{formatDate(r.service_date)}</span>
                  </div>
                  <div className="flex items-center gap-2 text-gray-700">
                    <Clock className="w-4 h-4 text-gray-500" />
                    <span>{formatTime(r.arrival_time)}</span>
                  </div>
                  <div className="flex items-center gap-2 text-gray-700">
                    <Users className="w-4 h-4 text-gray-500" />
                    <span>{r.pax} couvert{r.pax > 1 ? 's' : ''}</span>
                  </div>
                </div>
              </div>
              <div className="card-footer">
                <div className="flex items-center gap-2">
                  <Link to={`/reservation/${r.id}`} className="btn btn-sm"><Pencil className="w-4 h-4"/> Modifier</Link>
                  <button onClick={() => fileDownload(`/api/reservations/${r.id}/pdf`)} className="btn btn-sm"><Printer className="w-4 h-4"/> PDF</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
