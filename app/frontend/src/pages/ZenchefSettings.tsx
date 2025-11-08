import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { Save, RefreshCw, Upload, Trash2, Image as ImageIcon, Check } from 'lucide-react'
import type { AllergenDef } from '../types'

export default function ZenchefSettings() {
  const [apiToken, setApiToken] = useState('')
  const [restaurantId, setRestaurantId] = useState('')
  const [fromDate, setFromDate] = useState(new Date().toISOString().slice(0,10))
  const [toDate, setToDate] = useState(new Date().toISOString().slice(0,10))
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [result, setResult] = useState<{count:number, created:any[]} | null>(null)

  // Allergens state
  const [allergens, setAllergens] = useState<AllergenDef[]>([])
  const [newKey, setNewKey] = useState('')
  const [newLabel, setNewLabel] = useState('')
  const [savingAllergen, setSavingAllergen] = useState<string | null>(null)
  const fileInputs = useRef<Record<string, HTMLInputElement | null>>({})

  // helpers defined before usage to avoid TS scope/hoist warnings
  async function fetchAllergens() {
    const r = await api.get('/api/allergens')
    setAllergens(r.data)
  }

  useEffect(() => {
    api.get('/api/zenchef/settings').then(r => {
      setApiToken(r.data.api_token || '')
      setRestaurantId(r.data.restaurant_id || '')
    })
    fetchAllergens()
  }, [])

  async function save() {
    setSaving(true)
    try {
      await api.put('/api/zenchef/settings', { api_token: apiToken, restaurant_id: restaurantId })
    } finally {
      setSaving(false)
    }

  

  async function upsertAllergen(key: string, label: string) {
    setSavingAllergen(key)
    try {
      await api.post('/api/allergens', { key, label })
      await fetchAllergens()
    } finally {
      setSavingAllergen(null)
    }
  }

  async function onAdd() {
    const key = newKey.trim().toLowerCase()
    const label = newLabel.trim()
    if (!key || !label) return
    await upsertAllergen(key, label)
    setNewKey(''); setNewLabel('')
  }

  async function uploadIcon(key: string, file: File) {
    const fd = new FormData()
    fd.append('file', file)
    await api.post(`/api/allergens/${encodeURIComponent(key)}/icon`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    await fetchAllergens()
  }

  async function deleteIcon(key: string) {
    if (!confirm('Supprimer le logo de cet allergène ?')) return
    await api.delete(`/api/allergens/${encodeURIComponent(key)}/icon`)
    await fetchAllergens()
  }

  async function deleteAllergen(key: string) {
    if (!confirm('Supprimer cet allergène de la liste ?')) return
    await api.delete(`/api/allergens/${encodeURIComponent(key)}`)
    await fetchAllergens()
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
    <div className="space-y-8 max-w-4xl">
      <div className="card">
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

      {/* Allergens management */}
      <div className="card">
        <h2 className="text-xl font-semibold text-primary mb-4">Allergènes</h2>
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
            <div>
              <label className="label">Clé (ex: gluten)</label>
              <input className="input w-full" value={newKey} onChange={e=>setNewKey(e.target.value)} placeholder="clé ascii (a-z, 0-9, _ -)" />
            </div>
            <div>
              <label className="label">Libellé</label>
              <input className="input w-full" value={newLabel} onChange={e=>setNewLabel(e.target.value)} placeholder="Libellé lisible" />
            </div>
            <div>
              <button className="btn w-full flex items-center justify-center gap-2" onClick={onAdd}><Check className="h-4 w-4"/> Ajouter / Mettre à jour</button>
            </div>
          </div>

          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Logo</th>
                  <th>Clé</th>
                  <th>Libellé</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {allergens.map(al => (
                  <tr key={al.key}>
                    <td>
                      {al.has_icon ? (
                        <img src={`${al.icon_url}?t=${Date.now()}`} alt={al.label} className="h-8 w-8 object-contain" />
                      ) : (
                        <div className="h-8 w-8 flex items-center justify-center rounded border text-gray-400"><ImageIcon className="h-4 w-4"/></div>
                      )}
                    </td>
                    <td className="font-mono text-sm">{al.key}</td>
                    <td>
                      <div className="flex items-center gap-2">
                        <input className="input input-sm" defaultValue={al.label} onBlur={(e)=>{ const v=e.target.value.trim(); if (v && v!==al.label) upsertAllergen(al.key, v) }} />
                        {savingAllergen===al.key && <RefreshCw className="h-4 w-4 animate-spin text-gray-500"/>}
                      </div>
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-2 items-center">
                        <input type="file" accept="image/png" className="hidden" ref={el => { if (fileInputs.current) fileInputs.current[al.key]=el }} onChange={(e)=>{ const f=e.target.files?.[0]; if (f) uploadIcon(al.key, f).finally(()=>{ if (fileInputs.current[al.key]) fileInputs.current[al.key]!.value=''; }) }} />
                        <button className="btn btn-sm btn-outline" onClick={()=>fileInputs.current[al.key]?.click()}><Upload className="h-4 w-4"/> Logo PNG</button>
                        {al.has_icon && <button className="btn btn-sm btn-outline" onClick={()=>deleteIcon(al.key)}><Trash2 className="h-4 w-4"/> Supprimer logo</button>}
                        <button className="btn btn-sm btn-danger" onClick={()=>deleteAllergen(al.key)}><Trash2 className="h-4 w-4"/> Supprimer</button>
                      </div>
                    </td>
                  </tr>
                ))}
                {allergens.length===0 && (
                  <tr><td colSpan={4} className="p-3 text-gray-600">Aucun allergène. Ajoutez-en ci-dessus.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
