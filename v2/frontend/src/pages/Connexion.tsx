import { FormEvent, useState } from 'react'
import { api } from '../api'
import { Champ, Erreur, useAction } from '../composants/ui'

export default function Connexion({ configuration, surConnexion }: { configuration: boolean; surConnexion: () => void }) {
  const [email, setEmail] = useState('')
  const [motDePasse, setMotDePasse] = useState('')
  const { enCours, erreur, lancer } = useAction()

  const envoyer = async (e: FormEvent) => {
    e.preventDefault()
    const ok = await lancer(() =>
      api.post(configuration ? '/api/auth/configuration' : '/api/auth/connexion', { email, mot_de_passe: motDePasse }),
    )
    if (ok) surConnexion()
  }

  return (
    <main className="page-centre">
      <form className="carte connexion" onSubmit={envoyer}>
        <h1>Restaurant Albert</h1>
        <p className="muet">
          {configuration
            ? 'Première utilisation : créez le compte administrateur.'
            : 'Fiches, devis et bons pour facturation.'}
        </p>
        <Champ libelle="E-mail">
          <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Champ>
        <Champ libelle="Mot de passe" aide={configuration ? '12 caractères au moins.' : undefined}>
          <input type="password" autoComplete={configuration ? 'new-password' : 'current-password'} value={motDePasse}
            onChange={(e) => setMotDePasse(e.target.value)} required />
        </Champ>
        <Erreur message={erreur} />
        <button className="principal" disabled={enCours}>{configuration ? 'Créer le compte' : 'Se connecter'}</button>
      </form>
    </main>
  )
}
