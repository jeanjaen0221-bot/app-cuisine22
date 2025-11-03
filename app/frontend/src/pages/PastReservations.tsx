import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fileDownload } from '../lib/api'
import { Reservation } from '../types'
import { Search, Filter, Printer, Pencil } from 'lucide-react'

export default function PastReservations() {
  const [rows, setRows] = useState<Reservation[]>([])
  const [q, setQ] = useState('')

  async function load() {
    const params: any = {}
    if (q) params.q = q
    const res = await api.get('/api/reservations/past', { params })
    setRows(res.data)
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    const t = setTimeout(() => { load() }, 300)
    return () => clearTimeout(t)
  }, [q])

  return (
    <div className="card">
      <div className="flex flex-col md:flex-row gap-2 md:items-center md:justify-between">
        <div className="flex gap-2 items-center">
          <div className="relative">
            <Search className="h-4 w-4 text-gray-400 absolute left-2 top-1/2 -translate-y-1/2" />
            <input className="input pl-8" placeholder="Rechercher un client" value={q} onChange={e=>setQ(e.target.value)} />
          </div>
          <button className="btn flex items-center gap-2" onClick={load}><Filter className="h-4 w-4"/> Filtrer</button>
        </div>
        <div className="text-sm text-gray-500">Réservations passées (date/heure antérieures)</div>
      </div>

      <div className="mt-4 overflow-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-gray-600">
              <th className="p-2">Nom du client</th>
              <th className="p-2">Date</th>
              <th className="p-2">Heure</th>
              <th className="p-2">Couverts</th>
              <th className="p-2">Statut</th>
              <th className="p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id} className="border-t">
                <td className="p-2">{r.client_name}</td>
                <td className="p-2">{r.service_date}</td>
                <td className="p-2">{r.arrival_time}</td>
                <td className="p-2">{r.pax}</td>
                <td className="p-2 capitalize">{r.status}</td>
                <td className="p-2 flex gap-2">
                  <Link className="btn flex items-center gap-2" to={`/reservation/${r.id}`}><Pencil className="h-4 w-4"/> Modifier</Link>
                  <button className="btn flex items-center gap-2" onClick={() => fileDownload(`/api/reservations/${r.id}/pdf`)}><Printer className="h-4 w-4"/> PDF</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
