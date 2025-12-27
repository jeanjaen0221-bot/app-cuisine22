export type UUID = string

export type ReservationItem = {
  id?: UUID
  type: 'entrée' | 'plat' | 'dessert' | string
  name: string
  quantity: number
  comment?: string
}

export type Reservation = {
  id: UUID
  client_name: string
  pax: number
  service_date: string
  arrival_time: string
  drink_formula: string
  notes?: string
  status: 'draft' | 'confirmed' | 'printed'
  final_version: boolean
  on_invoice: boolean
  allergens?: string
  created_at: string
  updated_at: string
  last_pdf_exported_at?: string | null
  items: ReservationItem[]
}

export type ReservationCreate = Omit<Reservation, 'id' | 'created_at' | 'updated_at' | 'last_pdf_exported_at'>

export type MenuItem = {
  id: UUID
  name: string
  type: 'entrée' | 'plat' | 'dessert' | string
  active: boolean
}

export type Note = {
  id: UUID
  name: string
  content: string
  created_at: string
  updated_at: string
}

export type Drink = {
  id: UUID
  name: string
  category?: string
  unit?: string
  active: boolean
}

export type DrinkStock = {
  drink_id: UUID
  min_qty: number
  max_qty: number
  pack_size?: number | null
  reorder_enabled: boolean
}

export type ReplenishOptions = {
  target: 'max' | 'min'
  rounding: 'pack' | 'none'
}

export type ReplenishItem = {
  drink_id: UUID
  name: string
  unit?: string
  remaining: number
  min_qty: number
  max_qty: number
  pack_size?: number | null
  reorder_enabled: boolean
  target: number
  suggest: number
}

export type ReplenishResponse = {
  items: ReplenishItem[]
}
