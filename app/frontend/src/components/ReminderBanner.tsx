import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { BellRing, ChevronDown, ChevronUp, ExternalLink, VolumeX, X } from 'lucide-react'
import { api } from '../lib/api'

type ReminderItem = {
  reservation_id: string
  client_name: string
  service_date: string
  pax: number
  menu_formula: string | null
  snoozed_until: string | null
  muted: boolean
}

const SNOOZE_OPTIONS = [
  { label: '1 heure', hours: 1 },
  { label: '4 heures', hours: 4 },
  { label: 'Demain', hours: 24 },
  { label: '3 jours', hours: 72 },
  { label: '5 jours', hours: 120 },
]

function formatDate(d: string) {
  try {
    return new Date(d + 'T00:00').toLocaleDateString('fr-BE', {
      weekday: 'short', day: '2-digit', month: 'short',
    })
  } catch { return d }
}

function daysUntil(d: string): number {
  const diff = new Date(d + 'T00:00').getTime() - new Date().setHours(0, 0, 0, 0)
  return Math.ceil(diff / 86400000)
}

type Props = {
  days?: number
  onCountChange?: (count: number) => void
}

export default function ReminderBanner({ days = 5, onCountChange }: Props) {
  const [reminders, setReminders] = useState<ReminderItem[]>([])
  const [threshold, setThreshold] = useState(days)
  const [collapsed, setCollapsed] = useState(false)
  const [openSnooze, setOpenSnooze] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async (d?: number) => {
    setLoading(true)
    try {
      const res = await api.get('/api/reminders/pending', { params: { days: d ?? threshold } })
      const data: ReminderItem[] = Array.isArray(res.data) ? res.data : []
      setReminders(data)
      onCountChange?.(data.length)
    } catch {
      // non-fatal
    } finally {
      setLoading(false)
    }
  }, [threshold, onCountChange])

  useEffect(() => {
    load()
    if (intervalRef.current) clearInterval(intervalRef.current)
    intervalRef.current = setInterval(() => load(), 5 * 60 * 1000)
    function onVisible() {
      if (document.visibilityState === 'visible') load()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [load])

  async function snooze(reservationId: string, hours: number) {
    try {
      await api.post(`/api/reminders/${reservationId}/snooze`, { hours })
    } catch {}
    finally {
      setOpenSnooze(null)
      load()
    }
  }

  async function mute(reservationId: string) {
    try {
      await api.post(`/api/reminders/${reservationId}/mute`)
    } catch {}
    finally {
      load()
    }
  }

  if (reminders.length === 0 && !loading) return null

  return (
    <div className="reminder-banner">
      <div className="reminder-banner-header">
        <div className="flex items-center gap-2">
          <BellRing className="w-4 h-4 text-amber-600 shrink-0" />
          <span className="font-semibold text-amber-900 text-sm">
            {reminders.length === 1
              ? '1 réservation sans plats sélectionnés'
              : `${reminders.length} réservations sans plats sélectionnés`}
          </span>
          <span className="text-xs text-amber-700 ml-1">
            (dans les
            <input
              type="number"
              min={1}
              max={30}
              className="reminder-threshold-input"
              value={threshold}
              onChange={e => {
                const v = Math.max(1, Math.min(30, parseInt(e.target.value) || 5))
                setThreshold(v)
                load(v)
              }}
            />
            prochains jours)
          </span>
        </div>
        <button
          className="reminder-collapse-btn"
          onClick={() => setCollapsed(v => !v)}
          title={collapsed ? 'Afficher' : 'Réduire'}
        >
          {collapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
        </button>
      </div>

      {!collapsed && (
        <ul className="reminder-list">
          {reminders.map(rem => {
            const d = daysUntil(rem.service_date)
            const urgency = d <= 1 ? 'critical' : d <= 2 ? 'high' : 'normal'
            return (
              <li key={rem.reservation_id} className={`reminder-item reminder-item--${urgency}`}>
                <div className="reminder-item-info">
                  <span className="reminder-client">{rem.client_name}</span>
                  <span className="reminder-meta">
                    {formatDate(rem.service_date)}
                    {d === 0 && <span className="reminder-badge-today">Aujourd'hui</span>}
                    {d === 1 && <span className="reminder-badge-urgent">Demain</span>}
                    {d > 1 && <span className="reminder-badge-days">dans {d}j</span>}
                    · {rem.pax} pax
                  </span>
                </div>
                <div className="reminder-item-actions">
                  <Link
                    to={`/reservation/${rem.reservation_id}`}
                    className="btn btn-xs btn-outline"
                    title="Ouvrir la fiche"
                  >
                    <ExternalLink className="w-3 h-3" /> Fiche
                  </Link>

                  {/* Snooze dropdown */}
                  <div className="relative">
                    <button
                      className="btn btn-xs btn-outline"
                      onClick={() => setOpenSnooze(prev => prev === rem.reservation_id ? null : rem.reservation_id)}
                    >
                      Snooze <ChevronDown className="w-3 h-3 ml-0.5" />
                    </button>
                    {openSnooze === rem.reservation_id && (
                      <div className="reminder-snooze-menu">
                        {SNOOZE_OPTIONS.map(opt => (
                          <button
                            key={opt.hours}
                            className="reminder-snooze-option"
                            onClick={() => snooze(rem.reservation_id, opt.hours)}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  <button
                    className="btn btn-xs btn-outline reminder-mute-btn"
                    onClick={() => mute(rem.reservation_id)}
                    title="Ignorer définitivement ce rappel"
                  >
                    <VolumeX className="w-3 h-3" /> Ignorer
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
