import { AlertTriangle, X } from 'lucide-react'

interface Props {
  open: boolean
  clientName: string
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmDeleteModal({ open, clientName, onConfirm, onCancel }: Props) {
  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.45)' }}
      onClick={onCancel}
    >
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-sm p-6 space-y-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-full bg-red-100">
              <AlertTriangle className="w-5 h-5 text-red-600" />
            </div>
            <h3 className="text-base font-semibold text-gray-900">Supprimer la réservation</h3>
          </div>
          <button
            className="text-gray-400 hover:text-gray-600 transition-colors"
            onClick={onCancel}
            aria-label="Fermer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-sm text-gray-600">
          Êtes-vous sûr de vouloir supprimer la fiche de{' '}
          <span className="font-semibold text-gray-900">{clientName}</span> ?
          <br />
          <span className="text-red-600">Cette action est irréversible.</span>
        </p>

        <div className="flex justify-end gap-3 pt-2">
          <button
            className="btn btn-sm btn-outline"
            onClick={onCancel}
          >
            Annuler
          </button>
          <button
            className="btn btn-sm"
            style={{ backgroundColor: '#dc2626', color: '#fff', borderColor: '#dc2626' }}
            onClick={onConfirm}
          >
            Supprimer
          </button>
        </div>
      </div>
    </div>
  )
}
