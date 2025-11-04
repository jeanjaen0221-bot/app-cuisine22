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
    <div className="space-y-6">
      <div className="card">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <input className="input" placeholder="Rechercher un client" value={q} onChange={e=>setQ(e.target.value)} />
            <button className="btn btn-sm" onClick={load}><Filter className="h-4 w-4"/> Filtrer</button>
          </div>
          <div className="text-sm text-gray-500">Réservations passées</div>
        </div>
      </div>

      <div className="card">
        <div className="card-body overflow-auto">
          <table className="table">
            <thead>
              <tr>
                <th>Nom du client</th>
                <th>Date</th>
                <th>Heure</th>
                <th>Couverts</th>
                <th>Statut</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id}>
                  <td>{r.client_name}</td>
                  <td>{r.service_date}</td>
                  <td>{r.arrival_time}</td>
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
                    <div className="flex items-center gap-2">
                      <Link className="btn btn-sm" to={`/reservation/${r.id}`}><Pencil className="h-4 w-4"/> Modifier</Link>
                      <button className="btn btn-sm" onClick={() => fileDownload(`/api/reservations/${r.id}/pdf`)}><Printer className="h-4 w-4"/> PDF</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
