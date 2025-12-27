import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import type { Drink, DrinkStock, ReplenishItem, ReplenishOptions, ReplenishResponse } from '../types'

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
  const [sortBy, setSortBy] = useState<'name' | 'category' | 'unit' | 'active' | 'qty'>('name')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [activeTab, setActiveTab] = useState<'liste' | 'ajout' | 'import' | 'mass' | 'reassort'>('reassort')
  const [showInactive, setShowInactive] = useState(false)

  const [counts, setCounts] = useState<Record<string, number>>(() => {
    try {
      const raw = localStorage.getItem('drinks-order')
      return raw ? JSON.parse(raw) : {}
    } catch {
      return {}
    }
  })

  // Sous-onglets Réassort: saisie vs paramètres
  const [reassortTab, setReassortTab] = useState<'saisie' | 'param'>(() => {
    try {
      return ((localStorage.getItem('drinks-reassort-subtab') as any) || 'saisie') as 'saisie' | 'param'
    } catch {
      return 'saisie'
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem('drinks-reassort-subtab', reassortTab)
    } catch {}
  }, [reassortTab])

  // Réassort: remaining qty per drink (persist locally)
  const [remaining, setRemaining] = useState<Record<string, number>>(() => {
    try {
      const raw = localStorage.getItem('drinks-remaining')
      return raw ? JSON.parse(raw) : {}
    } catch {
      return {}
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem('drinks-remaining', JSON.stringify(remaining))
    } catch {}
  }, [remaining])

  // Réassort: stock settings loaded from backend
  const [stock, setStock] = useState<Record<string, DrinkStock>>({})
  const [loadingStock, setLoadingStock] = useState(false)

  async function loadStock() {
    setLoadingStock(true)
    try {
      const res = await api.get('/api/drinks/stock')
      const arr: DrinkStock[] = res.data
      const map: Record<string, DrinkStock> = {}
      arr.forEach((s) => {
        map[s.drink_id] = s
      })
      setStock(map)
    } finally {
      setLoadingStock(false)
    }
  }
  useEffect(() => {
    loadStock()
  }, [])

  // Réassort: compute suggestions
  const [opts, setOpts] = useState<ReplenishOptions>(() => {
    try {
      const raw = localStorage.getItem('drinks-replenish-opts')
      if (raw) return JSON.parse(raw)
    } catch {}
    return { target: 'max', rounding: 'pack' }
  })
  const [repl, setRepl] = useState<Record<string, ReplenishItem>>({})
  const [recalcPending, setRecalcPending] = useState(false)

  useEffect(() => {
    try {
      localStorage.setItem('drinks-replenish-opts', JSON.stringify(opts))
    } catch {}
  }, [opts])

  async function computeReplenishment() {
    setRecalcPending(true)
    try {
      const payload = { remaining, options: opts }
      const res = await api.post<ReplenishResponse>('/api/drinks/replenishment', payload)
      const map: Record<string, ReplenishItem> = {}
      res.data.items.forEach((it) => {
        map[it.drink_id] = it
      })
      setRepl(map)
    } finally {
      setRecalcPending(false)
    }
  }

  const [autoCalc, setAutoCalc] = useState<boolean>(() => {
    try {
      const raw = localStorage.getItem('drinks-replenish-auto')
      return raw ? JSON.parse(raw) : true
    } catch {
      return true
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem('drinks-replenish-auto', JSON.stringify(autoCalc))
    } catch {}
  }, [autoCalc])

  useEffect(() => {
    if (activeTab !== 'reassort' || !autoCalc) return
    const t = setTimeout(() => {
      computeReplenishment()
    }, 400)
    return () => clearTimeout(t)
  }, [remaining, stock, opts, activeTab, autoCalc])

  // Aide: panneau fixe à droite
  const [helpOpen, setHelpOpen] = useState<boolean>(() => {
    try {
      const raw = localStorage.getItem('drinks-help-open')
      return raw ? JSON.parse(raw) : true
    } catch {
      return true
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem('drinks-help-open', JSON.stringify(helpOpen))
    } catch {}
  }, [helpOpen])

  async function load() {
    const res = await api.get('/api/drinks')
    setDrinks(res.data)
  }
  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem('drinks-order', JSON.stringify(counts))
    } catch {}
  }, [counts])

  const categories = useMemo(() => {
    const s = new Set<string>()
    drinks.forEach((d) => {
      if (d.category) s.add(d.category)
    })
    return Array.from(s).sort()
  }, [drinks])

  const unitsList = useMemo(() => {
    const s = new Set<string>()
    drinks.forEach((d) => {
      if (d.unit) s.add(d.unit)
    })
    return Array.from(s).sort()
  }, [drinks])

  const collator = useMemo(() => new Intl.Collator('fr', { sensitivity: 'base' }), [])

  const filtered = useMemo(() => {
    const ql = q.trim().toLowerCase()
    return drinks.filter((d) => {
      if (!showInactive && !d.active) return false
      if (cat !== 'all' && (d.category || '') !== cat) return false
      if (ql && !d.name.toLowerCase().includes(ql)) return false
      return true
    })
  }, [drinks, q, cat, showInactive])

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

  const isMass = activeTab === 'mass'

  // Helpers for reassort
  function setRem(id: string, v: number) {
    setRemaining((prev) => ({ ...prev, [id]: Math.max(0, v) }))
  }

  async function updateStockField(id: string, patch: Partial<DrinkStock>) {
    const current: DrinkStock =
      stock[id] || { drink_id: id, min_qty: 0, max_qty: 0, pack_size: null, reorder_enabled: true }

    const payload: any = {}
    if (patch.min_qty !== undefined) payload.min_qty = Math.max(0, Number(patch.min_qty || 0))
    if (patch.max_qty !== undefined) payload.max_qty = Math.max(0, Number(patch.max_qty || 0))
    if (patch.pack_size !== undefined) payload.pack_size = patch.pack_size ? Math.max(1, Number(patch.pack_size || 0)) : null
    if (patch.reorder_enabled !== undefined) payload.reorder_enabled = !!patch.reorder_enabled

    // si rien à patch, éviter un PUT vide
    if (Object.keys(payload).length === 0) return

    const res = await api.put(`/api/drinks/${id}/stock`, payload)
    const updated: DrinkStock = res.data
    setStock((prev) => ({ ...prev, [id]: updated }))
  }

  type ReassortStatus = 'critique' | 'a_completer' | 'ok'
  function getStatus(id: string): ReassortStatus {
    const rem = Number(remaining[id] || 0)
    const s = stock[id] || { drink_id: id, min_qty: 0, max_qty: 0, pack_size: null, reorder_enabled: true }
    if (rem < (s.min_qty || 0)) return 'critique'
    if (rem < (s.max_qty || 0)) return 'a_completer'
    return 'ok'
  }

  function renderStatusBadge(s: ReassortStatus) {
    if (s === 'critique') return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-red-50 text-red-700">Critique</span>
    if (s === 'a_completer') return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-amber-50 text-amber-700">À compléter</span>
    return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-emerald-50 text-emerald-700">OK</span>
  }

  const replSummary = useMemo(() => {
    const items = Object.values(repl)
    const lines = items.filter((x) => (x.suggest || 0) > 0).length
    const total = items.reduce((a, b) => a + (b.suggest || 0), 0)
    return { lines, total }
  }, [repl])

  async function bulkEnableReorder(enabled: boolean) {
    const list = filtered.map((d) => d.id)
    await Promise.allSettled(list.map((id) => updateStockField(id, { reorder_enabled: enabled })))
    if (autoCalc) computeReplenishment()
  }
  async function bulkCopyMinToMax() {
    const updates = filtered.map((d) => {
      const s = stock[d.id] || { drink_id: d.id, min_qty: 0, max_qty: 0, pack_size: null, reorder_enabled: true }
      return updateStockField(d.id, { max_qty: s.min_qty })
    })
    await Promise.allSettled(updates)
    if (autoCalc) computeReplenishment()
  }
  async function bulkCopyMaxToMin() {
    const updates = filtered.map((d) => {
      const s = stock[d.id] || { drink_id: d.id, min_qty: 0, max_qty: 0, pack_size: null, reorder_enabled: true }
      return updateStockField(d.id, { min_qty: s.max_qty })
    })
    await Promise.allSettled(updates)
    if (autoCalc) computeReplenishment()
  }
  function bulkResetRemaining() {
    const next = { ...remaining }
    filtered.forEach((d) => {
      next[d.id] = 0
    })
    setRemaining(next)
  }

  const summary = useMemo(() => {
    let lines = 0
    let total = 0
    for (const id in counts) {
      const v = counts[id] || 0
      if (v > 0) {
        lines++
        total += v
      }
    }
    return { lines, total }
  }, [counts])

  function inc(id: string, delta: number) {
    setCounts((prev) => ({ ...prev, [id]: Math.max(0, (prev[id] || 0) + delta) }))
  }

  function resetAll() {
    if (!confirm('Remettre tous les compteurs à 0 ?')) return
    setCounts({})
  }

  async function quickAdd() {
    if (!name.trim()) return
    await api.post('/api/drinks', { name: name.trim(), category: category || null, unit: unit || null, active: true })
    setName('')
    setCategory('')
    setUnit('')
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
      setFileKey((k) => k + 1)
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
    setCounts((prev) => {
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
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleSelectAll() {
    setSelected((prev) => {
      const allIds = filtered.map((d) => d.id)
      const allSelected = allIds.every((id) => prev.has(id))
      return allSelected ? new Set() : new Set(allIds)
    })
  }

  async function applyBulk() {
    const ids = Array.from(selected)
    if (ids.length === 0) {
      alert('Sélectionnez au moins une boisson.')
      return
    }
    const hasCat = !!bulkCategory.trim()
    const hasUnit = !!bulkUnit.trim()
    const hasActive = bulkActive === 'true' || bulkActive === 'false'
    if (!hasCat && !hasUnit && !hasActive) {
      alert('Renseignez au moins un champ à appliquer.')
      return
    }
    const payloadBase: any = {}
    if (hasCat) payloadBase.category = bulkCategory.trim()
    if (hasUnit) payloadBase.unit = bulkUnit.trim()
    if (hasActive) payloadBase.active = bulkActive === 'true'
    await Promise.allSettled(ids.map((id) => api.put(`/api/drinks/${id}`, payloadBase)))
    setSelected(new Set())
    setBulkCategory('')
    setBulkUnit('')
    setBulkActive('')
    await load()
  }

  const reassortEmptyColSpan = reassortTab === 'saisie' ? 7 : 8

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="text-lg font-semibold">Commande boissons</h3>
        <div className="flex items-center gap-3 text-sm text-gray-700">
          <span>
            Lignes: <b>{summary.lines}</b>
          </span>
          <span>
            Total: <b>{summary.total}</b>
          </span>
          <button className="btn btn-sm btn-outline" onClick={resetAll}>
            Tout remettre à 0
          </button>
        </div>
      </div>

      <div className="card-body space-y-4">
        <div className="controls-panel">
          <div className="flex items-center gap-2" style={{ marginBottom: '.5rem' }}>
            <button className={`btn btn-sm ${activeTab === 'liste' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setActiveTab('liste')}>
              Liste
            </button>
            <button className={`btn btn-sm ${activeTab === 'ajout' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setActiveTab('ajout')}>
              Ajouter
            </button>
            <button className={`btn btn-sm ${activeTab === 'import' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setActiveTab('import')}>
              Importer
            </button>
            <button className={`btn btn-sm ${activeTab === 'mass' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setActiveTab('mass')}>
              Modifier en masse
            </button>
            <button className={`btn btn-sm ${activeTab === 'reassort' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setActiveTab('reassort')}>
              Réassort
            </button>
          </div>

          {activeTab === 'liste' && (
            <div className="drinks-controls">
              <input className="input" placeholder="Rechercher une boisson" value={q} onChange={(e) => setQ(e.target.value)} />
              <select className="input" value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Filtrer par catégorie">
                <option value="all">Toutes</option>
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <select className="input" value={sortBy} onChange={(e) => setSortBy(e.target.value as any)} aria-label="Trier par">
                <option value="name">Nom</option>
                <option value="category">Catégorie</option>
                <option value="unit">Unité</option>
                <option value="active">Actif</option>
                <option value="qty">Quantité</option>
              </select>
              <select className="input" value={sortDir} onChange={(e) => setSortDir(e.target.value as any)} aria-label="Ordre">
                <option value="asc">Ascendant</option>
                <option value="desc">Descendant</option>
              </select>
              <label className="form-check">
                <input className="form-check-input" type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} /> Afficher inactives
              </label>
            </div>
          )}

          {activeTab === 'reassort' && (
            <>
              <div className="flex items-center gap-2" style={{ marginBottom: '.25rem' }}>
                <button className={`btn btn-sm ${reassortTab === 'saisie' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setReassortTab('saisie')}>
                  Saisie
                </button>
                <button className={`btn btn-sm ${reassortTab === 'param' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setReassortTab('param')}>
                  Paramètres
                </button>
              </div>

              <div className="controls-hint">Saisir les quantités restantes et calculer les suggestions de réassort</div>

              <div className="drinks-controls">
                <input className="input" placeholder="Rechercher une boisson" value={q} onChange={(e) => setQ(e.target.value)} />
                <select className="input" value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Filtrer par catégorie">
                  <option value="all">Toutes</option>
                  {categories.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>

                <select className="input" value={opts.target} onChange={(e) => setOpts((o) => ({ ...o, target: e.target.value as any }))}>
                  <option value="max">Cible: maximum</option>
                  <option value="min">Cible: minimum</option>
                </select>

                <select className="input" value={opts.rounding} onChange={(e) => setOpts((o) => ({ ...o, rounding: e.target.value as any }))}>
                  <option value="pack">Arrondi: colis</option>
                  <option value="none">Arrondi: aucun</option>
                </select>

                <label className="form-check">
                  <input className="form-check-input" type="checkbox" checked={autoCalc} onChange={(e) => setAutoCalc(e.target.checked)} /> auto
                </label>

                <button className="btn btn-primary" onClick={computeReplenishment} disabled={recalcPending || loadingStock}>
                  {recalcPending ? 'Calcul...' : 'Calculer'}
                </button>

                <button className="btn btn-outline" style={{ marginLeft: 'auto' }} onClick={() => setHelpOpen((o) => !o)}>
                  {helpOpen ? 'Masquer aide' : 'Aide'}
                </button>
              </div>

              <div className="drinks-controls" style={{ marginTop: '.25rem' }}>
                <button className="btn btn-sm btn-outline" onClick={bulkResetRemaining}>
                  Restants = 0 (filtrés)
                </button>
                <button className="btn btn-sm btn-outline" onClick={() => bulkEnableReorder(true)}>
                  Activer réassort (filtrés)
                </button>
                <button className="btn btn-sm btn-outline" onClick={() => bulkEnableReorder(false)}>
                  Désactiver réassort (filtrés)
                </button>
                <button className="btn btn-sm btn-outline" onClick={bulkCopyMinToMax}>
                  Copier Min → Max (filtrés)
                </button>
                <button className="btn btn-sm btn-outline" onClick={bulkCopyMaxToMin}>
                  Copier Max → Min (filtrés)
                </button>
                <div className="flex items-center gap-3 text-sm text-gray-700" style={{ marginLeft: 'auto' }}>
                  <span>
                    Suggestions: <b>{replSummary.lines}</b> lignes
                  </span>
                  <span>
                    Total: <b>{replSummary.total}</b>
                  </span>
                </div>
              </div>
            </>
          )}

          {activeTab === 'ajout' && (
            <>
              <div className="controls-hint">Ajout rapide</div>
              <div className="drinks-grid">
                <input className="input" placeholder="Nom de la boisson" value={name} onChange={(e) => setName(e.target.value)} />
                <input className="input" list="drink-categories" placeholder="Catégorie (ex: vin, bière)" value={category} onChange={(e) => setCategory(e.target.value)} />
                <input className="input" list="drink-units" placeholder="Unité (ex: bouteille, carton)" value={unit} onChange={(e) => setUnit(e.target.value)} />
                <button className="btn btn-primary" onClick={quickAdd}>
                  Ajouter
                </button>
              </div>
            </>
          )}

          {activeTab === 'mass' && (
            <>
              <div className="controls-hint">Catégoriser / Modifier en masse (sélection)</div>
              <div className="upload-grid">
                <input className="input" list="drink-categories" placeholder="Catégorie" value={bulkCategory} onChange={(e) => setBulkCategory(e.target.value)} />
                <input className="input" list="drink-units" placeholder="Unité" value={bulkUnit} onChange={(e) => setBulkUnit(e.target.value)} />
                <select className="input" value={bulkActive} onChange={(e) => setBulkActive(e.target.value)}>
                  <option value="">Statut (inchangé)</option>
                  <option value="true">Activer</option>
                  <option value="false">Désactiver</option>
                </select>
                <div className="upload-actions">
                  <button className="btn btn-primary" onClick={applyBulk} disabled={selected.size === 0}>
                    Appliquer ({selected.size})
                  </button>
                </div>
              </div>
            </>
          )}

          {activeTab === 'import' && (
            <>
              <div className="controls-hint">Importer un fichier (.csv, .txt)</div>
              <div className="upload-grid">
                <input key={fileKey} type="file" accept=".csv,.txt" className="input" onChange={(e) => setUploadFile(e.target.files?.[0] || null)} />
                <input className="input" placeholder="Catégorie par défaut" value={uploadCategory} onChange={(e) => setUploadCategory(e.target.value)} />
                <input className="input" placeholder="Unité par défaut" value={uploadUnit} onChange={(e) => setUploadUnit(e.target.value)} />
                <div className="upload-actions">
                  <button className="btn btn-primary" onClick={handleUpload} disabled={!uploadFile || importing}>
                    {importing ? 'Import...' : 'Importer'}
                  </button>
                  {lastImportAdded !== null && <span className="text-sm text-gray-600">Ajoutés: {lastImportAdded}</span>}
                </div>
              </div>
            </>
          )}

          <datalist id="drink-categories">
            {categories.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
          <datalist id="drink-units">
            {unitsList.map((u) => (
              <option key={u} value={u} />
            ))}
          </datalist>
        </div>

        {/* === TABLES === */}
        {activeTab === 'reassort' ? (
          <div>
            <div
              className="drinks-main"
              style={{
                display: 'grid',
                gridTemplateColumns: helpOpen ? 'minmax(0,1fr) 320px' : '1fr',
                gap: '1rem',
                alignItems: 'start',
              }}
            >
              <div className="drinks-table-container">
                <table className="table drinks-table">
                  <thead>
                    <tr>
                      <th>Boisson</th>
                      <th>Catégorie</th>
                      <th>Unité</th>
                      {reassortTab !== 'param' && <th>Restant</th>}
                      {reassortTab === 'saisie' && <th>État</th>}
                      {reassortTab === 'saisie' && <th>Suggestion</th>}
                      {reassortTab === 'param' && <th>Min</th>}
                      {reassortTab === 'param' && <th>Max</th>}
                      {reassortTab === 'param' && <th>Colis</th>}
                      {reassortTab === 'param' && <th>Actif</th>}
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((d) => (
                      <tr key={d.id}>
                        <td className="font-medium text-gray-900 name-cell" title={d.name}>
                          {editingId === d.id ? <input className="input" value={eName} onChange={(e) => setEName(e.target.value)} /> : d.name}
                        </td>

                        <td>
                          {editingId === d.id ? (
                            <input className="input" list="drink-categories" value={eCategory} onChange={(e) => setECategory(e.target.value)} />
                          ) : (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-50 text-blue-700">{d.category || '-'}</span>
                          )}
                        </td>

                        <td>
                          {editingId === d.id ? (
                            <div className="drinks-grid" style={{ gridTemplateColumns: '1fr auto' }}>
                              <input className="input" list="drink-units" value={eUnit} onChange={(e) => setEUnit(e.target.value)} />
                              <label className="form-check">
                                <input className="form-check-input" type="checkbox" checked={eActive} onChange={(e) => setEActive(e.target.checked)} /> actif
                              </label>
                            </div>
                          ) : (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-emerald-50 text-emerald-700">{d.unit || '-'}</span>
                          )}
                        </td>

                        {reassortTab !== 'param' && (
                          <td>
                            <input className="input" type="number" value={remaining[d.id] || 0} onChange={(e) => setRem(d.id, parseInt(e.target.value || '0') || 0)} />
                          </td>
                        )}

                        {reassortTab === 'saisie' && <td>{renderStatusBadge(getStatus(d.id))}</td>}

                        {reassortTab === 'saisie' && (
                          <td>
                            <span
                              className={`inline-flex items-center px-2 py-1 rounded-full text-xs ${
                                (repl[d.id]?.suggest || 0) > 0 ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'
                              }`}
                            >
                              {repl[d.id]?.suggest ?? '-'}
                            </span>
                          </td>
                        )}

                        {reassortTab === 'param' && (
                          <td>
                            <input
                              className="input"
                              type="number"
                              value={stock[d.id]?.min_qty ?? 0}
                              onChange={(e) => {
                                const mv = parseInt(e.target.value || '0') || 0
                                setStock((prev) => ({
                                  ...prev,
                                  [d.id]: { ...(prev[d.id] || { drink_id: d.id, min_qty: 0, max_qty: 0, pack_size: null, reorder_enabled: true }), min_qty: mv },
                                }))
                              }}
                              onBlur={(e) => updateStockField(d.id, { min_qty: parseInt(e.target.value || '0') || 0 })}
                            />
                          </td>
                        )}

                        {reassortTab === 'param' && (
                          <td>
                            <input
                              className="input"
                              type="number"
                              value={stock[d.id]?.max_qty ?? 0}
                              onChange={(e) => {
                                const mv = parseInt(e.target.value || '0') || 0
                                setStock((prev) => ({
                                  ...prev,
                                  [d.id]: { ...(prev[d.id] || { drink_id: d.id, min_qty: 0, max_qty: 0, pack_size: null, reorder_enabled: true }), max_qty: mv },
                                }))
                              }}
                              onBlur={(e) => updateStockField(d.id, { max_qty: parseInt(e.target.value || '0') || 0 })}
                            />
                          </td>
                        )}

                        {reassortTab === 'param' && (
                          <td>
                            <input
                              className="input"
                              type="number"
                              placeholder="—"
                              value={(stock[d.id]?.pack_size ?? '') as any}
                              onChange={(e) => {
                                const pv = parseInt(e.target.value || '')
                                const nextVal = Number.isFinite(pv) ? pv : null
                                setStock((prev) => ({
                                  ...prev,
                                  [d.id]: { ...(prev[d.id] || { drink_id: d.id, min_qty: 0, max_qty: 0, pack_size: null, reorder_enabled: true }), pack_size: nextVal as any },
                                }))
                              }}
                              onBlur={(e) => {
                                const pv = parseInt(e.target.value || '0') || 0
                                updateStockField(d.id, { pack_size: pv > 0 ? pv : (null as any) })
                              }}
                            />
                          </td>
                        )}

                        {reassortTab === 'param' && (
                          <td>
                            <label className="form-check">
                              <input
                                className="form-check-input"
                                type="checkbox"
                                checked={stock[d.id]?.reorder_enabled ?? true}
                                onChange={(e) => {
                                  const val = e.target.checked
                                  setStock((prev) => ({
                                    ...prev,
                                    [d.id]: { ...(prev[d.id] || { drink_id: d.id, min_qty: 0, max_qty: 0, pack_size: null, reorder_enabled: true }), reorder_enabled: val },
                                  }))
                                  updateStockField(d.id, { reorder_enabled: val })
                                }}
                              />{' '}
                              actif
                            </label>
                          </td>
                        )}

                        <td>
                          {editingId === d.id ? (
                            <div className="btn-group">
                              <button className="btn btn-sm btn-primary" onClick={() => saveEdit(d.id)}>
                                Enregistrer
                              </button>
                              <button className="btn btn-sm btn-outline" onClick={cancelEdit}>
                                Annuler
                              </button>
                            </div>
                          ) : (
                            <div className="btn-group">
                              {/* si tu ne veux jamais éditer depuis réassort -> supprime ce bouton */}
                              <button className="btn btn-sm btn-outline" onClick={() => startEdit(d)}>
                                Modifier
                              </button>
                              <button className="btn btn-sm btn-outline" onClick={() => removeDrink(d.id)}>
                                Supprimer
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}

                    {filtered.length === 0 && (
                      <tr>
                        <td className="p-4 text-gray-500" colSpan={reassortEmptyColSpan}>
                          Aucune boisson.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {helpOpen && (
                <aside
                  className="help-panel"
                  style={{
                    position: 'sticky',
                    top: '1rem',
                    width: '320px',
                    maxHeight: 'calc(100vh - 140px)',
                    overflowY: 'scroll',
                    overflowX: 'hidden',
                    contain: 'layout paint',
                    backfaceVisibility: 'hidden',
                    willChange: 'transform',
                    transform: 'translateZ(0)',
                  }}
                >
                  <div className="card" style={{ padding: '0.75rem' }}>
                    <div className="flex items-center justify-between" style={{ marginBottom: '.5rem' }}>
                      <h4 className="text-md font-semibold">Mode d'emploi</h4>
                      <button className="btn btn-sm btn-outline" onClick={() => setHelpOpen(false)}>
                        Fermer
                      </button>
                    </div>
                    <ol className="text-sm space-y-1" style={{ paddingLeft: '1rem', listStyle: 'decimal' }}>
                      <li>Filtrez par catégorie et recherchez une boisson.</li>
                      <li>Choisissez la cible (Max/Min) et l'arrondi (Colis/Aucun).</li>
                      <li>Activez l'option <b>auto</b> pour recalculer automatiquement.</li>
                      <li>
                        En sous-onglet <b>Saisie</b>, renseignez les <b>Restants</b> par boisson.
                      </li>
                      <li>
                        En sous-onglet <b>Paramètres</b>, réglez <b>Min/Max/Colis</b> et l'état <b>Actif</b>.
                      </li>
                      <li>Cliquez <b>Calculer</b> si l'auto n'est pas activé.</li>
                      <li>
                        Utilisez les <b>actions groupées</b> (réinitialiser, activer/désactiver, copier Min/Max).
                      </li>
                    </ol>

                    <div className="text-sm" style={{ marginTop: '.75rem' }}>
                      <div className="font-semibold" style={{ marginBottom: '.25rem' }}>
                        Légende
                      </div>
                      <div className="space-y-1">
                        <div>
                          État: {renderStatusBadge('critique')} <span className="text-gray-600">Restant &lt; Min</span>
                        </div>
                        <div>
                          État: {renderStatusBadge('a_completer')} <span className="text-gray-600">Restant &lt; Max</span>
                        </div>
                        <div>
                          État: {renderStatusBadge('ok')} <span className="text-gray-600">Restant ≥ Max</span>
                        </div>
                      </div>

                      <div className="font-semibold" style={{ marginTop: '.5rem', marginBottom: '.25rem' }}>
                        Astuce
                      </div>
                      <div className="text-gray-700">
                        Renseignez <b>Colis</b> pour arrondir automatiquement la suggestion au multiple du colis.
                      </div>
                    </div>
                  </div>
                </aside>
              )}
            </div>

            {!helpOpen && (
              <button
                className="btn btn-primary"
                aria-label="Afficher l'aide"
                onClick={() => setHelpOpen(true)}
                style={{ position: 'fixed', right: '20px', bottom: '20px', borderRadius: '9999px', width: '44px', height: '44px', zIndex: 1000 }}
              >
                <span aria-hidden="true">?</span>
              </button>
            )}
          </div>
        ) : (
          <div className="drinks-table-container">
            <table className="table drinks-table">
              <thead>
                <tr>
                  {isMass && <th><input type="checkbox" checked={sorted.length > 0 && sorted.every((d) => selected.has(d.id))} onChange={toggleSelectAll} /></th>}
                  <th>Boisson</th>
                  <th>Catégorie</th>
                  <th>Unité</th>
                  <th>Quantité</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((d) => (
                  <tr key={d.id}>
                    {isMass && <td><input type="checkbox" checked={selected.has(d.id)} onChange={() => toggleSelect(d.id)} /></td>}
                    <td className="font-medium text-gray-900 name-cell" title={d.name}>
                      {editingId === d.id ? <input className="input" value={eName} onChange={(e) => setEName(e.target.value)} /> : d.name}
                    </td>
                    <td>
                      {editingId === d.id ? (
                        <input className="input" list="drink-categories" value={eCategory} onChange={(e) => setECategory(e.target.value)} />
                      ) : (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-50 text-blue-700">{d.category || '-'}</span>
                      )}
                    </td>
                    <td>
                      {editingId === d.id ? (
                        <div className="drinks-grid" style={{ gridTemplateColumns: '1fr auto' }}>
                          <input className="input" list="drink-units" value={eUnit} onChange={(e) => setEUnit(e.target.value)} />
                          <label className="form-check">
                            <input className="form-check-input" type="checkbox" checked={eActive} onChange={(e) => setEActive(e.target.checked)} /> actif
                          </label>
                        </div>
                      ) : (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-emerald-50 text-emerald-700">{d.unit || '-'}</span>
                      )}
                    </td>
                    <td>
                      <div className="qty-group">
                        <button className="btn btn-sm btn-outline qty-btn" onClick={() => inc(d.id, -1)}>
                          -
                        </button>
                        <input
                          className="input qty-input"
                          value={counts[d.id] || 0}
                          onChange={(e) => {
                            const v = Math.max(0, parseInt(e.target.value || '0') || 0)
                            setCounts((prev) => ({ ...prev, [d.id]: v }))
                          }}
                        />
                        <button className="btn btn-sm btn-outline qty-btn" onClick={() => inc(d.id, +1)}>
                          +
                        </button>
                      </div>
                    </td>
                    <td>
                      {editingId === d.id ? (
                        <div className="btn-group">
                          <button className="btn btn-sm btn-primary" onClick={() => saveEdit(d.id)}>
                            Enregistrer
                          </button>
                          <button className="btn btn-sm btn-outline" onClick={cancelEdit}>
                            Annuler
                          </button>
                        </div>
                      ) : (
                        <div className="btn-group">
                          <button className="btn btn-sm btn-outline" onClick={() => startEdit(d)}>
                            Modifier
                          </button>
                          <button className="btn btn-sm btn-outline" onClick={() => removeDrink(d.id)}>
                            Supprimer
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}

                {filtered.length === 0 && (
                  <tr>
                    <td className="p-4 text-gray-500" colSpan={isMass ? 7 : 6}>
                      Aucune boisson.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
