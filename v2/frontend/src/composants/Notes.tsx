import { useState } from 'react'
import { api, formatInstant } from '../api'
import { Erreur, useAction, useCharger } from './ui'

type Note = { id: string; auteur: string; contenu: string; epinglee: boolean; cree_le: string; modifie_le: string | null }

/** Post-it partagés de l'équipe. */
export default function Notes() {
  const { donnees, erreur, recharger } = useCharger(() => api.get<Note[]>('/api/notes'))
  const [texte, setTexte] = useState('')
  const action = useAction()
  const faire = async (f: () => Promise<unknown>) => { if (await action.lancer(f)) recharger() }

  return (
    <section className="carte">
      <h2>Notes de l'équipe</h2>
      <Erreur message={erreur || action.erreur} />
      <form className="ligne-champs" onSubmit={(e) => { e.preventDefault(); faire(() => api.post('/api/notes', { contenu: texte })).then(() => setTexte('')) }}>
        <input style={{ flex: 1 }} placeholder="Une info pour l'équipe…" value={texte} onChange={(e) => setTexte(e.target.value)} />
        <button className="principal" disabled={!texte.trim() || action.enCours}>Ajouter</button>
      </form>
      <div className="postits">
        {donnees?.map((n) => (
          <div key={n.id} className={`postit${n.epinglee ? ' epinglee' : ''}`}>
            <div className="postit-texte">{n.contenu}</div>
            <div className="postit-pied">
              <span className="muet">{n.auteur.split('@')[0]} · {formatInstant(n.modifie_le ?? n.cree_le)}</span>
              <span>
                <button className="lien" onClick={() => faire(() => api.patch(`/api/notes/${n.id}`, { epinglee: !n.epinglee }))}>{n.epinglee ? 'détacher' : 'épingler'}</button>
                {' · '}
                <button className="lien" onClick={() => window.confirm('Supprimer cette note ?') && faire(() => api.delete(`/api/notes/${n.id}`))}>supprimer</button>
              </span>
            </div>
          </div>
        ))}
        {donnees?.length === 0 && <p className="muet">Aucune note.</p>}
      </div>
    </section>
  )
}
