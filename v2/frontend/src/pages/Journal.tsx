import { useState } from 'react'
import { api, formatInstant } from '../api'
import { Chargement, EnTete, Erreur, Pastille, useCharger } from '../composants/ui'

type Entree = { id: string; le: string; utilisateur: string; canal: string; action: string; objet_type: string; resume: string }

export default function Journal() {
  const [canal, setCanal] = useState('')
  const { donnees, erreur, chargement } = useCharger(() => api.get<Entree[]>('/api/journal', { canal, limite: 500 }), [canal])
  return (
    <>
      <EnTete titre="Journal" sousTitre="Qui a fait quoi, sur le site ou par ChatGPT." />
      <div className="onglets">
        {[['', 'Tout'], ['site', 'Site'], ['chatgpt', 'ChatGPT']].map(([cle, libelle]) => (
          <button key={cle} className={canal === cle ? 'actif' : ''} onClick={() => setCanal(cle)}>{libelle}</button>
        ))}
      </div>
      <Erreur message={erreur} />
      <Chargement actif={chargement && !donnees} />
      <section className="carte">
        <table className="tableau">
          <thead><tr><th>Quand</th><th>Qui</th><th>Action</th><th>Détail</th></tr></thead>
          <tbody>
            {donnees?.map((e) => (
              <tr key={e.id}>
                <td className="etroit">{formatInstant(e.le)}</td>
                <td>{e.utilisateur} {e.canal === 'chatgpt' && <Pastille couleur="violet">ChatGPT</Pastille>}</td>
                <td>{e.action}</td>
                <td>{e.resume}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  )
}
