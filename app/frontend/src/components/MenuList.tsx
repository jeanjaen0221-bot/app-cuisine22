import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { MenuItem } from '../types'
import { Search } from 'lucide-react'

export default function MenuList() {
  const [items, setItems] = useState<MenuItem[]>([])
  const [name, setName] = useState('')
  const [type, setType] = useState('plat')
  const [active, setActive] = useState(true)
  const [q, setQ] = useState('')
  const [typeFilter, setTypeFilter] = useState<'all' | 'entrée' | 'plat' | 'dessert'>('all')
  const [activeFilter, setActiveFilter] = useState<'all' | 'true' | 'false'>('all')
  const [sortKey, setSortKey] = useState<'type' | 'active' | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  async function load() {
    const res = await api.get('/api/menu-items')
    setItems(res.data)
  }
  useEffect(() => { load() }, [])

  const counts = useMemo(() => {
    const c = { entree: 0, plat: 0, dessert: 0, total: items.length }
    for (const it of items) {
      if (it.type === 'entrée') c.entree++
      else if (it.type === 'plat') c.plat++
      else if (it.type === 'dessert') c.dessert++
    }
    return c
  }, [items])

  const filtered = useMemo(() => {
    const ql = q.trim().toLowerCase()
    return items.filter(it => {
      if (typeFilter !== 'all' && it.type !== typeFilter) return false
      if (activeFilter !== 'all') {
        const want = activeFilter === 'true'
        if (it.active !== want) return false
      }
      if (ql && !it.name.toLowerCase().includes(ql)) return false
      return true
    })
  }, [items, q, typeFilter, activeFilter])

  const sorted = useMemo(() => {
    const arr = [...filtered]
    if (!sortKey) return arr
    const typeOrder: Record<string, number> = { 'entrée': 0, 'plat': 1, 'dessert': 2 }
    arr.sort((a, b) => {
      let va: number | boolean | string
      let vb: number | boolean | string
      if (sortKey === 'type') {
        va = typeOrder[a.type] ?? 99
        vb = typeOrder[b.type] ?? 99
      } else {
        va = a.active
        vb = b.active
      }
      let cmp = 0
      if (typeof va === 'number' && typeof vb === 'number') cmp = va - vb
      else if (typeof va === 'boolean' && typeof vb === 'boolean') cmp = (va === vb ? 0 : va ? 1 : -1)
      else cmp = String(va).localeCompare(String(vb))
      return sortDir === 'asc' ? cmp : -cmp
    })
    return arr
  }, [filtered, sortKey, sortDir])

  function toggleSort(key: 'type' | 'active') {
    if (sortKey === key) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  async function add() {
    if (!name) return
    await api.post('/api/menu-items', { name, type, active })
    setName(''); setType('plat'); setActive(true)
    await load()
  }

  async function toggleActive(it: MenuItem) {
    await api.put(`/api/menu-items/${it.id}`, { active: !it.active })
    await load()
  }

  async function remove(it: MenuItem) {
    if (!confirm('Supprimer cet élément ?')) return
    await api.delete(`/api/menu-items/${it.id}`)
    await load()
  }

  async function clearAll() {
    const ok1 = confirm('Voulez-vous vraiment supprimer TOUS les plats ?')
    if (!ok1) return
    const ok2 = confirm('Confirmation finale: cette action est irréversible. Continuer ?')
    if (!ok2) return
    await api.delete('/api/menu-items', { params: { confirm: true } })
    await load()
  }

  return (
    <div className="card menu-list-page">
      <div className="card-header">
        <h3 className="text-lg font-semibold">Base de plats</h3>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs md:text-sm text-gray-600">
            <span>Total: <b>{counts.total}</b></span>
            <span>Entrées: <b>{counts.entree}</b></span>
            <span>Plats: <b>{counts.plat}</b></span>
            <span>Desserts: <b>{counts.dessert}</b></span>
          </div>
          <button className="btn btn-sm btn-danger" onClick={clearAll}>Tout supprimer</button>
        </div>
      </div>

      <div className="card-body space-y-3">
        <div className="grid grid-cols-12 gap-2 controls-row">
          <div className="col-span-12 md:col-span-5">
            <input className="input" placeholder="Rechercher un plat" value={q} onChange={e=>setQ(e.target.value)} />
          </div>
          <div className="col-span-12 md:col-span-7 flex flex-wrap gap-4 items-center">
            <div className="btn-group" role="group" aria-label="Filtrer par type">
              {(['all','entrée','plat','dessert'] as const).map(tf => (
                <button
                  key={tf}
                  className={`btn btn-sm ${typeFilter===tf ? '' : 'btn-outline'}`}
                  onClick={()=>setTypeFilter(tf)}
                >
                  {tf === 'all' ? 'Tous' : tf.charAt(0).toUpperCase()+tf.slice(1)}
                </button>
              ))}
            </div>
            <div className="btn-group" role="group" aria-label="Filtrer par statut">
              {(['all','true','false'] as const).map(af => (
                <button
                  key={af}
                  className={`btn btn-sm ${activeFilter===af ? '' : 'btn-outline'}`}
                  onClick={()=>setActiveFilter(af)}
                >
                  {af==='all' ? 'Tous' : af==='true' ? 'Actifs' : 'Inactifs'}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-12 gap-2 add-row">
          <input className="input col-span-12 md:col-span-6" placeholder="Nom du plat (ajout rapide)" value={name} onChange={e=>setName(e.target.value)} />
          <select className="input col-span-6 md:col-span-3" value={type} onChange={e=>setType(e.target.value)}>
            <option>entrée</option>
            <option>plat</option>
            <option>dessert</option>
          </select>
          <select className="input col-span-6 md:col-span-2" value={String(active)} onChange={e=>setActive(e.target.value==='true')}>
            <option value="true">Actif</option>
            <option value="false">Inactif</option>
          </select>
          <button className="btn btn-sm col-span-6 md:col-span-1" onClick={add}>Ajouter</button>
        </div>

        <div className="table-container">
          <table className="table menu-table">
            <thead>
              <tr>
                <th>Nom</th>
                <th aria-sort={sortKey==='type' ? (sortDir==='asc' ? 'ascending' : 'descending') : 'none'}>
                  <button type="button" className="px-2 py-1 rounded hover:bg-gray-100 select-none" onClick={()=>toggleSort('type')}>
                    Type {sortKey==='type' ? (sortDir==='asc' ? '▲' : '▼') : ''}
                  </button>
                </th>
                <th aria-sort={sortKey==='active' ? (sortDir==='asc' ? 'ascending' : 'descending') : 'none'}>
                  <button type="button" className="px-2 py-1 rounded hover:bg-gray-100 select-none" onClick={()=>toggleSort('active')}>
                    Statut {sortKey==='active' ? (sortDir==='asc' ? '▲' : '▼') : ''}
                  </button>
                </th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(it => (
                <tr key={it.id}>
                  <td className="font-medium text-gray-900 name-cell" title={it.name}>{it.name}</td>
                  <td>
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs ${it.type==='entrée' ? 'bg-emerald-50 text-emerald-700' : it.type==='plat' ? 'bg-blue-50 text-blue-700' : 'bg-amber-50 text-amber-700'}`}>{it.type}</span>
                  </td>
                  <td>
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs ${it.active ? 'bg-purple-50 text-purple-700' : 'bg-gray-100 text-gray-700'}`}>{it.active ? 'Actif' : 'Inactif'}</span>
                  </td>
                  <td>
                    <div className="flex gap-2 actions-cell">
                      <button className="btn btn-sm btn-outline" onClick={()=>toggleActive(it)}>{it.active ? 'Désactiver' : 'Activer'}</button>
                      <button className="btn btn-sm btn-outline" onClick={()=>remove(it)}>Supprimer</button>
                    </div>
                  </td>
                </tr>
              ))}
              {sorted.length === 0 && (
                <tr>
                  <td className="p-4 text-gray-500" colSpan={4}>Aucun élément ne correspond aux filtres.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
