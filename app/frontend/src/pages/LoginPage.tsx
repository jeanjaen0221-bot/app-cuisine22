import { FormEvent, useState } from 'react'
import { LockKeyhole } from 'lucide-react'
import { api } from '../lib/api'

type Props = { setupRequired: boolean, onAuthenticated: (token: string) => void }

export default function LoginPage({ setupRequired, onAuthenticated }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (setupRequired && password !== confirmation) return setError('Les mots de passe ne correspondent pas.')
    setSaving(true)
    try {
      const response = await api.post(`/api/auth/${setupRequired ? 'setup' : 'login'}`, { email, password })
      onAuthenticated(response.data.access_token)
    } catch (err: any) {
      setError(err.userMessage || 'Impossible de vous authentifier.')
    } finally { setSaving(false) }
  }

  return <main className="auth-page"><form className="auth-card" onSubmit={submit}>
    <div className="auth-icon"><LockKeyhole size={28} /></div>
    <h1>Fiche Cuisine</h1>
    <p>{setupRequired ? 'Créez le premier compte administrateur.' : 'Connectez-vous pour accéder à votre espace.'}</p>
    <label className="label" htmlFor="auth-email">Adresse e-mail</label>
    <input id="auth-email" className="input" type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} required />
    <label className="label" htmlFor="auth-password">Mot de passe</label>
    <input id="auth-password" className="input" type="password" autoComplete={setupRequired ? 'new-password' : 'current-password'} minLength={12} value={password} onChange={e => setPassword(e.target.value)} required />
    {setupRequired && <><label className="label" htmlFor="auth-confirmation">Confirmer le mot de passe</label><input id="auth-confirmation" className="input" type="password" autoComplete="new-password" minLength={12} value={confirmation} onChange={e => setConfirmation(e.target.value)} required /></>}
    {error && <p className="auth-error" role="alert">{error}</p>}
    <button className="btn btn-primary" disabled={saving}>{saving ? 'Veuillez patienter…' : setupRequired ? 'Créer mon compte' : 'Se connecter'}</button>
    {setupRequired && <small>Utilisez au moins 12 caractères.</small>}
  </form></main>
}
