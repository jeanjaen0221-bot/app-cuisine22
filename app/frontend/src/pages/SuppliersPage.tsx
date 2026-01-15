import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Supplier, SupplierCreate } from '../types'

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const res = await api.get('/api/suppliers')
      setSuppliers(res.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function add() {
    if (!name.trim()) return
    const payload: SupplierCreate = { name: name.trim(), email: email || undefined, phone: phone || undefined }
    await api.post('/api/suppliers', payload)
    setName('')
    setEmail('')
    setPhone('')
    await load()
  }

  async function toggleActive(id: string, active: boolean) {
    await api.put(`/api/suppliers/${id}`, { active })
    await load()
  }

  return (
    <div className="container space-y-4">
      <div className="card">
        <div className="card-header">
          <h3 className="text-lg font-semibold">Fournisseurs</h3>
          <div className="flex items-center gap-3">
            <button className="btn btn-outline btn-sm" onClick={load} disabled={loading}>{loading ? '...' : 'Rafraîchir'}</button>
          </div>
        </div>
        <div className="card-body space-y-4">
          <div className="controls-hint">Ajouter un fournisseur</div>
          <div className="drinks-grid">
            <input className="input" placeholder="Nom" value={name} onChange={(e) => setName(e.target.value)} />
            <input className="input" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <input className="input" placeholder="Téléphone" value={phone} onChange={(e) => setPhone(e.target.value)} />
            <button className="btn btn-primary" onClick={add}>Ajouter</button>
          </div>

          <div className="drinks-table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Nom</th>
                  <th>Email</th>
                  <th>Téléphone</th>
                  <th>Actif</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {suppliers.map((s) => (
                  <tr key={s.id}>
                    <td className="font-medium">{s.name}</td>
                    <td>{s.email || '-'}</td>
                    <td>{s.phone || '-'}</td>
                    <td>{s.active ? 'Oui' : 'Non'}</td>
                    <td>
                      <button className="btn btn-sm btn-outline" onClick={() => toggleActive(s.id, !s.active)}>{s.active ? 'Désactiver' : 'Activer'}</button>
                    </td>
                  </tr>
                ))}
                {suppliers.length === 0 && (
                  <tr>
                    <td colSpan={5} className="p-4 text-gray-600">Aucun fournisseur.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
