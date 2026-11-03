// Appels à l'API. La session est un cookie HttpOnly : rien n'est gardé dans le navigateur.
// Chaque écriture porte l'en-tête X-Albert exigé par le serveur (protection CSRF).

export type ErreurApi = {
  code: string
  message: string
  champ?: string
  valeurs_permises?: string[]
  details?: Record<string, unknown>
}

export class Echec extends Error {
  erreur: ErreurApi
  statut: number
  constructor(statut: number, erreur: ErreurApi) {
    super(erreur.message)
    this.statut = statut
    this.erreur = erreur
  }
}

async function appeler<T>(methode: string, chemin: string, corps?: unknown): Promise<T> {
  const reponse = await fetch(chemin, {
    method: methode,
    credentials: 'same-origin',
    headers: {
      'X-Albert': '1',
      ...(corps !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    body: corps !== undefined ? JSON.stringify(corps) : undefined,
  })
  const texte = await reponse.text()
  const donnees = texte ? JSON.parse(texte) : null
  if (!reponse.ok) {
    const erreur: ErreurApi = donnees?.erreur ?? { code: 'erreur_serveur', message: 'Erreur inattendue.' }
    if (reponse.status === 401 && !chemin.startsWith('/api/auth/')) {
      window.dispatchEvent(new Event('albert:deconnecte'))
    }
    throw new Echec(reponse.status, erreur)
  }
  return donnees as T
}

export const api = {
  get: <T,>(chemin: string, params?: Record<string, string | number | boolean | undefined | null>) => {
    const recherche = new URLSearchParams()
    for (const [cle, valeur] of Object.entries(params ?? {})) {
      if (valeur !== undefined && valeur !== null && valeur !== '') recherche.set(cle, String(valeur))
    }
    const suffixe = recherche.toString()
    return appeler<T>('GET', suffixe ? `${chemin}?${suffixe}` : chemin)
  },
  post: <T,>(chemin: string, corps: unknown = {}) => appeler<T>('POST', chemin, corps),
  patch: <T,>(chemin: string, corps: unknown) => appeler<T>('PATCH', chemin, corps),
  delete: <T,>(chemin: string) => appeler<T>('DELETE', chemin),
}

export function messageErreur(e: unknown): string {
  if (e instanceof Echec) {
    const { message, valeurs_permises } = e.erreur
    return valeurs_permises?.length ? `${message} Valeurs permises : ${valeurs_permises.join(', ')}.` : message
  }
  return e instanceof Error ? e.message : String(e)
}

export function ouvrirPdf(chemin: string) {
  window.open(chemin, '_blank', 'noopener')
}

export const formatDate = (iso?: string | null) => {
  if (!iso) return ''
  const [a, m, j] = iso.slice(0, 10).split('-')
  return `${j}/${m}/${a}`
}

const JOURS = ['dim.', 'lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.']
export const formatJour = (iso: string) => {
  const d = new Date(`${iso}T12:00:00`)
  return `${JOURS[d.getDay()]} ${formatDate(iso)}`
}

export const formatInstant = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString('fr-BE', { dateStyle: 'short', timeStyle: 'short' }) : ''

export const euros = (centimes?: number | null) =>
  centimes === null || centimes === undefined
    ? 'prix manquant'
    : (centimes / 100).toLocaleString('fr-BE', { style: 'currency', currency: 'EUR' })

export const aujourdhui = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
