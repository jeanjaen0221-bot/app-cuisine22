import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, Echec, messageErreur } from '../api'
import type { Client } from '../types'

type Props = {
  valeur: { id: string; nom: string } | null
  surChoix: (client: { id: string; nom: string } | null) => void
  desactive?: boolean
}

/** Chercher un client existant, ou le créer sans quitter la fiche. */
export default function ChoixClient({ valeur, surChoix, desactive }: Props) {
  const [q, setQ] = useState('')
  const [resultats, setResultats] = useState<Client[]>([])
  const [creation, setCreation] = useState(false)
  const [nouveau, setNouveau] = useState({ type: 'particulier', nom: '', email: '', telephone: '' })
  const [erreur, setErreur] = useState('')
  const [proches, setProches] = useState<{ id: string; nom: string }[]>([])

  useEffect(() => {
    if (q.trim().length < 2) { setResultats([]); return }
    const minuteur = setTimeout(() => {
      api.get<Client[]>('/api/clients', { q, limite: 8 }).then(setResultats).catch(() => {})
    }, 200)
    return () => clearTimeout(minuteur)
  }, [q])

  const creer = async (confirmer = false) => {
    setErreur('')
    try {
      const c = await api.post<Client>('/api/clients', { ...nouveau, confirmer_doublon: confirmer })
      surChoix({ id: c.id, nom: c.nom })
      setCreation(false)
      setProches([])
    } catch (e) {
      if (e instanceof Echec && e.erreur.code === 'doublon_probable') {
        setProches((e.erreur.details?.clients as { id: string; nom: string }[]) ?? [])
      }
      setErreur(messageErreur(e))
    }
  }

  if (valeur) {
    return (
      <div className="client-choisi">
        <Link to={`/clients/${valeur.id}`}><strong>{valeur.nom}</strong></Link>
        {!desactive && <button type="button" className="lien" onClick={() => surChoix(null)}>changer</button>}
      </div>
    )
  }

  if (creation) {
    return (
      <div className="encadre">
        <div className="ligne-champs">
          <select value={nouveau.type} onChange={(e) => setNouveau({ ...nouveau, type: e.target.value })}>
            <option value="particulier">Particulier</option>
            <option value="entreprise">Entreprise</option>
          </select>
          <input placeholder="Nom ou société" value={nouveau.nom} onChange={(e) => setNouveau({ ...nouveau, nom: e.target.value })} />
          <input placeholder="E-mail" type="email" value={nouveau.email} onChange={(e) => setNouveau({ ...nouveau, email: e.target.value })} />
          <input placeholder="Téléphone" value={nouveau.telephone} onChange={(e) => setNouveau({ ...nouveau, telephone: e.target.value })} />
        </div>
        {erreur && <div className="bandeau erreur">{erreur}</div>}
        {proches.length > 0 && (
          <div className="ligne-champs">
            {proches.map((p) => (
              <button type="button" key={p.id} onClick={() => { surChoix(p); setCreation(false) }}>Utiliser « {p.nom} »</button>
            ))}
            <button type="button" onClick={() => creer(true)}>Créer quand même</button>
          </div>
        )}
        <div className="ligne-champs">
          <button type="button" className="principal" onClick={() => creer()}>Créer le client</button>
          <button type="button" className="lien" onClick={() => setCreation(false)}>Annuler</button>
        </div>
        <p className="aide">L'adresse et le n° TVA se complètent ensuite sur la fiche client.</p>
      </div>
    )
  }

  return (
    <div className="choix-client">
      <input placeholder="Chercher un client (nom, contact, e-mail…)" value={q} onChange={(e) => setQ(e.target.value)} disabled={desactive} />
      {resultats.length > 0 && (
        <ul className="suggestions">
          {resultats.map((c) => (
            <li key={c.id}>
              <button type="button" onClick={() => { surChoix({ id: c.id, nom: c.nom }); setQ('') }}>
                <strong>{c.nom}</strong> <span className="muet">{[c.email, c.telephone].filter(Boolean).join(' · ')}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <button type="button" className="lien" onClick={() => { setCreation(true); setNouveau({ ...nouveau, nom: q }) }}>
        + Nouveau client
      </button>
    </div>
  )
}
