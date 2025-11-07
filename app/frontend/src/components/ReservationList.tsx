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

export default function ReservationList() {
  const [rows, setRows] = useState<Reservation[]>([])
  const [q, setQ] = useState('')
  const [date, setDate] = useState<string>('')

  async function load() {
    const params: any = {}
    if (q) params.q = q
    // Fetch only upcoming on server; apply date filter client-side
    const res = await api.get('/api/reservations/upcoming', { params })
    const all: Reservation[] = res.data
    const filtered = date ? all.filter(r => String(r.service_date).slice(0,10) === date) : all
    setRows(filtered)
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    const t = setTimeout(() => { load() }, 300)
    return () => clearTimeout(t)
  }, [q, date])

  return (
    <div className="space-y-6">
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
            <div key={r.id} className="card card-hoverable">
              <div className="card-header">
                <h3 className="text-lg font-medium flex items-center gap-2">
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
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-gray-700">
                    <CalendarDays className="w-4 h-4 text-gray-500" />
                    <span>{formatDate(r.service_date)}</span>
                  </div>
                  <div className="flex items-center gap-2 text-gray-700">
                    <Clock className="w-4 h-4 text-gray-500" />
                    <span>{formatTime(r.arrival_time)}</span>
                  </div>
                  <div className="flex items-center gap-2 text-gray-700">
                    <Users className="w-4 h-4 text-gray-500" />
                    <span>{r.pax} couvert{r.pax > 1 ? 's' : ''}</span>
                  </div>
                  {/* Résumé plats */}
                  {Array.isArray(r.items) && r.items.length > 0 && (
                    <div className="pt-1 border-t border-gray-100 mt-2 space-y-1 text-gray-800">
                      <div>
                        <span className="font-medium">Entrées:</span>{' '}
                        {(() => {
                          const list = r.items.filter(i => (i.type||'').toLowerCase().startsWith('entrée') && (i.quantity||0)>0)
                            .map(i => `${i.quantity}× ${i.name}`);
                          const head = list.slice(0,3).join(', ');
                          return head || '-';
                        })()}
                        {r.items.filter(i => (i.type||'').toLowerCase().startsWith('entrée') && (i.quantity||0)>0).length > 3 ? '…' : ''}
                      </div>
                      <div>
                        <span className="font-medium">Plats:</span>{' '}
                        {(() => {
                          const list = r.items.filter(i => (i.type||'').toLowerCase() === 'plat' && (i.quantity||0)>0)
                            .map(i => `${i.quantity}× ${i.name}`);
                          const head = list.slice(0,3).join(', ');
                          return head || '-';
                        })()}
                        {r.items.filter(i => (i.type||'').toLowerCase() === 'plat' && (i.quantity||0)>0).length > 3 ? '…' : ''}
                      </div>
                      <div>
                        <span className="font-medium">Desserts:</span>{' '}
                        {(() => {
                          const list = r.items.filter(i => (i.type||'').toLowerCase() === 'dessert' && (i.quantity||0)>0)
                            .map(i => `${i.quantity}× ${i.name}`);
                          const head = list.slice(0,3).join(', ');
                          return head || '-';
                        })()}
                        {r.items.filter(i => (i.type||'').toLowerCase() === 'dessert' && (i.quantity||0)>0).length > 3 ? '…' : ''}
                      </div>
                    </div>
                  )}
                  {/* Formule boisson */}
                  {r.drink_formula && (
                    <div className="flex items-center gap-2 text-gray-700">
                      <Wine className="w-4 h-4 text-gray-500" />
                      <span className="truncate max-w-full">{r.drink_formula}</span>
                    </div>
                  )}
                  {/* Notes */}
                  {r.notes && (
                    <div className="text-gray-700">
                      <span className="font-medium">Notes:</span>{' '}
                      <span className="text-gray-700">{cleanNotesPreview(r.notes)}</span>
                    </div>
                  )}
                  {/* Allergènes */}
                  {splitAllergens(r.allergens).length > 0 && (
                    <div className="space-x-1 space-y-1 pt-1">
                      {splitAllergens(r.allergens).map(a => (
                        <span key={a} className="inline-block align-middle bg-red-50 text-red-700 text-xs px-2 py-1 rounded">{a}</span>
                      ))}
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
