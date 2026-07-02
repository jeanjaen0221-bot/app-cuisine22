import type { ReservationItem } from '../types'

export const normType = (s: string): string =>
  s.toLowerCase().replace(/[éè]/g, 'e').trim()

export function deduceFormula(items: ReservationItem[]): string {
  const types = new Set(items.map(i => normType(i.type)))
  const hasEntree = types.has('entree') || types.has('entrees')
  const hasPlat = types.has('plat') || types.has('plats')
  const hasDessert = types.has('dessert') || types.has('desserts')
  if (hasEntree && hasPlat && hasDessert) return '3 services (Entrée · Plat · Dessert)'
  if (hasEntree && hasPlat) return '2 services (Entrée · Plat)'
  if (hasPlat && hasDessert) return '2 services (Plat · Dessert)'
  if (hasPlat) return '1 service (Plat)'
  return '—'
}
