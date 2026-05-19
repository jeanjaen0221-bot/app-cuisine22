import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, fileDownload } from '../lib/api'
import { Reservation } from '../types'
import { Search, Printer, Pencil } from 'lucide-react'

type AllergenMeta = { key: string; label: string; icon_url?: string }

const formatDate = (s: string) => {
  if (!s) return ''
  return new Date(s).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}
const formatTime = (s: string) => (s || '').slice(0, 5)

const allergenFallback: Record<string, string> = {
  gl: 'Gluten', la: 'Lait', oe: 'Oeufs', ar: 'Arachide', so: 'Soja',
  fr: 'Fruits à coque', se: 'Sésame', su: 'Sulfites', po: 'Poisson',
  cr: 'Crustacés', mo: 'Mollusques', ce: 'Céleri', lu: 'Lupin', mu: 'Moutarde', ai: 'Ail',
}

export default function PastReservations() {
  const [rows, setRows] = useState<Reservation[]>([])
  const [q, setQ] = useState('')
  const [allergenMeta, setAllergenMeta] = useState<Record<string, AllergenMeta>>({})
  const navigate = useNavigate()

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
  useEffect(() => {
    api.get('/api/allergens').then(r => {
      const map: Record<string, AllergenMeta> = {}
      for (const a of (Array.isArray(r.data) ? r.data : [])) {
        if (a?.key) map[a.key] = { key: a.key, label: a.label || a.key, icon_url: a.icon_url }
      }
      setAllergenMeta(map)
    }).catch(() => {})
  }, [])

  const friendlyAllergen = (key: string) =>
    allergenMeta[key]?.label || allergenFallback[key] || key

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (!s) return rows
    return rows.filter(r => r.client_name.toLowerCase().includes(s))
  }, [rows, q])

  return (
    <div className="space-y-4">
      <div className="card card-static">
        <div className="card-header">
          <h2 className="text-base font-semibold">Réservations passées
            <span className="ml-2 text-sm font-normal text-gray-400">({filtered.length})</span>
          </h2>
          <div className="relative">
            <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
            <input
              className="input pl-8 w-56"
              placeholder="Rechercher un client…"
              value={q}
              onChange={e => setQ(e.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-body overflow-auto p-0">
          <table className="table w-full">
            <thead>
              <tr>
                <th>Client</th>
                <th>Date</th>
                <th>Heure</th>
                <th>Couverts</th>
                <th>Statut</th>
                <th>Allergènes</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={7} className="p-6 text-center text-gray-500">Aucune réservation trouvée</td></tr>
              )}
              {filtered.map(r => {
                const allergenKeys = r.allergens ? r.allergens.split(',').map(s => s.trim()).filter(Boolean) : []
                return (
                  <tr
                    key={r.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/reservation/${r.id}`)}
                  >
                    <td className="capitalize font-medium">{r.client_name}</td>
                    <td>{formatDate(r.service_date)}</td>
                    <td>{formatTime(r.arrival_time)}</td>
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
                      {allergenKeys.length === 0
                        ? <span className="text-gray-400 text-xs">—</span>
                        : <div className="flex flex-wrap gap-1">
                            {allergenKeys.map(a => (
                              <span key={a} className="inline-block bg-red-50 text-red-700 text-xs px-1.5 py-0.5 rounded">
                                {friendlyAllergen(a)}
                              </span>
                            ))}
                          </div>
                      }
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      <div className="flex justify-end gap-2">
                        <button
                          className="btn btn-sm btn-primary"
                          onClick={e => { e.stopPropagation(); navigate(`/reservation/${r.id}`) }}
                        ><Pencil className="h-3.5 w-3.5" /> Modifier</button>
                        <button
                          className="btn btn-sm btn-outline"
                          title="Télécharger la fiche PDF"
                          onClick={e => { e.stopPropagation(); fileDownload(`/api/reservations/${r.id}/pdf`) }}
                        ><Printer className="h-3.5 w-3.5" /></button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
