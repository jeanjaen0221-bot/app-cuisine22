import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { api } from './api'
import { FournisseurSession, useSession } from './contexte'
import type { Moi } from './types'
import Connexion from './pages/Connexion'
import TableauDeBord from './pages/TableauDeBord'
import Fiches from './pages/Fiches'
import FicheEdition from './pages/FicheEdition'
import Clients from './pages/Clients'
import ClientDetail from './pages/ClientDetail'
import DevisListe from './pages/DevisListe'
import DevisDetail from './pages/DevisDetail'
import Bons from './pages/Bons'
import BonDetail from './pages/BonDetail'
import Compta from './pages/Compta'
import Prix from './pages/Prix'
import Formules from './pages/Formules'
import Journal from './pages/Journal'
import Utilisateurs from './pages/Utilisateurs'
import Parametres from './pages/Parametres'
import ChatGPT from './pages/ChatGPT'
import Salle from './pages/Salle'

export default function App() {
  const [etat, setEtat] = useState<'chargement' | 'configuration' | 'connexion' | 'connecte'>('chargement')
  const [moi, setMoi] = useState<Moi | null>(null)

  const charger = async () => {
    try {
      setMoi(await api.get<Moi>('/api/auth/moi'))
      setEtat('connecte')
    } catch {
      const { configuration_requise } = await api.get<{ configuration_requise: boolean }>('/api/auth/etat')
      setEtat(configuration_requise ? 'configuration' : 'connexion')
    }
  }

  useEffect(() => {
    charger()
    const sortir = () => { setMoi(null); setEtat('connexion') }
    window.addEventListener('albert:deconnecte', sortir)
    return () => window.removeEventListener('albert:deconnecte', sortir)
  }, [])

  if (etat === 'chargement') return <main className="page-centre">Chargement…</main>
  if (etat !== 'connecte' || !moi) {
    return <Connexion configuration={etat === 'configuration'} surConnexion={charger} />
  }
  return (
    <FournisseurSession moi={moi} surDeconnexion={() => { setMoi(null); setEtat('connexion') }}>
      <Mise />
    </FournisseurSession>
  )
}

function Lien({ vers, children, badge }: { vers: string; children: React.ReactNode; badge?: number }) {
  return (
    <NavLink to={vers} end={vers === '/'} className={({ isActive }) => `nav-lien${isActive ? ' actif' : ''}`}>
      <span>{children}</span>
      {badge ? <span className="badge-rouge">{badge}</span> : null}
    </NavLink>
  )
}

function Mise() {
  const { moi, prixManquants, deconnecter } = useSession()
  const p = moi.peut
  const accueil = p.fiches ? '/' : '/compta'
  return (
    <div className="mise">
      <aside className="barre">
        <div className="marque">Albert <small>v2</small></div>
        <nav>
          {p.fiches && <Lien vers="/">Tableau de bord</Lien>}
          {p.fiches && <Lien vers="/fiches">Fiches</Lien>}
          {p.fiches && <Lien vers="/clients">Clients</Lien>}
          {p.fiches && <Lien vers="/devis">Devis</Lien>}
          {p.fiches && <Lien vers="/bons">Bons pour facturation</Lien>}
          {p.fiches && <Lien vers="/salle">Salle</Lien>}
          {p.compta && <Lien vers="/compta">Espace compta</Lien>}
          <div className="separateur" />
          <Lien vers="/prix" badge={p.prix ? prixManquants : 0}>Prix</Lien>
          <Lien vers="/formules">Formules</Lien>
          {p.fiches && <Lien vers="/chatgpt">ChatGPT</Lien>}
          {p.admin && <Lien vers="/journal">Journal</Lien>}
          {p.admin && <Lien vers="/utilisateurs">Utilisateurs</Lien>}
          {p.admin && <Lien vers="/parametres">Paramètres</Lien>}
        </nav>
        <div className="pied-barre">
          <div className="muet">{moi.email}</div>
          <button className="lien" onClick={deconnecter}>Se déconnecter</button>
        </div>
      </aside>
      <main className="contenu">
        <Routes>
          {p.fiches && <Route path="/" element={<TableauDeBord />} />}
          {p.fiches && <Route path="/fiches" element={<Fiches />} />}
          {p.fiches && <Route path="/fiches/nouvelle" element={<FicheEdition />} />}
          {p.fiches && <Route path="/fiches/:id" element={<FicheEdition />} />}
          {p.fiches && <Route path="/clients" element={<Clients />} />}
          {p.fiches && <Route path="/clients/:id" element={<ClientDetail />} />}
          {p.fiches && <Route path="/devis" element={<DevisListe />} />}
          <Route path="/devis/:id" element={<DevisDetail />} />
          {p.fiches && <Route path="/bons" element={<Bons />} />}
          {p.fiches && <Route path="/salle" element={<Salle />} />}
          <Route path="/bons/:id" element={<BonDetail />} />
          {p.compta && <Route path="/compta" element={<Compta />} />}
          <Route path="/prix" element={<Prix />} />
          <Route path="/formules" element={<Formules />} />
          {p.fiches && <Route path="/chatgpt" element={<ChatGPT />} />}
          {p.admin && <Route path="/journal" element={<Journal />} />}
          {p.admin && <Route path="/utilisateurs" element={<Utilisateurs />} />}
          {p.admin && <Route path="/parametres" element={<Parametres />} />}
          <Route path="*" element={<Navigate to={accueil} replace />} />
        </Routes>
      </main>
    </div>
  )
}
