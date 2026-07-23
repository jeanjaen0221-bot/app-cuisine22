import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fileDownload } from '../lib/api'
import { IncidentReport } from '../types'
import { Plus, Pencil, Trash2, FileText, Search } from 'lucide-react'

const formatDate = (dateString: string) => {
  if (!dateString) return ''
  const d = new Date(dateString)
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function GravityBadge({ value }: { value?: string }) {
  const v = (value || '').toLowerCase()
  const cls = v.includes('élevé') || v.includes('critique') || v === 'eleve'
    ? 'gravity-badge is-high'
    : v.includes('moyen')
    ? 'gravity-badge is-medium'
    : 'gravity-badge is-low'
  return <span className={cls}>{value || '—'}</span>
}

export default function IncidentList() {
  const [rows, setRows] = useState<IncidentReport[]>([])
  const [q, setQ] = useState('')

  async function load() {
    const r = await api.get('/api/incidents')
    setRows(r.data || [])
  }

  useEffect(() => {
    load().catch(() => {})
  }, [])

  async function del(id: string) {
    if (!confirm('Supprimer ce rapport d\'incident ?')) return
    await api.delete(`/api/incidents/${id}`)
    setRows(prev => prev.filter(r => r.id !== id))
  }

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (!s) return rows
    return rows.filter(r => {
      return (
        (r.client || '').toLowerCase().includes(s) ||
        (r.lieu || '').toLowerCase().includes(s) ||
        (r.recit_brut || '').toLowerCase().includes(s)
      )
    })
  }, [rows, q])

  return (
    <div className="container space-y-4">
      <div className="card">
        <div className="card-header">
          <div>Rapports d'incident</div>
          <div className="flex gap-2">
            <Link className="btn btn-sm btn-primary" to="/incident/new">
              <Plus className="w-4 h-4" /> Nouveau
            </Link>
          </div>
        </div>
        <div className="card-body space-y-3">
          <div className="input-group">
            <span className="input-group-text"><Search className="w-4 h-4" /></span>
            <input className="input" placeholder="Rechercher (client, lieu, récit)…" value={q} onChange={e => setQ(e.target.value)} />
          </div>

          <div className="table">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="text-left">Date</th>
                  <th className="text-left">Heure</th>
                  <th className="text-left">Client</th>
                  <th className="text-left">Lieu</th>
                  <th className="text-left">Gravité</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr><td colSpan={6} className="p-4 text-center text-gray-500">Aucun rapport</td></tr>
                ) : filtered.map(r => (
                  <tr key={r.id}>
                    <td>{formatDate(r.date)}</td>
                    <td>{(r.heure || '').slice(0,5)}</td>
                    <td className="font-medium">{r.client || '—'}</td>
                    <td>{r.lieu || '—'}</td>
                    <td><GravityBadge value={r.gravite} /></td>
                    <td className="text-right">
                      <div className="flex justify-end gap-2">
                        <Link className="btn btn-sm btn-primary" to={`/incident/${r.id}`}>
                          <Pencil className="w-4 h-4" /> Modifier
                        </Link>
                        <button className="btn btn-sm btn-outline" title="Télécharger le PDF" onClick={() => void fileDownload(`/api/incidents/${r.id}/pdf`, `plainte-${r.id}.pdf`)}>
                          <FileText className="w-4 h-4" />
                        </button>
                        <button className="btn btn-sm btn-outline res-delete-btn" title="Supprimer" onClick={() => del(r.id)}>
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
