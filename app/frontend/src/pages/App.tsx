import { Routes, Route, NavLink } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Home as HomeIcon, UtensilsCrossed, Settings as SettingsIcon, History, ShoppingCart, Building2, AlertTriangle, Receipt, LayoutGrid, Package, LogOut, Sun, UsersRound } from 'lucide-react'
import { api, getAccessToken, setAccessToken } from '../lib/api'
import LoginPage from './LoginPage'
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
import RooftopReservationsPage from './RooftopReservationsPage'
import UsersPage from './UsersPage'
import { AppUser } from '../types'

const PERMISSION_PATHS: Record<string, string> = {
  reservations: '/', rooftop: '/rooftop', incidents: '/incidents', floorplan: '/salle',
  menu: '/menu', billing: '/facturation', orders: '/commande', suppliers: '/fournisseurs',
  settings: '/settings',
}

function NoAccess({ landing, notFound }: { landing?: string, notFound?: boolean }) {
  const target = landing ? PERMISSION_PATHS[landing] : undefined
  return <section className="empty-state">
    <h2>{notFound ? 'Page introuvable' : 'Accès refusé'}</h2>
    <p>{notFound
      ? "Cette page n'existe pas."
      : "Vous n'avez pas accès à cette section. Contactez un administrateur si vous pensez qu'il s'agit d'une erreur."}</p>
    {target && <NavLink className="btn btn-primary" to={target}>Aller à ma page d'accueil</NavLink>}
  </section>
}

export default function App() {
  const [reminderCount, setReminderCount] = useState(0)
  const [ready, setReady] = useState(false)
  const [setupRequired, setSetupRequired] = useState(false)
  const [authenticated, setAuthenticated] = useState(false)
  const [user, setUser] = useState<AppUser | null>(null)

  useEffect(() => {
    const initialise = async () => {
      try {
        const status = await api.get('/api/auth/status')
        setSetupRequired(status.data.setup_required)
        if (!status.data.setup_required && getAccessToken()) {
          const response = await api.get('/api/auth/me')
          setUser(response.data)
          setAuthenticated(true)
        }
      } finally { setReady(true) }
    }
    initialise()
    const expired = () => { setUser(null); setAuthenticated(false) }
    window.addEventListener('auth:expired', expired)
    return () => window.removeEventListener('auth:expired', expired)
  }, [])

  if (!ready) return <main className="auth-page">Chargement…</main>
  if (!authenticated) return <LoginPage setupRequired={setupRequired} onAuthenticated={async (token) => { setAccessToken(token); const response = await api.get('/api/auth/me'); setUser(response.data); setAuthenticated(true); setSetupRequired(false) }} />
  const isAdmin = user?.role === 'admin'
  const canAccess = (permission: string) => Boolean(isAdmin || user?.permissions?.includes(permission))
  // Hiding a nav link is not access control: someone can still type the URL.
  // Every route renders behind the same check the sidebar uses.
  const landing = ['reservations', 'rooftop', 'incidents', 'floorplan', 'menu', 'billing', 'orders', 'suppliers', 'settings']
    .find(canAccess)
  const guard = (permission: string, element: JSX.Element) =>
    canAccess(permission) ? element : <NoAccess landing={landing} />

  return (
    <div className="app-layout app-theme app-theme-violet">
      <aside className="sidebar">
        <div className="sidebar-header">Fiche Cuisine</div>
        <nav className="sidebar-nav">
          {canAccess('reservations') && <NavLink to="/" end className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <HomeIcon className="w-4 h-4"/> Fiches
            {reminderCount > 0 && (
              <span className="nav-reminder-badge">{reminderCount}</span>
            )}
          </NavLink>}
          {canAccess('reservations') && <NavLink to="/past" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <History className="w-4 h-4"/> Passées
          </NavLink>}
          {canAccess('rooftop') && <NavLink to="/rooftop" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <Sun className="w-4 h-4"/> Rooftop
          </NavLink>}
          {canAccess('incidents') && <NavLink to="/incidents" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <AlertTriangle className="w-4 h-4"/> Plaintes
          </NavLink>}
          {canAccess('floorplan') && <NavLink to="/salle" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <LayoutGrid className="w-4 h-4"/> Salle
          </NavLink>}
          {canAccess('menu') && <NavLink to="/menu" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <UtensilsCrossed className="w-4 h-4"/> Base de plats
          </NavLink>}
          {canAccess('billing') && <NavLink to="/facturation" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
            <Receipt className="w-4 h-4"/> Facturation
          </NavLink>}
          <div className="sidebar-sep" />
          {canAccess('orders') && <NavLink to="/commande" className={({isActive}) => `nav-link nav-link-secondary ${isActive ? 'active' : ''}`}>
            <ShoppingCart className="w-4 h-4"/> Commande
          </NavLink>}
          {canAccess('orders') && <NavLink to="/achats" className={({isActive}) => `nav-link nav-link-secondary ${isActive ? 'active' : ''}`}>
            <Package className="w-4 h-4"/> Achats
          </NavLink>}
          {canAccess('suppliers') && <NavLink to="/fournisseurs" className={({isActive}) => `nav-link nav-link-secondary ${isActive ? 'active' : ''}`}>
            <Building2 className="w-4 h-4"/> Fournisseurs
          </NavLink>}
          {canAccess('settings') && <NavLink to="/settings" className={({isActive}) => `nav-link nav-link-secondary ${isActive ? 'active' : ''}`}>
            <SettingsIcon className="w-4 h-4"/> Paramètres
          </NavLink>}
          {isAdmin && <NavLink to="/users" className={({isActive}) => `nav-link nav-link-secondary ${isActive ? 'active' : ''}`}><UsersRound className="w-4 h-4"/> Utilisateurs</NavLink>}
          <button className="nav-link nav-link-secondary nav-logout" onClick={() => { setAccessToken(null); setUser(null); setAuthenticated(false) }}>
            <LogOut className="w-4 h-4"/> Déconnexion
          </button>
        </nav>
      </aside>
      <main className="content">
        {/* setReminderCount is referentially stable, so ReminderBanner's
            load() callback does not change identity on every render. */}
        <Routes>
          <Route path="/" element={canAccess('reservations') ? <Home onReminderCount={setReminderCount} /> : <NoAccess landing={landing} />} />
          <Route path="/past" element={guard('reservations', <PastReservations />)} />
          <Route path="/rooftop" element={guard('rooftop', <RooftopReservationsPage />)} />
          <Route path="/users" element={isAdmin ? <UsersPage /> : <NoAccess landing={landing} />} />
          <Route path="/incidents" element={guard('incidents', <IncidentsPage />)} />
          <Route path="/salle" element={guard('floorplan', <FloorPlanPage />)} />
          <Route path="/reservation/new" element={guard('reservations', <EditReservation />)} />
          <Route path="/reservation/:id" element={guard('reservations', <EditReservation />)} />
          <Route path="/incident/new" element={guard('incidents', <EditIncident />)} />
          <Route path="/incident/:id" element={guard('incidents', <EditIncident />)} />
          <Route path="/menu" element={guard('menu', <MenuPage />)} />
          <Route path="/commande" element={guard('orders', <CommandePage />)} />
          <Route path="/achats" element={guard('orders', <OrdersListPage />)} />
          <Route path="/achats/:id" element={guard('orders', <OrderDetailPage />)} />
          <Route path="/fournisseurs" element={guard('suppliers', <SuppliersPage />)} />
          <Route path="/settings" element={guard('settings', <ZenchefSettings />)} />
          <Route path="/facturation" element={guard('billing', <FacturationPage />)} />
          <Route path="*" element={<NoAccess notFound />} />
        </Routes>
        {canAccess('dashboard') && <NotesWidget />}
      </main>
    </div>
  )
}
