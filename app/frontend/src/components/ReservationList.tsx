import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fileDownload } from '../lib/api'
import { Reservation } from '../types'
import { Plus, Printer, Pencil, Filter, Search, User, CalendarDays, Clock, Users, Wine } from 'lucide-react'

// Fonction pour formater la date au format français
const formatDate = (dateString: string) => {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  });
};

// Fonction pour formater l'heure
const formatTime = (timeString: string) => {
  if (!timeString) return '';
  const [hours, minutes] = timeString.split(':');
  return `${hours}:${minutes}`;
};

// Nettoyer un aperçu court des notes (enlever balises et couper)
const cleanNotesPreview = (s: string | undefined, max = 120) => {
  if (!s) return '';
  return s
    .replace(/\[color=[^\]]+\]|\[\/color\]|\[size=[^\]]+\]|\[\/size\]/g, '')
    .replace(/\*\*|_/g, '')
    .replace(/\n+/g, ' ')
    .trim()
    .slice(0, max);
};

const splitAllergens = (csv?: string) => (csv ? csv.split(',').map(s=>s.trim()).filter(Boolean) : []);
type AllergenMeta = { key: string; label: string; icon_url?: string }

function drinkVariantOf(label?: string): string {
  const s = (label || '').toLowerCase()
  if (!s || s === 'sans formule') return 'is-none'
  if (s === 'à la carte' || s === 'a la carte') return 'is-a-la-carte'
  if (s.includes('sans alcool') && s.includes('champ')) return 'is-na-champ'
  if (s.includes('avec alcool') && s.includes('champ')) return 'is-alcool-champ'
  if (s.includes('sans alcool') && s.includes('cava')) return 'is-na-cava'
  if (s.includes('avec alcool') && s.includes('cava')) return 'is-alcool-cava'
  if (s.includes('sans alcool')) return 'is-na'
  if (s.includes('avec alcool')) return 'is-alcool'
  return 'is-default'
}

function DrinkBadge({ value }: { value?: string }) {
  if (!value) return <span className="drink-badge is-none">—</span>
  const variant = drinkVariantOf(value)
  return (
    <span className={`drink-badge ${variant}`}>
      <Wine />
      <span className="drink-text">{value}</span>
    </span>
  )
}
const monthKey = (s: string) => String(s).slice(0, 7)
const monthLabel = (key: string) => {
  const [y, m] = key.split('-')
  const d = new Date(Number(y), Number(m) - 1, 1)
  return d.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
}

