import { useEffect, useState } from 'react'
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
            <Link to={date ? `/reservation/new?date=${encodeURIComponent(date)}` : "/reservation/new"} className="btn btn-sm"><Plus className="h-4 w-4"/> Nouvelle fiche</Link>
            <button className="btn btn-sm btn-outline" onClick={() => { if (!date) { alert('Sélectionnez une date'); return } fileDownload(`/api/reservations/day/${date}/pdf`) }}><Printer className="h-4 w-4"/> Export PDF du jour</button>
          </div>
        </div>
      </div>

      {/* Grille des réservations */}
      {rows.length === 0 ? (
        <div className="card">
          <div className="text-center p-4 text-gray-700">Aucune réservation trouvée</div>
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
                  {/* Résumé plats */}
              {Array.isArray(r.items) && r.items.length > 0 && (
                <div className="pt-1 border-t border-gray-100 mt-2 space-y-2 text-gray-800">
                  {(() => {
                    const list = r.items.filter(i => (i.type||'').toLowerCase().startsWith('entrée') && (i.quantity||0)>0)
                      .map(i => `${i.quantity}× ${i.name}`)
                    const head = list.slice(0,5)
                    const more = list.length > head.length
                    return (
                      <div>
                        <span className="section-label">Entrées</span>{' : '}
                        {list.length === 0 ? '-' : (
                          <ul className="menu-list">
                            {head.map((txt, idx) => (<li className="menu-line" key={`e-${idx}`}>{txt}</li>))}
                            {more && <li className="menu-more">…</li>}
                          </ul>
                        )}
                      </div>
                    )
                  })()}
                  {(() => {
                    const list = r.items.filter(i => (i.type||'').toLowerCase() === 'plat' && (i.quantity||0)>0)
                      .map(i => `${i.quantity}× ${i.name}`)
                    const head = list.slice(0,5)
                    const more = list.length > head.length
                    return (
                      <div>
                        <span className="section-label">Plats</span>{' : '}
                        {list.length === 0 ? '-' : (
                          <ul className="menu-list">
                            {head.map((txt, idx) => (<li className="menu-line" key={`p-${idx}`}>{txt}</li>))}
                            {more && <li className="menu-more">…</li>}
                          </ul>
                        )}
                      </div>
                    )
                  })()}
                  {(() => {
                    const list = r.items.filter(i => (i.type||'').toLowerCase() === 'dessert' && (i.quantity||0)>0)
                      .map(i => `${i.quantity}× ${i.name}`)
                    const head = list.slice(0,5)
                    const more = list.length > head.length
                    return (
                      <div>
                        <span className="section-label">Desserts</span>{' : '}
                        {list.length === 0 ? '-' : (
                          <ul className="menu-list">
                            {head.map((txt, idx) => (<li className="menu-line" key={`d-${idx}`}>{txt}</li>))}
                            {more && <li className="menu-more">…</li>}
                          </ul>
                        )}
                      </div>
                    )
                  })()}
                </div>
              )}
                  {/* Formule boisson */}
                  {r.drink_formula && (
                    <div className="flex items-center gap-2 text-gray-700">
                      <Wine className="w-4 h-4 text-gray-500" />
                      <span className="badge badge-secondary drink-badge" title="Formule boisson">{r.drink_formula}</span>
                    </div>
                  )}
                  {/* Notes */}
                  {r.notes && (
                    <div className="text-gray-700">
                      <span className="section-label">Notes</span>{': '}
                      <span className="text-gray-700 note-preview">{cleanNotesPreview(r.notes, 160)}</span>
                    </div>
                  )}
                  {/* Allergènes */}
                  {splitAllergens(r.allergens).length > 0 && (
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      {splitAllergens(r.allergens).map(a => {
                        const meta = allergenMeta[a]
                        const label = meta?.label || a
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
      )}
    </div>
  )
}
