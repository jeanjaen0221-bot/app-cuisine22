import { api, formatInstant } from '../api'
import { EnTete, Erreur, Pastille, useAction, useCharger } from '../composants/ui'

type Infos = {
  url_connecteur: string
  autorise: boolean
  droits: { cle: string; libelle: string }[]
  connexions: { id: string; utilisateur: string; application: string; droits: string[]; cree_le: string; derniere_utilisation: string | null; revoquee: boolean }[]
}

export default function ChatGPT() {
  const { donnees: i, erreur, recharger } = useCharger(() => api.get<Infos>('/api/chatgpt'))
  const action = useAction()
  const revoquer = async (id: string) => {
    if (!window.confirm('Couper cette connexion ChatGPT ?')) return
    if (await action.lancer(() => api.post(`/api/chatgpt/connexions/${id}/revoquer`))) recharger()
  }
  if (!i) return <Erreur message={erreur} />
  return (
    <>
      <EnTete titre="ChatGPT" sousTitre="ChatGPT agit en votre nom, avec les mêmes règles que le site. Tout ce qu'il fait apparaît dans l'historique." />
      <Erreur message={action.erreur} />
      <section className="carte">
        <h2>Connecter ChatGPT</h2>
        {!i.autorise && <div className="bandeau attention">Votre compte n'a pas le droit « Connecter ChatGPT » : le demander à un administrateur.</div>}
        <ol className="etapes simples">
          <li>Dans ChatGPT, ajouter un connecteur personnalisé (serveur MCP distant).</li>
          <li>Adresse du serveur MCP : <code>{i.url_connecteur}</code> — authentification : OAuth.</li>
          <li>ChatGPT ouvre la page de connexion du restaurant : se connecter et choisir les droits accordés.</li>
        </ol>
        <h3>Droits possibles</h3>
        <ul className="liste">{i.droits.map((d) => <li key={d.cle}><code>{d.cle}</code> — {d.libelle}</li>)}</ul>
        <p className="aide">Jamais possible pour ChatGPT : valider ou transmettre un devis, modifier un prix ou une formule, supprimer, passer une fiche en « finale », écrire au client.</p>
      </section>
      <section className="carte">
        <h2>Connexions</h2>
        <table className="tableau">
          <thead><tr><th>Compte</th><th>Application</th><th>Droits</th><th>Créée</th><th>Dernière utilisation</th><th /></tr></thead>
          <tbody>
            {i.connexions.map((c) => (
              <tr key={c.id} className={c.revoquee ? 'inactif' : ''}>
                <td>{c.utilisateur}</td>
                <td>{c.application}</td>
                <td>{c.droits.filter((d) => d !== 'offline_access').map((d) => <Pastille key={d} couleur="violet">{d}</Pastille>)}</td>
                <td>{formatInstant(c.cree_le)}</td>
                <td>{formatInstant(c.derniere_utilisation)}</td>
                <td>{c.revoquee ? 'coupée' : <button className="danger" onClick={() => revoquer(c.id)}>Couper</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {i.connexions.length === 0 && <p className="muet">Aucune connexion.</p>}
      </section>
    </>
  )
}
