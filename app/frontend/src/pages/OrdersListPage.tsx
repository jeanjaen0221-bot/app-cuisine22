import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import type { PurchaseOrder } from '../types'

export default function OrdersListPage() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([])
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const res = await api.get('/api/purchase-orders')
      setOrders(res.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="container space-y-4">
      <div className="card">
        <div className="card-header">
          <h3 className="text-lg font-semibold">Commandes d'achat</h3>
          <div className="flex items-center gap-3">
            <button className="btn btn-outline btn-sm" onClick={load} disabled={loading}>{loading ? '...' : 'Rafraîchir'}</button>
          </div>
        </div>
        <div className="card-body">
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Statut</th>
                <th>Créée</th>
                <th>Lignes</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td className="font-mono text-xs">{o.id}</td>
                  <td>{o.status}</td>
                  <td>{new Date(o.created_at).toLocaleString()}</td>
                  <td>{o.items.length}</td>
                  <td>
                    <Link className="btn btn-sm btn-outline" to={`/achats/${o.id}`}>Ouvrir</Link>
                  </td>
                </tr>
              ))}
              {orders.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-4 text-gray-600">Aucune commande.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
