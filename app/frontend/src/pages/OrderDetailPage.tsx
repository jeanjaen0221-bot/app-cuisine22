import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, fileDownload } from '../lib/api'
import type { Drink, PurchaseOrder } from '../types'

export default function OrderDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [order, setOrder] = useState<PurchaseOrder | null>(null)
  const [drinks, setDrinks] = useState<Drink[]>([])
  const [status, setStatus] = useState('draft')
  const [loading, setLoading] = useState(false)
  const [addDrinkId, setAddDrinkId] = useState('')
  const [addQty, setAddQty] = useState(1)

  const orderId = id as string

  const drinkOptions = useMemo(() => drinks.map((d) => ({ value: d.id, label: d.name })), [drinks])

  async function load() {
    setLoading(true)
    try {
      const [o, d] = await Promise.all([
        api.get(`/api/purchase-orders/${orderId}`),
        api.get('/api/drinks'),
      ])
      setOrder(o.data)
      setStatus(o.data.status)
      setDrinks(d.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!orderId) return
    load()
  }, [orderId])

  async function updateStatus() {
    if (!order) return
    const res = await api.put(`/api/purchase-orders/${order.id}`, { status })
    setOrder(res.data)
  }

  async function addItem() {
    if (!order) return
    if (!addDrinkId || addQty <= 0) return
    const res = await api.post(`/api/purchase-orders/${order.id}/items`, { drink_id: addDrinkId, quantity: addQty })
    setOrder(res.data)
    setAddDrinkId('')
    setAddQty(1)
  }

  async function removeItem(itemId: string) {
    if (!order) return
    await api.delete(`/api/purchase-orders/${order.id}/items/${itemId}`)
    await load()
  }

  function exportCsv() {
    fileDownload(`/api/purchase-orders/${orderId}/export.csv`)
  }

  return (
    <div className="container space-y-4">
      <div className="card">
        <div className="card-header">
          <h3 className="text-lg font-semibold">Commande d'achat</h3>
          <div className="flex items-center gap-2">
            <button className="btn btn-outline btn-sm" onClick={() => navigate('/achats')}>Retour</button>
            <button className="btn btn-outline btn-sm" onClick={exportCsv} disabled={!order}>Export CSV</button>
          </div>
        </div>
        <div className="card-body space-y-4">
          {order && (
            <>
              <div className="drinks-grid order-meta-grid">
                <div>
                  <div className="text-xs text-gray-600">ID</div>
                  <div className="font-mono text-xs break-all">{order.id}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600">Créée</div>
                  <div>{new Date(order.created_at).toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600">Statut</div>
                  <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
                    <option value="draft">draft</option>
                    <option value="sent">sent</option>
                    <option value="received">received</option>
                    <option value="cancelled">cancelled</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <button className="btn btn-primary" onClick={updateStatus}>Enregistrer</button>
                </div>
              </div>

              <div>
                <div className="controls-hint">Ajouter un article</div>
                <div className="drinks-grid order-add-grid">
                  <select className="input" value={addDrinkId} onChange={(e) => setAddDrinkId(e.target.value)}>
                    <option value="">Sélectionner une boisson</option>
                    {drinkOptions.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                  <input className="input" type="number" value={addQty} onChange={(e) => setAddQty(parseInt(e.target.value || '0') || 0)} />
                  <button className="btn btn-primary" onClick={addItem}>Ajouter</button>
                </div>
              </div>

              <div className="drinks-table-container">
                <table className="table drinks-table">
                  <thead>
                    <tr>
                      <th>Article</th>
                      <th>Unité</th>
                      <th>Quantité</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {order.items.map((it) => (
                      <tr key={it.id}>
                        <td>{it.name}</td>
                        <td>{it.unit || '-'}</td>
                        <td>{it.quantity}</td>
                        <td>
                          <button className="btn btn-sm btn-outline" onClick={() => removeItem(it.id)}>Supprimer</button>
                        </td>
                      </tr>
                    ))}
                    {order.items.length === 0 && (
                      <tr>
                        <td colSpan={4} className="p-4 text-gray-600">Aucun article</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {!order && <div className="p-4 text-gray-600">{loading ? 'Chargement...' : 'Commande introuvable.'}</div>}
        </div>
      </div>
    </div>
  )
}
