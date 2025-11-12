import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { Note } from '../types'
import { MessageSquare, X, Plus, Pencil, Trash2, Save, User, Clock } from 'lucide-react'

export default function NotesWidget() {
  const [open, setOpen] = useState(false)
  const [notes, setNotes] = useState<Note[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const [newContent, setNewContent] = useState('')
  const [editing, setEditing] = useState<Record<string, { name: string; content: string }>>({})

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/notes')
      setNotes(Array.isArray(res.data) ? res.data : [])
    } catch (e: any) {
      setError(e?.userMessage || 'Erreur de chargement')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) load()
  }, [open])

  async function addNote() {
    const name = newName.trim()
    const content = newContent.trim()
    if (!name || !content) return
    setError(null)
    try {
      await api.post('/api/notes', { name, content })
      setNewName('')
      setNewContent('')
      await load()
    } catch (e: any) {
      setError(e?.userMessage || 'Erreur lors de l\'ajout')
    }
  }

  async function saveNote(id: string) {
    const name = (editing[id]?.name ?? '').trim()
    const content = (editing[id]?.content ?? '').trim()
    if (!name || !content) return
    setError(null)
    try {
      await api.put(`/api/notes/${id}`, { name, content })
      setEditing(prev => { const n = { ...prev }; delete n[id]; return n })
      await load()
    } catch (e: any) {
      setError(e?.userMessage || 'Erreur lors de la sauvegarde')
    }
  }

  async function deleteNote(id: string) {
    setError(null)
    try {
      await api.delete(`/api/notes/${id}`)
      await load()
    } catch (e: any) {
      setError(e?.userMessage || 'Erreur lors de la suppression')
    }
  }

  const hasEditing = useMemo(() => Object.keys(editing).length > 0, [editing])

  const fmt = (iso: string) => {
    try { return new Date(iso).toLocaleString('fr-FR') } catch { return iso }
  }
  const initials = (name: string) => {
    const n = (name || '').trim().split(/\s+/).filter(Boolean)
    if (n.length === 0) return '?'
    if (n.length === 1) return n[0].slice(0,2).toUpperCase()
    return (n[0][0] + n[1][0]).toUpperCase()
  }

  return (
    <>
      <div style={{ position: 'fixed', bottom: 16, right: 16, zIndex: 1000 }}>
        <button
          className={`btn ${open ? '' : 'btn-primary'} rounded-full px-3 py-3 notes-fab`}
          onClick={() => setOpen(v => !v)}
          aria-label={open ? 'Fermer les notes' : 'Ouvrir les notes'}
        >
          {open ? <X className="w-5 h-5"/> : <MessageSquare className="w-5 h-5"/>}
        </button>
      </div>

      {open && (
        <div style={{ position: 'fixed', bottom: 80, right: 16, zIndex: 1000, width: '22rem', maxWidth: '90vw' }}>
          <div className="notes-theme">
          <div className="card notes-panel">
            <div className="card-header">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-semibold notes-title">Notes</h3>
                <button className="btn btn-sm" onClick={() => setOpen(false)} aria-label="Fermer">
                  <X className="w-4 h-4"/>
                </button>
              </div>
            </div>
            <div className="card-body space-y-3 notes-body">
              {error && <div className="text-sm text-red-600">{error}</div>}
              {loading && <div className="text-sm text-gray-600">Chargement…</div>}

              <div className="notes-scroll">
                <div className="notes-section-title">Historique</div>
                <div className="space-y-2">
                {notes.map(n => (
                  <div key={n.id} className="notes-item">
                    {editing[n.id] !== undefined ? (
                      <div className="space-y-2">
                        <input
                          className="input w-full"
                          placeholder="Prénom"
                          value={editing[n.id].name}
                          onChange={e => setEditing(prev => ({ ...prev, [n.id]: { ...prev[n.id], name: e.target.value } }))}
                        />
                        <textarea
                          className="input w-full h-24"
                          value={editing[n.id].content}
                          onChange={e => setEditing(prev => ({ ...prev, [n.id]: { ...prev[n.id], content: e.target.value } }))}
                        />
                        <div className="flex items-center justify-end gap-2">
                          <button className="btn btn-sm" onClick={() => saveNote(n.id)}>
                            <Save className="w-4 h-4"/> Sauvegarder
                          </button>
                          <button className="btn btn-sm btn-outline" onClick={() => setEditing(prev => { const x = { ...prev }; delete x[n.id]; return x })}>
                            Annuler
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <div className="notes-item-header">
                          <div className="notes-item-author">
                            <div className="notes-avatar">{initials(n.name)}</div>
                            <div>
                              <div className="notes-author-name">{n.name}</div>
                              <div className="notes-meta"><Clock className="w-3 h-3"/> {fmt(n.updated_at)}</div>
                            </div>
                          </div>
                          <div className="notes-actions">
                            <button className="btn btn-ghost btn-sm" title="Éditer" onClick={() => setEditing(prev => ({ ...prev, [n.id]: { name: n.name, content: n.content } }))}>
                              <Pencil className="w-4 h-4"/>
                            </button>
                            <button className="btn btn-ghost btn-sm" title="Supprimer" onClick={() => deleteNote(n.id)}>
                              <Trash2 className="w-4 h-4"/>
                            </button>
                          </div>
                        </div>
                        <div className="notes-content">{n.content}</div>
                      </div>
                    )}
                  </div>
                ))}
                {notes.length === 0 && !loading && (
                  <div className="text-sm text-gray-600">Aucune note pour l'instant.</div>
                )}
                </div>
              </div>

              <div className="notes-composer">
                <div className="notes-section-title">Nouvelle note</div>
                <div className="notes-form space-y-2">
                  <div className="form-group">
                    <div className="label">Prénom</div>
                    <div className="input-group">
                      <span className="input-group-text"><User className="w-4 h-4"/></span>
                      <input
                        className="input"
                        placeholder="Prénom (obligatoire)"
                        value={newName}
                        onChange={e => setNewName(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="form-group">
                    <div className="label">Message</div>
                    <textarea
                      className="input w-full h-24"
                      placeholder="Contenu de la note (obligatoire)"
                      value={newContent}
                      onChange={e => setNewContent(e.target.value)}
                    />
                  </div>
                  <div className="flex justify-end">
                    <button className="btn btn-primary btn-sm" onClick={addNote} disabled={!newName.trim() || !newContent.trim()}>
                      <Plus className="w-4 h-4"/> Envoyer
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          </div>
        </div>
      )}
    </>
  )
}
