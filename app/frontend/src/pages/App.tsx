import { Routes, Route, NavLink } from 'react-router-dom'
import { Home as HomeIcon, UtensilsCrossed, Settings as SettingsIcon, History, ShoppingCart, Building2 } from 'lucide-react'
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

export default function App() {
  return (
    <div className="app-layout app-theme app-theme-violet">
      <aside className="sidebar">
        <div className="sidebar-header">Fiche Cuisine Manager</div>
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
          <NavLink to="/commande" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <ShoppingCart className="w-4 h-4"/> Commande
          </NavLink>
          <NavLink to="/achats" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <ShoppingCart className="w-4 h-4"/> Achats
          </NavLink>
          <NavLink to="/fournisseurs" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <Building2 className="w-4 h-4"/> Fournisseurs
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
          <Route path="/commande" element={<CommandePage />} />
          <Route path="/achats" element={<OrdersListPage />} />
          <Route path="/achats/:id" element={<OrderDetailPage />} />
          <Route path="/fournisseurs" element={<SuppliersPage />} />
          <Route path="/settings" element={<ZenchefSettings />} />
        </Routes>
        <NotesWidget />
      </main>
    </div>
  )
}
