import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { IncidentReport } from '../types'
import { Sparkles, Save, FileText } from 'lucide-react'

type Props = {
  initial?: IncidentReport
  onSubmit: (payload: any) => Promise<void> | void
  navActions?: any
}

const emptyText = (s: any) => (s == null ? '' : String(s))

export default function IncidentForm({ initial, onSubmit, navActions }: Props) {
  const [date, setDate] = useState('')
  const [heure, setHeure] = useState('')
  const [lieu, setLieu] = useState('')
  const [employes, setEmployes] = useState('')
  const [client, setClient] = useState('')
  const [recitBrut, setRecitBrut] = useState('')
  const [contexte, setContexte] = useState('')
  const [descriptionIncident, setDescriptionIncident] = useState('')
  const [reactionPersonnel, setReactionPersonnel] = useState('')
  const [consequences, setConsequences] = useState('')
  const [mesuresPrises, setMesuresPrises] = useState('')
  const [observations, setObservations] = useState('')
  const [gravite, setGravite] = useState<'Faible' | 'Moyen' | 'Élevé'>('Faible')

  const [saving, setSaving] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!initial) {
      const d = new Date().toISOString().slice(0, 10)
      setDate(d)
      setHeure('')
      return
    }
    setDate(emptyText(initial.date))
    setHeure(emptyText(initial.heure).slice(0, 5))
    setLieu(emptyText(initial.lieu))
    setEmployes(emptyText(initial.employes))
    setClient(emptyText(initial.client))
    setRecitBrut(emptyText(initial.recit_brut))
    setContexte(emptyText(initial.contexte))
    setDescriptionIncident(emptyText(initial.description_incident))
    setReactionPersonnel(emptyText(initial.reaction_personnel))
    setConsequences(emptyText(initial.consequences))
    setMesuresPrises(emptyText(initial.mesures_prises))
    setObservations(emptyText(initial.observations))
    setGravite((initial.gravite as any) || 'Faible')
  }, [initial])

  async function aiFill() {
    setError(null)
    if (!recitBrut.trim()) {
      setError('Le récit brut est requis pour l’assistance IA.')
      return
    }
    setAiLoading(true)
    try {
      const r = await api.post('/api/incidents/ai-fill', { recit_brut: recitBrut })
      const d = r.data || {}
      if (d.date && d.date !== 'Non précisé') setDate(d.date)
      if (d.heure && d.heure !== 'Non précisé') setHeure(String(d.heure).slice(0,5))
      if (d.lieu && d.lieu !== 'Non précisé') setLieu(d.lieu)
      if (d.employes && d.employes !== 'Non précisé') setEmployes(d.employes)
      if (d.client && d.client !== 'Non précisé') setClient(d.client)
      if (d.recit_brut && d.recit_brut !== 'Non précisé') setRecitBrut(d.recit_brut)
      if (d.contexte && d.contexte !== 'Non précisé') setContexte(d.contexte)
      if (d.description_incident && d.description_incident !== 'Non précisé') setDescriptionIncident(d.description_incident)
      if (d.reaction_personnel && d.reaction_personnel !== 'Non précisé') setReactionPersonnel(d.reaction_personnel)
      if (d.consequences && d.consequences !== 'Non précisé') setConsequences(d.consequences)
      if (d.mesures_prises && d.mesures_prises !== 'Non précisé') setMesuresPrises(d.mesures_prises)
      if (d.observations && d.observations !== 'Non précisé') setObservations(d.observations)
      if (d.gravite && (d.gravite === 'Faible' || d.gravite === 'Moyen' || d.gravite === 'Élevé')) setGravite(d.gravite)
    } catch (e: any) {
      setError(e?.userMessage || e?.response?.data?.detail || e?.message || 'Erreur lors de l’assistance IA')
    } finally {
      setAiLoading(false)
    }
  }

  async function submit(e: any) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await onSubmit({
        date,
        heure,
        lieu,
        employes,
        client,
        recit_brut: recitBrut,
        contexte,
        description_incident: descriptionIncident,
        reaction_personnel: reactionPersonnel,
        consequences,
        mesures_prises: mesuresPrises,
        observations,
        gravite,
      })
    } catch (err: any) {
      setError(err?.userMessage || err?.response?.data?.detail || err?.message || 'Erreur lors de l\'enregistrement')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="container pt-4">
      {error && (
        <div className="p-3 rounded-md bg-red-50 border border-red-200 text-red-700" style={{ marginBottom: '1rem' }}>{error}</div>
      )}

      <div className="card">
        <div className="card-header">
          <div>Rapport d'incident</div>
          <div className="flex gap-2 items-center">
            {navActions}
            {initial?.id && (
              <button className="btn btn-sm btn-outline" type="button" onClick={() => window.open(`/api/incidents/${initial.id}/pdf`, '_blank')}>
                <FileText className="w-4 h-4" /> PDF
              </button>
            )}
          </div>
        </div>

        <form onSubmit={submit}>
          <div className="card-body space-y-4">
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
              <div className="form-group">
                <label className="label">Date</label>
                <input className="input" type="date" value={date} onChange={e => setDate(e.target.value)} required />
              </div>
              <div className="form-group">
                <label className="label">Heure</label>
                <input className="input" type="time" value={heure} onChange={e => setHeure(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="label">Lieu</label>
                <input className="input" value={lieu} onChange={e => setLieu(e.target.value)} placeholder="Ex: Salle, terrasse…" />
              </div>
              <div className="form-group">
                <label className="label">Employé(s)</label>
                <input className="input" value={employes} onChange={e => setEmployes(e.target.value)} placeholder="Ex: Alice, Bob…" />
              </div>
              <div className="form-group">
                <label className="label">Client</label>
                <input className="input" value={client} onChange={e => setClient(e.target.value)} placeholder="Nom du client" />
              </div>
              <div className="form-group">
                <label className="label">Gravité</label>
                <select className="input" value={gravite} onChange={e => setGravite(e.target.value as any)}>
                  <option value="Faible">Faible</option>
                  <option value="Moyen">Moyen</option>
                  <option value="Élevé">Élevé</option>
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="label">Récit brut</label>
              <textarea className="input" style={{ minHeight: 110 }} value={recitBrut} onChange={e => setRecitBrut(e.target.value)} placeholder="Racontez librement l’incident…" />
              <div className="flex justify-end" style={{ marginTop: '0.5rem' }}>
                <button className="btn btn-sm btn-outline" type="button" onClick={aiFill} disabled={aiLoading}>
                  <Sparkles className="w-4 h-4" /> {aiLoading ? 'Analyse…' : 'Remplir avec IA'}
                </button>
              </div>
            </div>

            <div className="form-group">
              <label className="label">Contexte</label>
              <textarea className="input" style={{ minHeight: 80 }} value={contexte} onChange={e => setContexte(e.target.value)} />
            </div>

            <div className="form-group">
              <label className="label">Description de l'incident</label>
              <textarea className="input" style={{ minHeight: 90 }} value={descriptionIncident} onChange={e => setDescriptionIncident(e.target.value)} />
            </div>

            <div className="form-group">
              <label className="label">Réaction du personnel</label>
              <textarea className="input" style={{ minHeight: 80 }} value={reactionPersonnel} onChange={e => setReactionPersonnel(e.target.value)} />
            </div>

            <div className="form-group">
              <label className="label">Conséquences</label>
              <textarea className="input" style={{ minHeight: 80 }} value={consequences} onChange={e => setConsequences(e.target.value)} />
            </div>

            <div className="form-group">
              <label className="label">Mesures prises</label>
              <textarea className="input" style={{ minHeight: 80 }} value={mesuresPrises} onChange={e => setMesuresPrises(e.target.value)} />
            </div>

            <div className="form-group">
              <label className="label">Observations</label>
              <textarea className="input" style={{ minHeight: 80 }} value={observations} onChange={e => setObservations(e.target.value)} />
            </div>
          </div>

          <div className="card-footer">
            <button className="btn btn-primary" type="submit" disabled={saving}>
              <Save className="w-4 h-4" /> {saving ? 'Enregistrement…' : 'Enregistrer'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
