import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from './api'
import type { Moi, References } from './types'

type Session = {
  moi: Moi
  references: References | null
  rechargerReferences: () => Promise<void>
  prixManquants: number
  rechargerCompteur: () => void
  deconnecter: () => Promise<void>
}

const Contexte = createContext<Session | null>(null)

export function useSession(): Session {
  const valeur = useContext(Contexte)
  if (!valeur) throw new Error('Session absente')
  return valeur
}

export function FournisseurSession({ moi, surDeconnexion, children }: {
  moi: Moi
  surDeconnexion: () => void
  children: React.ReactNode
}) {
  const [references, setReferences] = useState<References | null>(null)
  const [prixManquants, setPrixManquants] = useState(0)

  const rechargerReferences = useCallback(async () => {
    setReferences(await api.get<References>('/api/references'))
  }, [])
  const rechargerCompteur = useCallback(() => {
    api.get<{ nombre: number }>('/api/produits/manquants').then((r) => setPrixManquants(r.nombre)).catch(() => {})
  }, [])

  useEffect(() => {
    rechargerReferences().catch(() => {})
    rechargerCompteur()
  }, [rechargerReferences, rechargerCompteur])

  const deconnecter = async () => {
    await api.post('/api/auth/deconnexion').catch(() => {})
    surDeconnexion()
  }

  return (
    <Contexte.Provider value={{ moi, references, rechargerReferences, prixManquants, rechargerCompteur, deconnecter }}>
      {children}
    </Contexte.Provider>
  )
}
