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
