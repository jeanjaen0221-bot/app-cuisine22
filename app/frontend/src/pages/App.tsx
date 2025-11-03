import { Routes, Route, Link, useNavigate } from 'react-router-dom'
import { Home as HomeIcon, UtensilsCrossed, Settings as SettingsIcon, History } from 'lucide-react'
import Home from './Home'
import EditReservation from './EditReservation'
import MenuPage from './MenuPage'
import ZenchefSettings from './ZenchefSettings'
import PastReservations from './PastReservations'

export default function App() {
  const navigate = useNavigate()
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white shadow-soft">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-primary cursor-pointer" onClick={() => navigate('/')}>FicheCuisineManager</h1>
          <nav className="flex gap-2">
            <Link className="btn flex items-center gap-2" to="/"><HomeIcon className="h-4 w-4"/> Fiches</Link>
            <Link className="btn flex items-center gap-2" to="/past"><History className="h-4 w-4"/> Passées</Link>
            <Link className="btn flex items-center gap-2" to="/menu"><UtensilsCrossed className="h-4 w-4"/> Base de plats</Link>
            <Link className="btn flex items-center gap-2" to="/settings"><SettingsIcon className="h-4 w-4"/> Paramètres</Link>
          </nav>
        </div>
      </header>
      <main className="max-w-6xl mx-auto w-full px-4 py-6 flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/past" element={<PastReservations />} />
          <Route path="/reservation/new" element={<EditReservation />} />
          <Route path="/reservation/:id" element={<EditReservation />} />
          <Route path="/menu" element={<MenuPage />} />
          <Route path="/settings" element={<ZenchefSettings />} />
        </Routes>
      </main>
    </div>
  )
}
