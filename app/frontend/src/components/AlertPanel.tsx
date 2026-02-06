import React from 'react'

export interface AlertPanelProps {
  title?: string
  alerts: string[]
  onClear?: () => void
}

export default function AlertPanel({ title = 'Alertes auto-assign', alerts, onClear }: AlertPanelProps) {
  if (!alerts || alerts.length === 0) return null

  return (
    <div className="card shadow-lg border border-gray-200 bg-white">
      <div className="card-body p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="font-semibold text-gray-800 flex items-center gap-2">
            <span>🛈</span>
            <span>{title}</span>
          </div>
          {onClear && (
            <button className="btn btn-xs btn-outline" onClick={onClear} title="Effacer les alertes">
              Effacer
            </button>
          )}
        </div>
        <div className="max-h-64 overflow-auto pr-1">
          <ul className="space-y-2 text-sm">
            {alerts.map((a, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="mt-0.5">⚠️</span>
                <span className="text-gray-800 leading-snug">{a}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
