import { FormEvent, useState } from 'react'
import { api, formatInstant } from '../api'
import { Champ, EnTete, Erreur, useAction, useCharger } from '../composants/ui'
import type { Utilisateur } from '../types'

const ROLES = { admin: 'Administrateur', equipe: 'Équipe', compta: 'Comptabilité' }
const DROITS = { prix: 'Modifier les prix et formules', chatgpt: 'Connecter ChatGPT' }

export default function Utilisateurs() {
  const { donnees, erreur, recharger } = useCharger(() => api.get<Utilisateur[]>('/api/utilisateurs'))
  const action = useAction()
  const [nouveau, setNouveau] = useState({ email: '', nom: '', role: 'equipe', mot_de_passe: '', droits: [] as string[] })

  const modifier = async (u: Utilisateur, changement: object) => {
    if (await action.lancer(() => api.patch(`/api/utilisateurs/${u.id}`, changement))) recharger()
  }
  const creer = async (e: FormEvent) => {
    e.preventDefault()
    if (await action.lancer(() => api.post('/api/utilisateurs', nouveau))) {
      setNouveau({ email: '', nom: '', role: 'equipe', mot_de_passe: '', droits: [] })
      recharger()
    }
  }

  return (
    <>
      <EnTete titre="Utilisateurs" sousTitre="Équipe : clients, fiches, devis et bons. Comptabilité : espace compta seulement. Administrateur : tout." />
      <Erreur message={erreur || action.erreur} />
      <section className="carte">
        <table className="tableau">
          <thead><tr><th>E-mail</th><th>Nom</th><th>Rôle</th><th>Droits en plus</th><th>Actif</th><th>Dernière connexion</th><th /></tr></thead>
          <tbody>
            {donnees?.map((u) => (
              <tr key={u.id} className={u.actif ? '' : 'inactif'}>
                <td>{u.email}</td>
                <td>{u.nom}</td>
                <td>
                  <select value={u.role} onChange={(e) => modifier(u, { role: e.target.value })}>
                    {Object.entries(ROLES).map(([cle, l]) => <option key={cle} value={cle}>{l}</option>)}
                  </select>
                </td>
                <td>
                  {Object.entries(DROITS).map(([cle, l]) => (
                    <label key={cle} className="case">
                      <input type="checkbox" checked={u.droits.includes(cle)}
                        onChange={(e) => modifier(u, { droits: e.target.checked ? [...u.droits, cle] : u.droits.filter((d) => d !== cle) })} /> {l}
                    </label>
                  ))}
                </td>
                <td><input type="checkbox" checked={u.actif} onChange={(e) => modifier(u, { actif: e.target.checked })} /></td>
                <td>{formatInstant(u.derniere_connexion)}</td>
                <td>
                  <button className="lien" onClick={() => {
                    const mdp = window.prompt('Nouveau mot de passe (12 caractères au moins) ?')
                    if (mdp) modifier(u, { mot_de_passe: mdp })
                  }}>mot de passe</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <form className="carte" onSubmit={creer}>
        <h2>Ajouter un utilisateur</h2>
        <div className="ligne-champs">
          <Champ libelle="E-mail"><input type="email" value={nouveau.email} onChange={(e) => setNouveau({ ...nouveau, email: e.target.value })} required /></Champ>
          <Champ libelle="Nom"><input value={nouveau.nom} onChange={(e) => setNouveau({ ...nouveau, nom: e.target.value })} /></Champ>
          <Champ libelle="Rôle">
            <select value={nouveau.role} onChange={(e) => setNouveau({ ...nouveau, role: e.target.value })}>
              {Object.entries(ROLES).map(([cle, l]) => <option key={cle} value={cle}>{l}</option>)}
            </select>
          </Champ>
          <Champ libelle="Mot de passe" aide="12 caractères au moins."><input type="password" autoComplete="new-password" value={nouveau.mot_de_passe} onChange={(e) => setNouveau({ ...nouveau, mot_de_passe: e.target.value })} required /></Champ>
          <button className="principal" disabled={action.enCours}>Ajouter</button>
        </div>
      </form>
    </>
  )
}
