import { Routes, Route, NavLink } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { Home as HomeIcon, UtensilsCrossed, Settings as SettingsIcon, History, ShoppingCart, Building2, AlertTriangle, Receipt, LayoutGrid, Package } from 'lucide-react'
import { api } from '../lib/api'
import NotesWidget from '../components/NotesWidget'
import Home from './Home'
import EditReservation from './EditReservation'
import MenuPage from './MenuPage'
import ZenchefSettings from './ZenchefSettings'
import PastReservations from './PastReservations'
import CommandePage from './CommandePage'
import OrdersListPage from './OrdersListPage'
import OrderDetailPage from './OrderDetailPage'
import SuppliersPage from './SuppliersPage'
import FloorPlanPage from './FloorPlanPage'
import IncidentsPage from './IncidentsPage'
import EditIncident from './EditIncident'
import FacturationPage from './FacturationPage'

export default function App() {
  const [reminderCount, setReminderCount] = useState(0)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    function fetchCount() {
      api.get('/api/reminders/pending', { params: { days: 5 } })
        .then(r => setReminderCount(Array.isArray(r.data) ? r.data.length : 0))
        .catch(() => {})
    }
    fetchCount()
    intervalRef.current = setInterval(fetchCount, 5 * 60 * 1000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [])

  return (
    <div className="app-layout app-theme app-theme-violet">
      <aside className="sidebar">
        <div className="sidebar-header">Fiche Cuisine</div>
        <nav className="sidebar-nav">
          <NavLink to="/" end className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <HomeIcon className="w-4 h-4"/> Fiches
            {reminderCount > 0 && (
              <span className="nav-reminder-badge">{reminderCount}</span>
            )}
          </NavLink>
          <NavLink to="/past" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <History className="w-4 h-4"/> Passées
          </NavLink>
          <NavLink to="/incidents" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <AlertTriangle className="w-4 h-4"/> Plaintes
          </NavLink>
          <NavLink to="/salle" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <LayoutGrid className="w-4 h-4"/> Salle
          </NavLink>
          <NavLink to="/menu" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <UtensilsCrossed className="w-4 h-4"/> Base de plats
          </NavLink>
          <NavLink to="/facturation" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <Receipt className="w-4 h-4"/> Facturation
          </NavLink>
          <div className="sidebar-sep" />
          <NavLink to="/commande" className={({isActive}) => `nav-link nav-link-secondary ${isActive ? 'active' : ''}`}>
            <ShoppingCart className="w-4 h-4"/> Commande
          </NavLink>
          <NavLink to="/achats" className={({isActive}) => `nav-link nav-link-secondary ${isActive ? 'active' : ''}`}>
            <Package className="w-4 h-4"/> Achats
          </NavLink>
          <NavLink to="/fournisseurs" className={({isActive}) => `nav-link nav-link-secondary ${isActive ? 'active' : ''}`}>
            <Building2 className="w-4 h-4"/> Fournisseurs
          </NavLink>
          <NavLink to="/settings" className={({isActive}) => `nav-link nav-link-secondary ${isActive ? 'active' : ''}`}>
            <SettingsIcon className="w-4 h-4"/> Paramètres
          </NavLink>
        </nav>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/past" element={<PastReservations />} />
          <Route path="/incidents" element={<IncidentsPage />} />
          <Route path="/salle" element={<FloorPlanPage />} />
          <Route path="/reservation/new" element={<EditReservation />} />
          <Route path="/reservation/:id" element={<EditReservation />} />
          <Route path="/incident/new" element={<EditIncident />} />
          <Route path="/incident/:id" element={<EditIncident />} />
          <Route path="/menu" element={<MenuPage />} />
          <Route path="/commande" element={<CommandePage />} />
          <Route path="/achats" element={<OrdersListPage />} />
          <Route path="/achats/:id" element={<OrderDetailPage />} />
          <Route path="/fournisseurs" element={<SuppliersPage />} />
          <Route path="/settings" element={<ZenchefSettings />} />
          <Route path="/facturation" element={<FacturationPage />} />
        </Routes>
        <NotesWidget />
      </main>
    </div>
  )
}
