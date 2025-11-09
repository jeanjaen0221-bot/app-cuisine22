import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Save, RefreshCw, Plus, Upload, Trash2, Image } from 'lucide-react'

export default function ZenchefSettings() {
  const [apiToken, setApiToken] = useState('')
  const [restaurantId, setRestaurantId] = useState('')
  const [fromDate, setFromDate] = useState(new Date().toISOString().slice(0,10))
  const [toDate, setToDate] = useState(new Date().toISOString().slice(0,10))
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [result, setResult] = useState<{count:number, created:any[]} | null>(null)
  const [allergens, setAllergens] = useState<Array<{key:string,label:string,has_icon:boolean,icon_url?:string}>>([])
  const [loadingAllergens, setLoadingAllergens] = useState(false)
  const [newKey, setNewKey] = useState('')
  const [newLabel, setNewLabel] = useState('')

  useEffect(() => {
    api.get('/api/zenchef/settings').then(r => {
      setApiToken(r.data.api_token || '')
      setRestaurantId(r.data.restaurant_id || '')
    })
    loadAllergens()
  }, [])

  async function save() {
    setSaving(true)
    try {
      await api.put('/api/zenchef/settings', { api_token: apiToken, restaurant_id: restaurantId })
    } finally {
      setSaving(false)
    }

  async function loadAllergens() {
    setLoadingAllergens(true)
    try {
      const r = await api.get('/api/allergens')
      setAllergens(r.data)
    } finally {
      setLoadingAllergens(false)
    }
  }

  async function upsertAllergen(key: string, label: string) {
    await api.put(`/api/allergens/${encodeURIComponent(key)}`, { label })
    await loadAllergens()
  }

  async function uploadIcon(key: string, file: File) {
    const fd = new FormData()
    fd.append('file', file)
    await api.post(`/api/allergens/${encodeURIComponent(key)}/icon`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    await loadAllergens()
  }

  async function addNew() {
    if (!newKey || !newLabel) return
    await upsertAllergen(newKey.trim(), newLabel.trim())
    setNewKey(''); setNewLabel('')
  }

  async function removeAllergen(key: string) {
    if (!confirm(`Supprimer l'allergène "${key}" ?`)) return
    await api.delete(`/api/allergens/${encodeURIComponent(key)}`)
    await loadAllergens()
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
    <div className="space-y-8">
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
      </div>

      <div className="card max-w-3xl">
        <h3 className="text-lg font-semibold text-primary mb-2">Synchroniser les réservations (&gt;10 pers)</h3>
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
      </div>

      {result && (
        <div className="card max-w-3xl">
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

      <div className="card max-w-4xl">
        <h2 className="text-xl font-semibold text-primary mb-4">Allergènes</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
          <div>
            <label className="label">Clé</label>
            <input className="input w-full" placeholder="ex: gluten" value={newKey} onChange={e=>setNewKey(e.target.value)} />
          </div>
          <div>
            <label className="label">Libellé</label>
            <input className="input w-full" placeholder="ex: Gluten" value={newLabel} onChange={e=>setNewLabel(e.target.value)} />
          </div>
          <div>
            <button className="btn w-full flex items-center justify-center gap-2" onClick={addNew} disabled={!newKey || !newLabel}><Plus className="h-4 w-4"/> Ajouter / Mettre à jour</button>
          </div>
        </div>

        <div className="table-container mt-4">
          <table className="table">
            <thead>
              <tr>
                <th>Icône</th>
                <th>Clé</th>
                <th>Libellé</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loadingAllergens && (
                <tr><td className="p-3 text-gray-500" colSpan={4}>Chargement…</td></tr>
              )}
              {!loadingAllergens && allergens.map(a => (
                <tr key={a.key}>
                  <td>
                    <div className="flex items-center gap-2">
                      {a.has_icon ? (
                        <img src={a.icon_url} alt={a.label} className="h-6 w-6 object-contain" />
                      ) : (
                        <span className="text-xs text-gray-500 inline-flex items-center gap-1"><Image className="w-4 h-4"/>Aucune</span>
                      )}
                      <label className="btn btn-sm btn-outline inline-flex items-center gap-2 cursor-pointer">
                        <Upload className="w-4 h-4"/> Icône
                        <input type="file" accept="image/png" className="hidden" onChange={e=>{ const f=e.target.files?.[0]; if(f) uploadIcon(a.key, f) }} />
                      </label>
                    </div>
                  </td>
                  <td className="font-mono text-sm">{a.key}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <input className="input" defaultValue={a.label} onBlur={e=>{ const v=e.target.value.trim(); if(v && v!==a.label) upsertAllergen(a.key, v) }} />
                    </div>
                  </td>
                  <td className="actions-cell">
                    <button className="btn btn-sm btn-outline inline-flex items-center gap-1" onClick={()=>upsertAllergen(a.key, a.label)}><Save className="w-4 h-4"/> Sauver</button>
                    <button className="btn btn-sm btn-outline inline-flex items-center gap-1" onClick={()=>removeAllergen(a.key)}><Trash2 className="w-4 h-4"/> Supprimer</button>
                  </td>
                </tr>
              ))}
              {!loadingAllergens && allergens.length===0 && (
                <tr><td className="p-3 text-gray-500" colSpan={4}>Aucun allergène</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
