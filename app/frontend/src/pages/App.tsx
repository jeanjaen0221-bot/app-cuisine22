import { Routes, Route, NavLink } from 'react-router-dom'
import { Home as HomeIcon, UtensilsCrossed, Settings as SettingsIcon, History } from 'lucide-react'
import NotesWidget from '../components/NotesWidget'
import Home from './Home'
import EditReservation from './EditReservation'
import MenuPage from './MenuPage'
import ZenchefSettings from './ZenchefSettings'
import PastReservations from './PastReservations'

export default function App() {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">FicheCuisineManager</div>
        <nav className="sidebar-nav">
          <NavLink to="/" end className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <HomeIcon className="w-4 h-4"/> Fiches
          </NavLink>
          <NavLink to="/past" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <History className="w-4 h-4"/> Passées
          </NavLink>
          <NavLink to="/menu" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <UtensilsCrossed className="w-4 h-4"/> Base de plats
          </NavLink>
          <NavLink to="/settings" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <SettingsIcon className="w-4 h-4"/> Paramètres
          </NavLink>
        </nav>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/past" element={<PastReservations />} />
          <Route path="/reservation/new" element={<EditReservation />} />
          <Route path="/reservation/:id" element={<EditReservation />} />
          <Route path="/menu" element={<MenuPage />} />
          <Route path="/settings" element={<ZenchefSettings />} />
        </Routes>
        <NotesWidget />
      </main>
    </div>
  )
}