export default function ReservationList() {
  const [rows, setRows] = useState<Reservation[]>([])
  const [allRows, setAllRows] = useState<Reservation[]>([])
  const [q, setQ] = useState('')
  const [date, setDate] = useState<string>('')
  const [allergenMeta, setAllergenMeta] = useState<Record<string, AllergenMeta>>({})
  const [months, setMonths] = useState<{ key: string; label: string }[]>([])
  const [selectedMonth, setSelectedMonth] = useState<string>('')
  const [expanded, setExpanded] = useState<Record<string, { entries?: boolean; mains?: boolean; desserts?: boolean; notes?: boolean; allergens?: boolean }>>({})
  const [viewMode, setViewMode] = useState<'cards' | 'compact'>('cards')

  function toggle(resId: string, key: keyof NonNullable<(typeof expanded)[string]>) {
    setExpanded(prev => ({ ...prev, [resId]: { ...prev[resId], [key]: !prev[resId]?.[key] } }))
  }

  const allergenFallback: Record<string, string> = useMemo(() => ({
    gl: 'Gluten',
    la: 'Lait',
    oe: 'Oeufs',
    ar: 'Arachide',
    so: 'Soja',
    fr: 'Fruits à coque',
    se: 'Sésame',
    su: 'Sulfites',
    po: 'Poisson',
    cr: 'Crustacés',
    mo: 'Mollusques',
    ce: 'Céleri',
    lu: 'Lupin',
    mu: 'Moutarde',
    ai: 'Ail',
  }), [])

  const friendlyAllergen = (key: string) => allergenMeta[key]?.label || allergenFallback[key] || key

  async function load() {
    const params: any = {}
    if (q) params.q = q
    // Fetch only upcoming on server; apply date filter client-side
    const res = await api.get('/api/reservations/upcoming', { params })
    const all: Reservation[] = res.data
    setAllRows(all)
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const res = await api.get('/api/allergens')
        if (!mounted) return
        const map: Record<string, AllergenMeta> = {}
        for (const a of (Array.isArray(res.data) ? res.data : [])) {
          if (!a?.key) continue
          map[a.key] = { key: a.key, label: a.label || a.key, icon_url: a.icon_url || undefined }
        }
        setAllergenMeta(map)
      } catch {}
    })()
    return () => { mounted = false }
  }, [])
  useEffect(() => {
    const t = setTimeout(() => { load() }, 300)
    return () => clearTimeout(t)
  }, [q, date])
  useEffect(() => {
    const keys = Array.from(new Set(allRows.map(r => monthKey(r.service_date)))).sort()
    const list = keys.map(k => ({ key: k, label: monthLabel(k) }))
    setMonths(list)
    const currentKey = new Date().toISOString().slice(0,7)
    if (!selectedMonth || !list.find(m => m.key === selectedMonth)) {
      setSelectedMonth(list.find(m => m.key === currentKey)?.key || (list[list.length - 1]?.key || ''))
    }
    const base = allRows.filter(r => !selectedMonth || monthKey(r.service_date) === selectedMonth)
    const filtered = date ? base.filter(r => String(r.service_date).slice(0,10) === date) : base
    setRows(filtered)
  }, [allRows, selectedMonth, date])

  return (
    <div className="space-y-6">
      <div className="card">
        <div className="card-body">
          <div className="flex flex-wrap gap-2">
            {months.map(m => (
              <button
                key={m.key}
                className={`btn btn-sm ${selectedMonth === m.key ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => setSelectedMonth(m.key)}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
      </div>
      {/* Barre de filtres */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <input className="input" placeholder="Rechercher un client" value={q} onChange={e=>setQ(e.target.value)} />
            <input type="date" className="input" value={date} onChange={e=>setDate(e.target.value)} />
            <button className="btn btn-sm btn-outline" onClick={load}><Filter className="h-4 w-4"/> Filtrer</button>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1" title="Mode d'affichage">
              <button className={`btn btn-sm ${viewMode==='cards'?'btn-primary':'btn-outline'}`} onClick={()=>setViewMode('cards')}>Cartes</button>
              <button className={`btn btn-sm ${viewMode==='compact'?'btn-primary':'btn-outline'}`} onClick={()=>setViewMode('compact')}>Liste</button>
            </div>
            <Link to={date ? `/reservation/new?date=${encodeURIComponent(date)}` : "/reservation/new"} className="btn btn-sm"><Plus className="h-4 w-4"/> Nouvelle fiche</Link>
            <button className="btn btn-sm btn-outline" onClick={() => { if (!date) { alert('Sélectionnez une date'); return } fileDownload(`/api/reservations/day/${date}/pdf`) }}><Printer className="h-4 w-4"/> Export PDF du jour</button>
          </div>
        </div>
      </div>

      {/* Grille/Table des réservations */}
      {rows.length === 0 ? (
        <div className="card">
          <div className="text-center p-4 text-gray-700">Aucune réservation trouvée</div>
        </div>
      ) : (
        viewMode === 'compact' ? (
          <div className="card">
            <div className="card-body overflow-auto">
              <table className="table w-full">
                <thead>
                  <tr>
                    <th>Client</th>
                    <th>Date</th>
                    <th>Heure</th>
                    <th>Couverts</th>
                    <th>Boisson</th>
                    <th>Menu (résumé)</th>
                    <th style={{width:120}}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(r => {
                    const e = r.items.filter(i => (i.type||'').toLowerCase().startsWith('entrée')).length
                    const p = r.items.filter(i => (i.type||'').toLowerCase() === 'plat').length
                    const d = r.items.filter(i => (i.type||'').toLowerCase() === 'dessert').length
                    const firstNames = r.items.map(i => `${i.quantity}× ${i.name}`).slice(0, 6).join(', ')
                    const pdfOk = r.last_pdf_exported_at && new Date(r.last_pdf_exported_at) >= new Date(r.updated_at)
                    return (
                      <tr key={r.id}>
                        <td className="capitalize">{r.client_name}</td>
                        <td>{formatDate(r.service_date)}</td>
                        <td>{formatTime(r.arrival_time)}</td>
                        <td>{r.pax}</td>
                        <td><DrinkBadge value={r.drink_formula} /></td>
                        <td>
                          <div className="text-gray-800">
                            <div className="text-sm">E {e} / P {p} / D {d}</div>
                            {firstNames && (
                              <div className="text-xs text-gray-600 line-clamp-2" title={firstNames}>{firstNames}</div>
                            )}
                          </div>
                        </td>
                        <td>
                          {pdfOk && (
                            <div className="mb-1"><span className="pdf-badge ok" title={`Exporté le ${new Date(r.last_pdf_exported_at as string).toLocaleString('fr-FR')}`}>PDF à jour</span></div>
                          )}
                          <div className="flex items-center gap-2">
                            <Link to={`/reservation/${r.id}`} className="btn btn-sm btn-outline"><Pencil className="w-4 h-4"/> Modifier</Link>
                            <button onClick={() => fileDownload(`/api/reservations/${r.id}/pdf`)} className="btn btn-sm btn-outline"><Printer className="w-4 h-4"/> PDF</button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {rows.map(r => (
            <div key={r.id} className="card card-hoverable reservation-card">
              <div className="card-header">
                <h3 className="text-lg font-medium flex items-center gap-2 capitalize">
                  <User className="w-4 h-4 text-gray-600" />
                  {r.client_name}
                </h3>
                <div className="flex items-center gap-2">
                  {r.last_pdf_exported_at && new Date(r.last_pdf_exported_at) >= new Date(r.updated_at) && (
                    <span className="pdf-badge ok" title={`Exporté le ${new Date(r.last_pdf_exported_at).toLocaleString('fr-FR')}`}>PDF à jour</span>
                  )}
                  <span className={`status-badge ${
                    r.status === 'confirmed' ? 'is-confirmed' :
                    r.status === 'printed' ? 'is-printed' :
                    'is-draft'
                  }`}>
                    {r.status === 'confirmed' ? 'Confirmée' : r.status === 'printed' ? 'Imprimée' : 'Brouillon'}
                  </span>
                  {r.final_version && (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-red-50 text-red-700">Version finale</span>
                  )}
                </div>
              </div>
              <div className="card-body">
                <div className="space-y-3">
                  <div className="meta-list">
                    <div className="meta-item"><CalendarDays className="w-4 h-4" /><span>{formatDate(r.service_date)}</span></div>
                    <div className="meta-item"><Clock className="w-4 h-4" /><span>{formatTime(r.arrival_time)}</span></div>
                    <div className="meta-item"><Users className="w-4 h-4" /><span>{r.pax} couvert{r.pax > 1 ? 's' : ''}</span></div>
                  </div>
                  <div className="card-sep" />
                <div className="res-sections">
                  <div className="res-col res-col-main">
                  {/* Résumé plats */}
              {Array.isArray(r.items) && r.items.length > 0 && (
                <div className="pt-1 border-t border-gray-100 mt-2 space-y-2 text-gray-800">
                  {(() => {
                    const list = r.items.filter(i => (i.type||'').toLowerCase().startsWith('entrée') && (i.quantity||0)>0)
                      .map(i => `${i.quantity}× ${i.name}`)
                    const isOpen = !!expanded[r.id]?.entries
                    const shown = isOpen ? list : list.slice(0,5)
                    const more = list.length > shown.length
                    if (list.length === 0) return null
                    return (
                      <div className="res-block">
                        <span className="section-label">Entrées</span> <span className="section-count">({list.length})</span>{' : '}
                        <>
                          <ul className="menu-list">
                            {shown.map((txt, idx) => (<li className="menu-line" key={`e-${idx}`}>{txt}</li>))}
                          </ul>
                          { (more || isOpen) && (
                            <button className="section-toggle" onClick={() => toggle(r.id, 'entries')}>
                              {isOpen ? 'Réduire' : 'Voir tout'}
                            </button>
                          )}
                        </>
                      </div>
                    )
                  })()}
                  {(() => {
                    const list = r.items.filter(i => (i.type||'').toLowerCase() === 'plat' && (i.quantity||0)>0)
                      .map(i => `${i.quantity}× ${i.name}`)
                    const isOpen = !!expanded[r.id]?.mains
                    const shown = isOpen ? list : list.slice(0,5)
                    const more = list.length > shown.length
                    if (list.length === 0) return null
                    return (
                      <div className="res-block">
                        <span className="section-label">Plats</span> <span className="section-count">({list.length})</span>{' : '}
                        <>
                          <ul className="menu-list">
                            {shown.map((txt, idx) => (<li className="menu-line" key={`p-${idx}`}>{txt}</li>))}
                          </ul>
                          { (more || isOpen) && (
                            <button className="section-toggle" onClick={() => toggle(r.id, 'mains')}>
                              {isOpen ? 'Réduire' : 'Voir tout'}
                            </button>
                          )}
                        </>
                      </div>
                    )
                  })()}
                  {(() => {
                    const list = r.items.filter(i => (i.type||'').toLowerCase() === 'dessert' && (i.quantity||0)>0)
                      .map(i => `${i.quantity}× ${i.name}`)
                    const isOpen = !!expanded[r.id]?.desserts
                    const shown = isOpen ? list : list.slice(0,5)
                    const more = list.length > shown.length
                    if (list.length === 0) return null
                    return (
                      <div className="res-block">
                        <span className="section-label">Desserts</span> <span className="section-count">({list.length})</span>{' : '}
                        <>
                          <ul className="menu-list">
                            {shown.map((txt, idx) => (<li className="menu-line" key={`d-${idx}`}>{txt}</li>))}
                          </ul>
                          { (more || isOpen) && (
                            <button className="section-toggle" onClick={() => toggle(r.id, 'desserts')}>
                              {isOpen ? 'Réduire' : 'Voir tout'}
                            </button>
                          )}
                        </>
                      </div>
                    )
                  })()}
                </div>
              )}
                  </div>
                  <div className="res-col res-col-aside">
                  {/* Formule boisson */}
                  <DrinkBadge value={r.drink_formula} />
                  {/* Notes */}
                  {r.notes && (
                    <div className="text-gray-700">
                      <span className="section-label">Notes</span>{': '}
                      {(() => {
                        const lines = String(r.notes || '')
                          .split(/\r?\n|\s*-\s+/g)
                          .map(s => s.trim())
                          .filter(Boolean)
                        const isOpen = !!expanded[r.id]?.notes
                        const shown = isOpen ? lines : lines.slice(0, 5)
                        return lines.length === 0 ? (
                          <>-</>
                        ) : (
                          <>
                            <ul className="menu-list note-list">
                              {shown.map((l, i) => (<li key={`n-${i}`} className="menu-line">{l}</li>))}
                            </ul>
                            {(lines.length > 5 || isOpen) && (
                              <button className="section-toggle" onClick={() => toggle(r.id, 'notes')}>
                                {isOpen ? 'Réduire' : 'Voir tout'}
                              </button>
                            )}
                          </>
                        )
                      })()}
                    </div>
                  )}
                  {/* Allergènes */}
                  {/* Allergènes déplacés pleine largeur sous la grille */}
                  </div>
                </div>
                {/* Allergènes en pleine largeur */}
                {splitAllergens(r.allergens).length > 0 && (
                  <div className="allergens-block res-row-full">
                    <div className="section-label w-full">Allergènes</div>
                    {splitAllergens(r.allergens).map(a => {
                      const meta = allergenMeta[a]
                      const label = friendlyAllergen(a)
                      const icon = meta?.icon_url || `/backend-assets/allergens/${a}.png`
                      return (
                        <span key={a} className="allergen-chip allergen-chip-card">
                          <img
                            src={icon}
                            alt={label}
                            title={label}
                            className="allergen-icon"
                            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                          />
                          <span className="allergen-chip-label">{label}</span>
                        </span>
                      )
                    })}
                  </div>
                )}
                </div>
              </div>
              <div className="card-footer">
                <div className="flex items-center gap-2">
                  <Link to={`/reservation/${r.id}`} className="btn btn-sm btn-outline"><Pencil className="w-4 h-4"/> Modifier</Link>
                  <button onClick={() => fileDownload(`/api/reservations/${r.id}/pdf`)} className="btn btn-sm btn-outline"><Printer className="w-4 h-4"/> PDF</button>
                </div>
              </div>
            </div>
          ))}
        </div>
        )
      )}
    </div>
  )
}
