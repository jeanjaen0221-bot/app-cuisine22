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
  const [editingId, setEditingId] = useState<string | null>(null)
  const [eName, setEName] = useState('')
  const [eCategory, setECategory] = useState('')
  const [eUnit, setEUnit] = useState('')
  const [eActive, setEActive] = useState(true)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bulkCategory, setBulkCategory] = useState('')
  const [bulkUnit, setBulkUnit] = useState('')
  const [bulkActive, setBulkActive] = useState('')
  const [sortBy, setSortBy] = useState<'name'|'category'|'unit'|'active'|'qty'>('name')
  const [sortDir, setSortDir] = useState<'asc'|'desc'>('asc')
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

  const unitsList = useMemo(() => {
    const s = new Set<string>()
    drinks.forEach(d => { if (d.unit) s.add(d.unit) })
    return Array.from(s).sort()
  }, [drinks])

  const collator = useMemo(() => new Intl.Collator('fr', { sensitivity: 'base' }), [])

  const filtered = useMemo(() => {
    const ql = q.trim().toLowerCase()
    return drinks.filter(d => {
      if (!d.active) return false
      if (cat !== 'all' && (d.category || '') !== cat) return false
      if (ql && !d.name.toLowerCase().includes(ql)) return false
      return true
    })
  }, [drinks, q, cat])

  const sorted = useMemo(() => {
    const arr = [...filtered]
    arr.sort((a, b) => {
      let cmp = 0
      if (sortBy === 'name') {
        cmp = collator.compare(a.name, b.name)
      } else if (sortBy === 'category') {
        cmp = collator.compare(a.category || '', b.category || '')
      } else if (sortBy === 'unit') {
        cmp = collator.compare(a.unit || '', b.unit || '')
      } else if (sortBy === 'active') {
        cmp = (a.active ? 1 : 0) - (b.active ? 1 : 0)
      } else if (sortBy === 'qty') {
        const qa = counts[a.id] || 0
        const qb = counts[b.id] || 0
        cmp = qa - qb
      }
      if (cmp === 0) cmp = collator.compare(a.name, b.name)
      return sortDir === 'asc' ? cmp : -cmp
    })
    return arr
  }, [filtered, counts, sortBy, sortDir, collator])

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

  async function removeDrink(id: string) {
    if (!confirm('Supprimer cette boisson ?')) return
    await api.delete(`/api/drinks/${id}`)
    setCounts(prev => {
      const next = { ...prev }
      delete next[id]
      return next
    })
    await load()
  }

  function startEdit(d: Drink) {
    setEditingId(d.id)
    setEName(d.name)
    setECategory(d.category || '')
    setEUnit(d.unit || '')
    setEActive(!!d.active)
  }

  function cancelEdit() {
    setEditingId(null)
  }

  async function saveEdit(id: string) {
    const payload: any = {
      name: eName.trim(),
      category: eCategory.trim() || null,
      unit: eUnit.trim() || null,
      active: !!eActive,
    }
    await api.put(`/api/drinks/${id}`, payload)
    setEditingId(null)
    await load()
  }

  function toggleSelect(id: string) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  function toggleSelectAll() {
    setSelected(prev => {
      const allIds = filtered.map(d => d.id)
      const allSelected = allIds.every(id => prev.has(id))
      return allSelected ? new Set() : new Set(allIds)
    })
  }

  async function applyBulk() {
    const ids = Array.from(selected)
    if (ids.length === 0) { alert('Sélectionnez au moins une boisson.'); return }
    const hasCat = !!bulkCategory.trim()
    const hasUnit = !!bulkUnit.trim()
    const hasActive = bulkActive === 'true' || bulkActive === 'false'
    if (!hasCat && !hasUnit && !hasActive) { alert('Renseignez au moins un champ à appliquer.'); return }
    const payloadBase: any = {}
    if (hasCat) payloadBase.category = bulkCategory.trim()
    if (hasUnit) payloadBase.unit = bulkUnit.trim()
    if (hasActive) payloadBase.active = (bulkActive === 'true')
    await Promise.allSettled(ids.map(id => api.put(`/api/drinks/${id}`, payloadBase)))
    setSelected(new Set())
    setBulkCategory('')
    setBulkUnit('')
    setBulkActive('')
    await load()
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
            <select className="input" value={sortBy} onChange={e=>setSortBy(e.target.value as any)} aria-label="Trier par">
              <option value="name">Nom</option>
              <option value="category">Catégorie</option>
              <option value="unit">Unité</option>
              <option value="active">Actif</option>
              <option value="qty">Quantité</option>
            </select>
            <select className="input" value={sortDir} onChange={e=>setSortDir(e.target.value as any)} aria-label="Ordre">
              <option value="asc">Ascendant</option>
              <option value="desc">Descendant</option>
            </select>
          </div>
          <datalist id="drink-categories">
            {categories.map(c => (<option key={c} value={c} />))}
          </datalist>
          <datalist id="drink-units">
            {unitsList.map(u => (<option key={u} value={u} />))}
          </datalist>
          <div className="controls-divider" />
          <div className="controls-hint">Ajout rapide</div>
          <div className="drinks-grid">
            <input className="input" placeholder="Nom de la boisson" value={name} onChange={e=>setName(e.target.value)} />
            <input className="input" list="drink-categories" placeholder="Catégorie (ex: vin, bière)" value={category} onChange={e=>setCategory(e.target.value)} />
            <input className="input" list="drink-units" placeholder="Unité (ex: bouteille, carton)" value={unit} onChange={e=>setUnit(e.target.value)} />
            <button className="btn btn-primary" onClick={quickAdd}>Ajouter</button>
          </div>
          <div className="controls-divider" />
          <div className="controls-hint">Catégoriser / Modifier en masse (sélection)</div>
          <div className="upload-grid">
            <input className="input" list="drink-categories" placeholder="Catégorie" value={bulkCategory} onChange={e=>setBulkCategory(e.target.value)} />
            <input className="input" list="drink-units" placeholder="Unité" value={bulkUnit} onChange={e=>setBulkUnit(e.target.value)} />
            <select className="input" value={bulkActive} onChange={e=>setBulkActive(e.target.value)}>
              <option value="">Statut (inchangé)</option>
              <option value="true">Activer</option>
              <option value="false">Désactiver</option>
            </select>
            <div className="upload-actions">
              <button className="btn btn-primary" onClick={applyBulk} disabled={selected.size===0}>Appliquer ({selected.size})</button>
            </div>
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
                <th><input type="checkbox" checked={filtered.length>0 && filtered.every(d=>selected.has(d.id))} onChange={toggleSelectAll} /></th>
                <th>Boisson</th>
                <th>Catégorie</th>
                <th>Unité</th>
                <th>Quantité</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(d => (
                <tr key={d.id}>
                  <td><input type="checkbox" checked={selected.has(d.id)} onChange={()=>toggleSelect(d.id)} /></td>
                  <td className="font-medium text-gray-900 name-cell" title={d.name}>
                    {editingId===d.id ? (
                      <input className="input" value={eName} onChange={e=>setEName(e.target.value)} />
                    ) : (
                      d.name
                    )}
                  </td>
                  <td>
                    {editingId===d.id ? (
                      <input className="input" list="drink-categories" value={eCategory} onChange={e=>setECategory(e.target.value)} />
                    ) : (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-50 text-blue-700">{d.category || '-'}</span>
                    )}
                  </td>
                  <td>
                    {editingId===d.id ? (
                      <div className="drinks-grid" style={{gridTemplateColumns:'1fr auto'}}>
                        <input className="input" list="drink-units" value={eUnit} onChange={e=>setEUnit(e.target.value)} />
                        <label className="form-check"><input className="form-check-input" type="checkbox" checked={eActive} onChange={e=>setEActive(e.target.checked)} /> actif</label>
                      </div>
                    ) : (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-emerald-50 text-emerald-700">{d.unit || '-'}</span>
                    )}
                  </td>
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
                  <td>
                    {editingId===d.id ? (
                      <div className="btn-group">
                        <button className="btn btn-sm btn-primary" onClick={()=>saveEdit(d.id)}>Enregistrer</button>
                        <button className="btn btn-sm btn-outline" onClick={cancelEdit}>Annuler</button>
                      </div>
                    ) : (
                      <div className="btn-group">
                        <button className="btn btn-sm btn-outline" onClick={()=>startEdit(d)}>Modifier</button>
                        <button className="btn btn-sm btn-outline" onClick={()=>removeDrink(d.id)}>Supprimer</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td className="p-4 text-gray-500" colSpan={5}>Aucune boisson.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
