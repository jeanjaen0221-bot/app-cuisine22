import { useCallback, useEffect, useState } from 'react'
import { messageErreur } from '../api'

/** Charge une donnée et la recharge à la demande. */
export function useCharger<T>(charger: () => Promise<T>, dependances: unknown[] = []) {
  const [donnees, setDonnees] = useState<T | null>(null)
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(true)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const recharger = useCallback(async () => {
    setChargement(true)
    try {
      setDonnees(await charger())
      setErreur('')
    } catch (e) {
      setErreur(messageErreur(e))
    } finally {
      setChargement(false)
    }
  }, dependances)
  useEffect(() => { recharger() }, [recharger])
  return { donnees, setDonnees, erreur, chargement, recharger }
}

/** Lance une action, affiche son erreur, empêche le double clic. */
export function useAction() {
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')
  const lancer = async <T,>(action: () => Promise<T>): Promise<T | undefined> => {
    setEnCours(true)
    setErreur('')
    try {
      return await action()
    } catch (e) {
      setErreur(messageErreur(e))
      return undefined
    } finally {
      setEnCours(false)
    }
  }
  return { enCours, erreur, setErreur, lancer }
}

export function Erreur({ message }: { message?: string }) {
  if (!message) return null
  return <div className="bandeau erreur" role="alert">{message}</div>
}

export function Alertes({ liste, titre }: { liste?: string[]; titre?: string }) {
  if (!liste?.length) return null
  return (
    <div className="bandeau attention">
      {titre && <strong>{titre}</strong>}
      <ul>{liste.map((a) => <li key={a}>{a}</li>)}</ul>
    </div>
  )
}

const COULEURS_STATUT: Record<string, string> = {
  brouillon: 'gris', confirmee: 'bleu', finale: 'violet', realisee: 'vert', annulee: 'rouge',
  valide: 'bleu', transmis: 'ambre', envoye: 'violet', accepte: 'vert', refuse: 'rouge', remplace: 'gris',
  facture: 'vert',
}

export function Statut({ statut, libelle }: { statut: string; libelle: string }) {
  return <span className={`pastille ${COULEURS_STATUT[statut] ?? 'gris'}`}>{libelle}</span>
}

export function Pastille({ couleur, children }: { couleur: string; children: React.ReactNode }) {
  return <span className={`pastille ${couleur}`}>{children}</span>
}

export function Champ({ libelle, children, aide, large }: {
  libelle: string; children: React.ReactNode; aide?: string; large?: boolean
}) {
  return (
    <label className={`champ${large ? ' large' : ''}`}>
      <span className="champ-libelle">{libelle}</span>
      {children}
      {aide && <span className="aide">{aide}</span>}
    </label>
  )
}

export function Chargement({ actif }: { actif: boolean }) {
  return actif ? <p className="muet">Chargement…</p> : null
}

export function EnTete({ titre, children, sousTitre }: { titre: string; children?: React.ReactNode; sousTitre?: React.ReactNode }) {
  return (
    <header className="en-tete">
      <div>
        <h1>{titre}</h1>
        {sousTitre && <div className="muet">{sousTitre}</div>}
      </div>
      {children && <div className="actions">{children}</div>}
    </header>
  )
}
