import { useLocation, useNavigate, useParams } from 'react-router-dom'
import ReservationForm from '../components/ReservationForm'
import { useEffect, useState } from 'react'
import { api, fileDownload } from '../lib/api'
import { Reservation } from '../types'

export default function EditReservation() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [data, setData] = useState<Reservation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
  const isExisting = !!id && id !== 'new' && uuidRegex.test(id)

  useEffect(() => {
    // If not a valid UUID (including 'new' or missing/garbled like 'nov'), treat as new and prefill immediately
    if (!isExisting) {
      const params = new URLSearchParams(location.search)
      const d = params.get('date') || new Date().toISOString().slice(0,10)
      setData({
        id: '' as any,
        client_name: '',
        pax: 2,
        service_date: d,
        arrival_time: '',
        drink_formula: 'sans alcool',
        notes: '',
        status: 'draft',
        final_version: false,
        allergens: '',
        created_at: '' as any,
        updated_at: '' as any,
        items: []
      } as Reservation)
      return
    }
    // Existing reservation: we have a valid UUID id
    setLoading(true)
    setData(null)
    setError(null)
    api.get(`/api/reservations/${id}`)
      .then(r=> setData(r.data))
      .catch((e:any)=> setError(e?.userMessage || e?.response?.data?.detail || e?.message || 'Erreur de chargement'))
      .finally(()=> setLoading(false))
  }, [id, isExisting, location.search])

  async function save(payload: any) {
    setError(null)
    try {
      if (id && id !== 'new') {
        await api.put(`/api/reservations/${id}`, payload)
        navigate('/')
      } else {
        const res = await api.post('/api/reservations', payload)
        navigate(`/reservation/${res.data.id}`)
      }
    } catch (e: any) {
      setError(e?.userMessage || e?.response?.data?.detail || e?.message || 'Erreur lors de l\'enregistrement')
    }
  }

  async function duplicate() {
    if (!id || id === 'new') return
    setError(null)
    try {
      const res = await api.post(`/api/reservations/${id}/duplicate`)
      navigate(`/reservation/${res.data.id}`)
    } catch (e: any) {
      setError(e?.userMessage || e?.response?.data?.detail || e?.message || 'Erreur lors du doublon')
    }
  }

  return (
    <div className="container space-y-4">
      {error && (
        <div className="p-3 rounded-md bg-red-50 border border-red-200 text-red-700">{error}</div>
      )}
      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-medium">{id && id !== 'new' ? 'Modifier la réservation' : 'Nouvelle réservation'}</h2>
          <div className="flex items-center gap-2">
            <button className="btn" onClick={()=>navigate(-1)}>Retour</button>
            {id && id !== 'new' && (
              <>
                <button className="btn" onClick={duplicate}>Dupliquer</button>
                <button className="btn" onClick={()=>fileDownload(`/api/reservations/${id}/pdf`)}>PDF</button>
              </>
            )}
          </div>
        </div>
      </div>
      {(isExisting && (loading || !data)) ? (
        <div className="card"><div className="card-body text-gray-600">Chargement…</div></div>
      ) : (
        <div key={(data && (data as any).id) || (!isExisting ? 'new' : id)}>
          <ReservationForm initial={data || undefined} onSubmit={save} />
        </div>
      )}
    </div>
  )
}
