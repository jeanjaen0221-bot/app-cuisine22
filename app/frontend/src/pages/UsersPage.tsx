import { FormEvent, useEffect, useState } from 'react'
import { KeyRound, Plus, Save, ShieldCheck, Trash2, UserRound } from 'lucide-react'
import { api } from '../lib/api'
import { AppUser } from '../types'

const accessOptions = [
  ['dashboard', 'Tableau de bord'], ['reservations', 'Fiches cuisine'], ['rooftop', 'Rooftop'], ['floorplan', 'Plan de salle'], ['menu', 'Base de plats'], ['orders', 'Commandes & achats'], ['suppliers', 'Fournisseurs'], ['billing', 'Facturation'], ['incidents', 'Plaintes'], ['settings', 'Paramètres'], ['users', 'Utilisateurs'],
]
const blank = () => ({ email: '', password: '', role: 'member', permissions: ['rooftop'] as string[] })

export default function UsersPage() {
  const [users, setUsers] = useState<AppUser[]>([])
  const [form, setForm] = useState(blank)
  const [editing, setEditing] = useState<AppUser | null>(null)
  const [message, setMessage] = useState('')
  const load = async () => setUsers((await api.get('/api/auth/users')).data)
  useEffect(() => { void load() }, [])
  const togglePermission = (permission: string) => setForm(value => ({ ...value, permissions: value.permissions.includes(permission) ? value.permissions.filter(item => item !== permission) : [...value.permissions, permission] }))
  async function submit(event: FormEvent) {
    event.preventDefault(); setMessage('')
    try {
      if (editing) await api.put(`/api/auth/users/${editing.id}`, { role: form.role, permissions: form.permissions, ...(form.password ? { password: form.password } : {}) })
      else await api.post('/api/auth/users', form)
      await load(); setEditing(null); setForm(blank()); setMessage('Utilisateurs mis à jour.')
    } catch (error: any) { setMessage(error.userMessage || 'Impossible d’enregistrer cet utilisateur.') }
  }
  return <div className="users-page container"><header className="users-hero"><div><p className="eyebrow">Administration</p><h1>Utilisateurs & accès</h1><p>Créez les comptes de l’équipe et choisissez exactement les espaces auxquels ils ont accès.</p></div><ShieldCheck size={42} /></header><div className="users-layout"><section className="card users-list"><h2>Comptes actifs</h2>{users.map(user => <article key={user.id} className="user-row"><div className="user-avatar"><UserRound size={18} /></div><div><strong>{user.email}</strong><small>{user.role === 'admin' ? 'Administrateur · accès complet' : `${user.permissions.length} accès attribué(s)`}</small></div><div className="user-row-actions"><button className="btn btn-outline btn-sm" onClick={() => { setEditing(user); setForm({ email: user.email, password: '', role: user.role, permissions: user.permissions }) }}>Modifier</button><button className="btn btn-ghost btn-icon" aria-label="Supprimer" onClick={async () => { if (confirm(`Supprimer ${user.email} ?`)) { try { await api.delete(`/api/auth/users/${user.id}`); await load() } catch (error: any) { setMessage(error.userMessage || 'Suppression impossible.') } } }}><Trash2 size={16} /></button></div></article>)}</section><section className="card user-form"><header><div><p className="eyebrow">{editing ? 'Modifier le compte' : 'Nouveau compte'}</p><h2>{editing ? editing.email : 'Inviter un utilisateur'}</h2></div>{editing ? <button className="btn btn-ghost btn-sm" onClick={() => { setEditing(null); setForm(blank()) }}>Annuler</button> : <Plus />}</header><form onSubmit={submit}><label>Adresse e-mail<input className="input" type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} disabled={!!editing} required /></label><label><span>Mot de passe {editing && <small>(laisser vide pour ne pas le modifier)</small>}</span><input className="input" type="password" minLength={12} value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required={!editing} /></label><div className="role-picker"><button type="button" className={form.role === 'member' ? 'active' : ''} onClick={() => setForm({ ...form, role: 'member' })}>Accès personnalisé</button><button type="button" className={form.role === 'admin' ? 'active' : ''} onClick={() => setForm({ ...form, role: 'admin' })}>Administrateur</button></div>{form.role === 'member' ? <fieldset><legend>Espaces autorisés</legend><div className="permission-grid">{accessOptions.map(([key, label]) => <label key={key} className="permission-choice"><input type="checkbox" checked={form.permissions.includes(key)} onChange={() => togglePermission(key)} />{label}</label>)}</div></fieldset> : <p className="admin-note"><ShieldCheck size={16} /> L’administrateur a accès à tous les espaces, y compris la gestion des utilisateurs.</p>}{message && <p className="auth-error">{message}</p>}<button className="btn btn-primary"><Save size={17} /> {editing ? 'Enregistrer les accès' : 'Créer le compte'}</button></form></section></div></div>
}
