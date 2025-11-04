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
    <div className="card">
      <div className="flex flex-col md:flex-row gap-2 md:items-center md:justify-between">
        <div className="flex gap-2 items-center">
          <div className="relative">
            <Search className="h-4 w-4 text-gray-400 absolute left-2 top-1/2 -translate-y-1/2" />
            <input className="input pl-8" placeholder="Rechercher un client" value={q} onChange={e=>setQ(e.target.value)} />
          </div>
          <input type="date" className="input" value={date} onChange={e=>setDate(e.target.value)} />
          <button className="btn flex items-center gap-2" onClick={load}><Filter className="h-4 w-4"/> Filtrer</button>
        </div>
        <div className="flex gap-2">
          <Link to={date ? `/reservation/new?date=${encodeURIComponent(date)}` : "/reservation/new"} className="btn flex items-center gap-2"><Plus className="h-4 w-4"/> Nouvelle fiche</Link>
          <button className="btn flex items-center gap-2" onClick={() => {
            if (!date) { alert('Sélectionnez une date'); return }
            fileDownload(`/api/reservations/day/${date}/pdf`)
          }}><Printer className="h-4 w-4"/> Export PDF du jour</button>
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {rows.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            Aucune réservation trouvée
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {rows.map(r => (
              <div key={r.id} className="border rounded-lg overflow-hidden shadow-sm hover:shadow-md transition-shadow">
                <div className="p-4 border-b bg-gray-50">
                  <div className="flex justify-between items-start">
                    <h3 className="font-medium text-lg flex items-center gap-2">
                      <User className="h-5 w-5 text-gray-600" />
                      {r.client_name}
                    </h3>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      r.status === 'confirmed' ? 'bg-green-100 text-green-800' :
                      r.status === 'printed' ? 'bg-blue-100 text-blue-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {r.status === 'confirmed' ? 'Confirmée' : 
                       r.status === 'printed' ? 'Imprimée' : 'Brouillon'}
                    </span>
                  </div>
                </div>
                
                <div className="p-4">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-gray-700">
                      <CalendarDays className="h-4 w-4 text-gray-500" />
                      <span>{formatDate(r.service_date)}</span>
                    </div>
                    <div className="flex items-center gap-2 text-gray-700">
                      <Clock className="h-4 w-4 text-gray-500" />
                      <span>{formatTime(r.arrival_time)}</span>
                    </div>
                    <div className="flex items-center gap-2 text-gray-700">
                      <Users className="h-4 w-4 text-gray-500" />
                      <span>{r.pax} couvert{r.pax > 1 ? 's' : ''}</span>
                    </div>
                  </div>
                  
                  <div className="mt-4 pt-4 border-t flex justify-end gap-2">
                    <Link 
                      to={`/reservation/${r.id}`} 
                      className="btn btn-sm flex items-center gap-1"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      <span>Modifier</span>
                    </Link>
                    <button 
                      onClick={() => fileDownload(`/api/reservations/${r.id}/pdf`)}
                      className="btn btn-sm flex items-center gap-1"
                    >
                      <Printer className="h-3.5 w-3.5" />
                      <span>PDF</span>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
