import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api'
import { MenuItem } from '../types'
import { Check, ChevronDown, Pencil, Plus, Search, Trash2, X } from 'lucide-react'

type EditState = { id: string; name: string; type: string }

const TYPE_COLORS: Record<string, string> = {
  'entrée': 'bg-emerald-50 text-emerald-700 border-emerald-200',
  'plat': 'bg-blue-50 text-blue-700 border-blue-200',
  'dessert': 'bg-amber-50 text-amber-700 border-amber-200',
}

export default function MenuList() {
  const [items, setItems] = useState<MenuItem[]>([])
  const [name, setName] = useState('')
  const [type, setType] = useState('plat')
  const [active, setActive] = useState(true)
  const [q, setQ] = useState('')
  const [activeFilter, setActiveFilter] = useState<'all' | 'true' | 'false'>('all')
  const [editing, setEditing] = useState<EditState | null>(null)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [bulkOpen, setBulkOpen] = useState(false)
  const [bulkText, setBulkText] = useState('')
  const [bulkStatus, setBulkStatus] = useState<string | null>(null)
  const [bulkLoading, setBulkLoading] = useState(false)
  const editNameRef = useRef<HTMLInputElement>(null)

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

  const byType = useMemo(() => {
    const ql = q.trim().toLowerCase()
    const filter = (t: string) => items.filter(it => {
      if (it.type !== t) return false
      if (activeFilter !== 'all' && String(it.active) !== activeFilter) return false
      if (ql && !it.name.toLowerCase().includes(ql)) return false
      return true
    }).sort((a, b) => a.name.localeCompare(b.name))
    return {
      'entrée': filter('entrée'),
      'plat': filter('plat'),
      'dessert': filter('dessert'),
    }
  }, [items, q, activeFilter])

  async function add() {
    if (!name.trim()) return
    await api.post('/api/menu-items', { name: name.trim(), type, active })
    setName('')
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

  function startEdit(it: MenuItem) {
    setEditing({ id: it.id, name: it.name, type: it.type })
    setTimeout(() => editNameRef.current?.focus(), 0)
  }

  async function commitEdit() {
    if (!editing) return
    const it = items.find(i => i.id === editing.id)
    if (!it) { setEditing(null); return }
    if (editing.name.trim() === it.name && editing.type === it.type) { setEditing(null); return }
    setSavingId(editing.id)
    try {
      await api.put(`/api/menu-items/${editing.id}`, { name: editing.name.trim(), type: editing.type })
      await load()
    } finally {
      setSavingId(null)
      setEditing(null)
    }
  }

  async function addBulk() {
    if (!bulkText.trim()) return
    setBulkLoading(true)
    setBulkStatus(null)
    const lines = bulkText.split('\n').map(l => l.trim()).filter(Boolean)
    let ok = 0; let fail = 0
    for (const line of lines) {
      const parts = line.split('|').map(s => s.trim())
      const dishName = parts[0]
      const rawType = (parts[1] || type).toLowerCase()
      const dishType = rawType.startsWith('entr') ? 'entrée' : rawType.startsWith('des') ? 'dessert' : 'plat'
      if (!dishName) { fail++; continue }
      try {
        await api.post('/api/menu-items', { name: dishName, type: dishType, active: true })
        ok++
      } catch { fail++ }
    }
    await load()
    setBulkLoading(false)
    setBulkStatus(`${ok} ajouté(s)${fail > 0 ? `, ${fail} erreur(s)` : ''}`)
    if (ok > 0) setBulkText('')
  }

  const COLUMNS: { key: 'entrée' | 'plat' | 'dessert'; label: string }[] = [
    { key: 'entrée', label: 'Entrées' },
    { key: 'plat', label: 'Plats' },
    { key: 'dessert', label: 'Desserts' },
  ]

  return (
    <div className="card menu-list-page">
      <div className="card-header">
        <h3 className="text-lg font-semibold">Base de plats</h3>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-gray-500">
            <b>{counts.entree}</b> entrées · <b>{counts.plat}</b> plats · <b>{counts.dessert}</b> desserts
          </span>
          <button
            className={`btn btn-sm ${bulkOpen ? 'btn-primary' : 'btn-outline'} flex items-center gap-1`}
            onClick={() => { setBulkOpen(v => !v); setBulkStatus(null) }}
          >
            {bulkOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
            Ajout en masse
          </button>
          <button className="btn btn-sm btn-outline text-red-600 hover:bg-red-50" onClick={clearAll}>
            <Trash2 className="w-3.5 h-3.5" /> Tout supprimer
          </button>
        </div>
      </div>

      <div className="card-body space-y-4">

        {/* ── Ajout en masse (collapsible) ── */}
        {bulkOpen && (
          <div className="p-4 bg-violet-50 border border-violet-100 rounded-lg space-y-3">
            <p className="text-sm font-medium text-violet-800">Ajout en masse</p>
            <p className="text-xs text-violet-600">
              Une ligne par plat. Format : <code className="bg-white px-1 rounded">Nom du plat | type</code> (type = entrée / plat / dessert).
              Si pas de type indiqué, le type par défaut ci-dessous s'applique.
            </p>
            <div className="flex gap-2 items-center text-sm">
              <span className="text-gray-600">Type par défaut :</span>
              {(['entrée','plat','dessert'] as const).map(t => (
                <button
                  key={t}
                  className={`px-2 py-0.5 rounded border text-xs ${type === t ? 'bg-violet-600 text-white border-violet-600' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'}`}
                  onClick={() => setType(t)}
                >{t}</button>
              ))}
            </div>
            <textarea
              className="input w-full h-32 font-mono text-sm"
              placeholder={"Salade César | entrée\nBœuf bourguignon | plat\nTarte tatin | dessert\nCarpaccio\nSaumon grillé"}
              value={bulkText}
              onChange={e => setBulkText(e.target.value)}
            />
            {bulkStatus && (
              <p className={`text-sm font-medium ${bulkStatus.includes('erreur') ? 'text-red-600' : 'text-green-700'}`}>{bulkStatus}</p>
            )}
            <div className="flex gap-2">
              <button
                className="btn btn-primary flex items-center gap-1.5"
                onClick={addBulk}
                disabled={bulkLoading || !bulkText.trim()}
              >
                <Plus className="w-4 h-4" /> {bulkLoading ? 'Ajout…' : 'Ajouter tout'}
              </button>
              <button className="btn btn-outline" onClick={() => setBulkOpen(false)}>Fermer</button>
            </div>
          </div>
        )}

        {/* ── Barre de filtres + ajout rapide ── */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
              <input className="input pl-8 w-48" placeholder="Rechercher…" value={q} onChange={e => setQ(e.target.value)} />
            </div>
            <div className="flex items-center gap-1">
              {(['all','true','false'] as const).map(af => (
                <button
                  key={af}
                  className={`filter-chip ${activeFilter === af ? 'is-active' : ''}`}
                  onClick={() => setActiveFilter(af)}
                >
                  {af === 'all' ? 'Tous' : af === 'true' ? 'Actifs' : 'Inactifs'}
                </button>
              ))}
            </div>
          </div>

          {/* Ajout rapide */}
          <div className="flex items-center gap-2 flex-wrap">
            <input
              className="input w-44 text-sm"
              placeholder="Nouveau plat…"
              value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
            />
            <select className="input text-sm w-28" value={type} onChange={e => setType(e.target.value)}>
              <option value="entrée">Entrée</option>
              <option value="plat">Plat</option>
              <option value="dessert">Dessert</option>
            </select>
            <label className="flex items-center gap-1 text-sm text-gray-600 cursor-pointer">
              <input type="checkbox" checked={active} onChange={e => setActive(e.target.checked)} className="form-check-input" />
              Actif
            </label>
            <button className="btn btn-primary btn-sm flex items-center gap-1" onClick={add} disabled={!name.trim()}>
              <Plus className="w-4 h-4" /> Ajouter
            </button>
          </div>
        </div>

        {/* ── 3 colonnes par catégorie ── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {COLUMNS.map(({ key, label }) => {
            const colItems = byType[key]
            const colorHeader = key === 'entrée'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : key === 'plat'
              ? 'bg-blue-50 border-blue-200 text-blue-800'
              : 'bg-amber-50 border-amber-200 text-amber-800'
            const colorBadge = key === 'entrée'
              ? 'bg-emerald-100 text-emerald-700'
              : key === 'plat'
              ? 'bg-blue-100 text-blue-700'
              : 'bg-amber-100 text-amber-700'

            return (
              <div key={key} className="border border-gray-200 rounded-lg overflow-hidden">
                {/* Entête colonne */}
                <div className={`flex items-center justify-between px-3 py-2 border-b ${colorHeader}`}>
                  <span className="font-semibold text-sm">{label}</span>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${colorBadge}`}>
                    {colItems.length}
                  </span>
                </div>

                {/* Liste */}
                <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
                  {colItems.length === 0 && (
                    <p className="text-center text-gray-400 text-sm py-6">Aucun élément</p>
                  )}
                  {colItems.map(it => {
                    const isEditing = editing?.id === it.id
                    const isSaving = savingId === it.id
                    return (
                      <div key={it.id} className={`flex items-center gap-2 px-3 py-2 group hover:bg-gray-50 transition-colors ${!it.active ? 'opacity-50' : ''}`}>
                        {isEditing ? (
                          /* ── Mode édition inline ── */
                          <>
                            <input
                              ref={editNameRef}
                              className="input flex-1 text-sm py-1"
                              value={editing.name}
                              onChange={e => setEditing(prev => prev ? { ...prev, name: e.target.value } : null)}
                              onKeyDown={e => {
                                if (e.key === 'Enter') commitEdit()
                                if (e.key === 'Escape') setEditing(null)
                              }}
                            />
                            <select
                              className="input text-xs w-24 py-1"
                              value={editing.type}
                              onChange={e => setEditing(prev => prev ? { ...prev, type: e.target.value } : null)}
                            >
                              <option value="entrée">Entrée</option>
                              <option value="plat">Plat</option>
                              <option value="dessert">Dessert</option>
                            </select>
                            <button
                              className="btn btn-sm btn-primary px-2 py-1 flex items-center gap-0.5"
                              onClick={commitEdit}
                              disabled={isSaving}
                            >
                              <Check className="w-3.5 h-3.5" />
                            </button>
                            <button className="btn btn-sm btn-outline px-2 py-1" onClick={() => setEditing(null)}>
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </>
                        ) : (
                          /* ── Mode lecture ── */
                          <>
                            <span className="flex-1 text-sm text-gray-800 truncate" title={it.name}>{it.name}</span>
                            <span className={`text-xs px-1.5 py-0.5 rounded-full border shrink-0 ${TYPE_COLORS[it.type] || ''}`}>{it.type}</span>
                            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                              <button
                                className="btn btn-sm btn-outline px-1.5 py-1"
                                onClick={() => startEdit(it)}
                                title="Modifier"
                              >
                                <Pencil className="w-3 h-3" />
                              </button>
                              <button
                                className={`btn btn-sm btn-outline px-1.5 py-1 ${it.active ? 'text-gray-500' : 'text-green-600'}`}
                                onClick={() => toggleActive(it)}
                                title={it.active ? 'Désactiver' : 'Activer'}
                              >
                                {it.active ? <X className="w-3 h-3" /> : <Check className="w-3 h-3" />}
                              </button>
                              <button
                                className="btn btn-sm btn-outline px-1.5 py-1 text-red-500 hover:bg-red-50"
                                onClick={() => remove(it)}
                                title="Supprimer"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    )
                  })}
                </div>

                {/* Quick-add par colonne */}
                <div className="border-t border-gray-100 p-2">
                  <form
                    onSubmit={async e => {
                      e.preventDefault()
                      const form = e.currentTarget
                      const input = form.elements.namedItem('colname') as HTMLInputElement
                      const v = input.value.trim()
                      if (!v) return
                      await api.post('/api/menu-items', { name: v, type: key, active: true })
                      input.value = ''
                      await load()
                    }}
                    className="flex gap-1"
                  >
                    <input
                      name="colname"
                      className="input flex-1 text-sm py-1"
                      placeholder={`Ajouter une ${label.toLowerCase().slice(0, -1)}…`}
                    />
                    <button type="submit" className="btn btn-sm btn-outline px-2">
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                  </form>
                </div>
              </div>
            )
          })}
        </div>

      </div>
    </div>
  )
}
