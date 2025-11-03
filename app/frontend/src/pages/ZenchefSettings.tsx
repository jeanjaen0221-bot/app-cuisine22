import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Save, RefreshCw } from 'lucide-react'

export default function ZenchefSettings() {
  const [apiToken, setApiToken] = useState('')
  const [restaurantId, setRestaurantId] = useState('')
  const [fromDate, setFromDate] = useState(new Date().toISOString().slice(0,10))
  const [toDate, setToDate] = useState(new Date().toISOString().slice(0,10))
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [result, setResult] = useState<{count:number, created:any[]} | null>(null)

  useEffect(() => {
    api.get('/api/zenchef/settings').then(r => {
      setApiToken(r.data.api_token || '')
      setRestaurantId(r.data.restaurant_id || '')
    })
  }, [])

  async function save() {
    setSaving(true)
    try {
      await api.put('/api/zenchef/settings', { api_token: apiToken, restaurant_id: restaurantId })
    } finally {
      setSaving(false)
    }
  }

  async function syncNow() {
    setSyncing(true)
    setResult(null)
    try {
      const r = await api.post('/api/zenchef/sync', { fromDate, toDate })
      setResult({ count: r.data.count, created: r.data.created })
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="card max-w-2xl">
      <h2 className="text-xl font-semibold text-primary mb-4">Paramètres Zenchef</h2>
      <div className="space-y-4">
        <div>
          <label className="label">API Token</label>
          <input className="input w-full" value={apiToken} onChange={e=>setApiToken(e.target.value)} />
        </div>
        <div>
          <label className="label">Restaurant ID</label>
          <input className="input w-full" value={restaurantId} onChange={e=>setRestaurantId(e.target.value)} />
        </div>
        <div className="flex gap-2">
          <button className="btn flex items-center gap-2" onClick={save} disabled={saving}>{saving ? <><RefreshCw className="h-4 w-4 animate-spin"/> Sauvegarde…</> : <><Save className="h-4 w-4"/> Sauvegarder</>}</button>
        </div>
      </div>

      <h3 className="text-lg font-semibold text-primary mt-8 mb-2">Synchroniser les réservations (&gt;10 pers)</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
        <div>
          <label className="label">Du</label>
          <input type="date" className="input w-full" value={fromDate} onChange={e=>setFromDate(e.target.value)} />
        </div>
        <div>
          <label className="label">Au</label>
          <input type="date" className="input w-full" value={toDate} onChange={e=>setToDate(e.target.value)} />
        </div>
        <div>
          <button className="btn w-full flex items-center justify-center gap-2" onClick={syncNow} disabled={syncing || !apiToken || !restaurantId}>{syncing ? <><RefreshCw className="h-4 w-4 animate-spin"/> Synchronisation…</> : <><RefreshCw className="h-4 w-4"/> Synchroniser</>}</button>
        </div>
      </div>

      {result && (
        <div className="mt-6">
          <div className="label">Résultat</div>
          <div className="text-sm">{result.count} fiches créées</div>
          {result.created.length > 0 && (
            <ul className="mt-2 text-sm list-disc pl-5">
              {result.created.slice(0,10).map((c, i) => (
                <li key={i}>{c.client_name} – {c.pax} pers – {c.service_date} {c.arrival_time}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
