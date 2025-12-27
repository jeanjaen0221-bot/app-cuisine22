import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import type { Drink } from '../types'

export default function DrinksOrder() {
  const [drinks, setDrinks] = useState<Drink[]>([])
  const [q, setQ] = useState('')
  const [cat, setCat] = useState<string>('all')
  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const [unit, setUnit] = useState('')
  const [uploadCategory, setUploadCategory] = useState('')
  const [uploadUnit, setUploadUnit] = useState('')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [lastImportAdded, setLastImportAdded] = useState<number | null>(null)
  const [fileKey, setFileKey] = useState(0)
  const [counts, setCounts] = useState<Record<string, number>>(() => {
    try {
      const raw = localStorage.getItem('drinks-order')
      return raw ? JSON.parse(raw) : {}
    } catch {
      return {}
    }
  })

  async function load() {
    const res = await api.get('/api/drinks')
    setDrinks(res.data)
  }
  useEffect(() => { load() }, [])

  useEffect(() => {
    try { localStorage.setItem('drinks-order', JSON.stringify(counts)) } catch {}
  }, [counts])

  const categories = useMemo(() => {
    const s = new Set<string>()
    drinks.forEach(d => { if (d.category) s.add(d.category) })
    return Array.from(s).sort()
  }, [drinks])

  const filtered = useMemo(() => {
    const ql = q.trim().toLowerCase()
    return drinks.filter(d => {
      if (!d.active) return false
      if (cat !== 'all' && (d.category || '') !== cat) return false
      if (ql && !d.name.toLowerCase().includes(ql)) return false
      return true
    })
  }, [drinks, q, cat])

  const summary = useMemo(() => {
    let lines = 0
    let total = 0
    for (const id in counts) {
      const v = counts[id] || 0
      if (v > 0) { lines++; total += v }
    }
    return { lines, total }
  }, [counts])

  function inc(id: string, delta: number) {
    setCounts(prev => ({ ...prev, [id]: Math.max(0, (prev[id] || 0) + delta) }))
  }

  function resetAll() {
    if (!confirm('Remettre tous les compteurs à 0 ?')) return
    setCounts({})
  }

  async function quickAdd() {
    if (!name.trim()) return
    await api.post('/api/drinks', { name: name.trim(), category: category || null, unit: unit || null, active: true })
    setName(''); setCategory(''); setUnit('')
    await load()
  }

  async function handleUpload() {
    if (!uploadFile) return
    setImporting(true)
    setLastImportAdded(null)
    try {
      const fd = new FormData()
      fd.append('file', uploadFile)
      if (uploadCategory) fd.append('default_category', uploadCategory)
      if (uploadUnit) fd.append('unit', uploadUnit)
      const res = await api.post('/api/drinks/import/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      const added = Number((res.data as any)?.added ?? 0)
      setLastImportAdded(Number.isFinite(added) ? added : 0)
      setUploadFile(null)
      setFileKey(k => k + 1)
      await load()
    } catch (e: any) {
      alert(e?.userMessage || 'Import échoué')
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="text-lg font-semibold">Commande boissons</h3>
        <div className="flex items-center gap-3 text-sm text-gray-700">
          <span>Lignes: <b>{summary.lines}</b></span>
          <span>Total: <b>{summary.total}</b></span>
          <button className="btn btn-sm btn-outline" onClick={resetAll}>Tout remettre à 0</button>
        </div>
      </div>

      <div className="card-body space-y-4">
        <div className="controls-panel">
          <div className="drinks-controls">
            <input className="input" placeholder="Rechercher une boisson" value={q} onChange={e=>setQ(e.target.value)} />
            <select className="input" value={cat} onChange={e=>setCat(e.target.value)} aria-label="Filtrer par catégorie">
              <option value="all">Toutes</option>
              {categories.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="controls-divider" />
          <div className="controls-hint">Ajout rapide</div>
          <div className="drinks-grid">
            <input className="input" placeholder="Nom de la boisson" value={name} onChange={e=>setName(e.target.value)} />
            <input className="input" placeholder="Catégorie (ex: vin, bière)" value={category} onChange={e=>setCategory(e.target.value)} />
            <input className="input" placeholder="Unité (ex: bouteille, carton)" value={unit} onChange={e=>setUnit(e.target.value)} />
            <button className="btn btn-primary" onClick={quickAdd}>Ajouter</button>
          </div>
          <div className="controls-divider" />
          <div className="controls-hint">Importer un fichier (.csv, .txt)</div>
          <div className="upload-grid">
            <input key={fileKey} type="file" accept=".csv,.txt" className="input" onChange={e=>setUploadFile(e.target.files?.[0] || null)} />
            <input className="input" placeholder="Catégorie par défaut" value={uploadCategory} onChange={e=>setUploadCategory(e.target.value)} />
            <input className="input" placeholder="Unité par défaut" value={uploadUnit} onChange={e=>setUploadUnit(e.target.value)} />
            <div className="upload-actions">
              <button className="btn btn-primary" onClick={handleUpload} disabled={!uploadFile || importing}>{importing ? 'Import...' : 'Importer'}</button>
              {lastImportAdded !== null && (
                <span className="text-sm text-gray-600">Ajoutés: {lastImportAdded}</span>
              )}
            </div>
          </div>
        </div>

        <div className="drinks-table-container">
          <table className="table drinks-table">
            <thead>
              <tr>
                <th>Boisson</th>
                <th>Catégorie</th>
                <th>Unité</th>
                <th>Quantité</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(d => (
                <tr key={d.id}>
                  <td className="font-medium text-gray-900 name-cell" title={d.name}>{d.name}</td>
                  <td><span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-50 text-blue-700">{d.category || '-'}</span></td>
                  <td><span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-emerald-50 text-emerald-700">{d.unit || '-'}</span></td>
                  <td>
                    <div className="qty-group">
                      <button className="btn btn-sm btn-outline qty-btn" onClick={()=>inc(d.id, -1)}>-</button>
                      <input className="input qty-input" value={counts[d.id] || 0} onChange={e=>{
                        const v = Math.max(0, parseInt(e.target.value||'0')||0)
                        setCounts(prev => ({ ...prev, [d.id]: v }))
                      }} />
                      <button className="btn btn-sm btn-outline qty-btn" onClick={()=>inc(d.id, +1)}>+</button>
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td className="p-4 text-gray-500" colSpan={4}>Aucune boisson.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
