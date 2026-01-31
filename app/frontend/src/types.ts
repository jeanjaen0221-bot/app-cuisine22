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

// --- Suppliers & Purchasing ---
export type Supplier = {
  id: UUID
  name: string
  email?: string
  phone?: string
  notes?: string
  active: boolean
}

export type SupplierCreate = {
  name: string
  email?: string
  phone?: string
  notes?: string
  active?: boolean
}

export type PurchaseOrderItem = {
  id: UUID
  order_id: UUID
  drink_id?: UUID | null
  name: string
  unit?: string | null
  quantity: number
  price_cents?: number | null
}

export type PurchaseOrder = {
  id: UUID
  supplier_id?: UUID | null
  status: 'draft' | 'sent' | 'received' | 'cancelled'
  note?: string | null
  created_at: string
  items: PurchaseOrderItem[]
}

export type PurchaseOrderItemCreate = {
  drink_id?: UUID | null
  name?: string
  unit?: string
  quantity: number
  price_cents?: number | null
}

export type PurchaseOrderCreate = {
  supplier_id?: UUID | null
  note?: string | null
  items: PurchaseOrderItemCreate[]
}

// --- Floor plan ---
export type FloorPlanFixedTable = {
  id: string
  x: number
  y: number
  rotation?: number
  seats: number
  label?: string
}

export type FloorPlanObstacle = {
  id: string
  type: 'rect' | 'circle' | 'poly'
  x?: number
  y?: number
  width?: number
  height?: number
  radius?: number
  points?: { x: number; y: number }[]
}

export type FloorPlanZone = {
  id: string
  kind: 'circulation' | 'reservable' | 'forbidden'
  points: { x: number; y: number }[]
}

export type FloorPlanServiceElement = {
  id: string
  kind: 'service_round' | 'desk' | 'custom'
  x: number
  y: number
  radius?: number
  width?: number
  height?: number
}

export type FloorPlanLayout = {
  fixedTables: FloorPlanFixedTable[]
  obstacles?: FloorPlanObstacle[]
  zones?: FloorPlanZone[]
  serviceElements?: FloorPlanServiceElement[]
  movableTables6Count?: number
  round10ReserveCount?: number
}

export type FloorPlanTemplate = {
  id: UUID
  name: string
  width: number
  height: number
  layout: FloorPlanLayout
  created_at: string
  updated_at: string
}

export type AssignmentTable = { type: 'fixed' | 't6' | 'r10'; id: string; seats?: number; head?: boolean }

export type FloorPlanAssignment = {
  name: string
  pax: number
  tables: AssignmentTable[]
}

export type FloorPlanInstance = {
  id: UUID
  template_id: UUID
  service_date: string
  service_label: string
  assignments: Record<string, FloorPlanAssignment>
  layout_overrides: any
  created_at: string
  updated_at: string
}

export type ParsedReservation = {
  name: string
  pax: number
  service_date?: string | null
  arrival_time?: string | null
  reference?: string | null
  constraints?: string | null
}
