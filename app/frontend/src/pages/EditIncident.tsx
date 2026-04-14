import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { IncidentReport } from '../types'
import IncidentForm from '../components/IncidentForm'
import { ArrowLeft } from 'lucide-react'

export default function EditIncident() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [data, setData] = useState<IncidentReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
  const isExisting = !!id && id !== 'new' && uuidRegex.test(id)

  useEffect(() => {
    if (!isExisting) {
      const params = new URLSearchParams(location.search)
      const d = params.get('date') || new Date().toISOString().slice(0, 10)
      setData({
        id: '' as any,
        date: d,
        heure: '',
        lieu: '',
        employes: '',
        client: '',
        recit_brut: '',
        contexte: '',
        description_incident: '',
        reaction_personnel: '',
        consequences: '',
        mesures_prises: '',
        observations: '',
        gravite: 'Faible',
        created_at: '' as any,
        updated_at: '' as any,
      } as IncidentReport)
      return
    }

    setLoading(true)
    setData(null)
    setError(null)
    api.get(`/api/incidents/${id}`)
      .then(r => setData(r.data))
      .catch((e: any) => setError(e?.userMessage || e?.response?.data?.detail || e?.message || 'Erreur de chargement'))
      .finally(() => setLoading(false))
  }, [id, isExisting, location.search])

  async function save(payload: any) {
    setError(null)
    try {
      if (id && id !== 'new') {
        await api.put(`/api/incidents/${id}`, payload)
        navigate('/incidents')
      } else {
        const res = await api.post('/api/incidents', payload)
        navigate(`/incident/${res.data.id}`)
      }
    } catch (e: any) {
      setError(e?.userMessage || e?.response?.data?.detail || e?.message || 'Erreur lors de l\'enregistrement')
    }
  }

  const navActions = (
    <button className="btn btn-sm btn-outline" onClick={() => navigate(-1)} type="button">
      <ArrowLeft className="w-4 h-4" /> Retour
    </button>
  )

  return (
    <div>
      {error && (
        <div className="container pt-4">
          <div className="p-3 rounded-md bg-red-50 border border-red-200 text-red-700">{error}</div>
        </div>
      )}
      {(isExisting && (loading || !data)) ? (
        <div className="container pt-6">
          <div className="card"><div className="card-body text-gray-600">Chargement…</div></div>
        </div>
      ) : (
        <div key={(data && (data as any).id) || (!isExisting ? 'new' : id)}>
          <IncidentForm initial={data || undefined} onSubmit={save} navActions={navActions} />
        </div>
      )}
    </div>
  )
}
