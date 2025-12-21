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
          <div className="controls-stack controls-row">
            <div className="controls-top">
              <input className="input" placeholder="Rechercher une boisson" value={q} onChange={e=>setQ(e.target.value)} />
            </div>
            <div className="controls-filters">
              <div className="filter-group" aria-label="Filtrer par catégorie">
                <span className="filter-label">Catégorie</span>
                <button className={`filter-chip ${cat==='all'?'is-active':''}`} onClick={()=>setCat('all')}>Toutes</button>
                {categories.map(c => (
                  <button key={c} className={`filter-chip ${cat===c?'is-active':''}`} onClick={()=>setCat(c)}>{c}</button>
                ))}
              </div>
            </div>
          </div>
          <div className="controls-divider" />
          <div className="controls-hint">Ajout rapide</div>
          <div className="add-stack add-row">
            <div className="add-top">
              <input className="input input-large" placeholder="Nom de la boisson" value={name} onChange={e=>setName(e.target.value)} />
            </div>
            <div className="add-controls">
              <label className="filter-label" htmlFor="add-cat">Catégorie</label>
              <input id="add-cat" className="input" placeholder="ex: vin, bière" value={category} onChange={e=>setCategory(e.target.value)} />
              <label className="filter-label" htmlFor="add-unit">Unité</label>
              <input id="add-unit" className="input" placeholder="ex: bouteille, carton" value={unit} onChange={e=>setUnit(e.target.value)} />
              <button className="btn btn-primary" onClick={quickAdd}>Ajouter</button>
            </div>
          </div>
        </div>

        <div className="table-container">
          <table className="table menu-table">
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
                    <div className="flex items-center gap-2">
                      <button className="btn btn-sm btn-outline" onClick={()=>inc(d.id, -1)}>-</button>
                      <input className="input w-16 text-center" value={counts[d.id] || 0} onChange={e=>{
                        const v = Math.max(0, parseInt(e.target.value||'0')||0)
                        setCounts(prev => ({ ...prev, [d.id]: v }))
                      }} />
                      <button className="btn btn-sm btn-outline" onClick={()=>inc(d.id, +1)}>+</button>
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
