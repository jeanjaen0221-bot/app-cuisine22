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

export type ServiceLabel = 'lunch' | 'dinner' | (string & {})

export type FloorTable = {
  id: string
  kind: 'fixed' | 'rect' | 'round' | 'sofa' | 'standing'
  x: number
  y: number
  w?: number
  h?: number
  r?: number
  capacity?: number
  locked?: boolean
  label?: string
}

export type FloorRect = { id: string; x: number; y: number; w: number; h: number }
export type FloorCircle = { id: string; x: number; y: number; r: number }

export type FloorPlanData = {
  room?: { width: number; height: number; grid?: number }
  walls?: FloorRect[]
  columns?: FloorCircle[]
  no_go?: FloorRect[]
  round_only_zones?: FloorRect[]
  rect_only_zones?: FloorRect[]
  fixtures?: ((FloorRect & { shape?: 'rect'; label?: string; locked?: boolean }) | (FloorCircle & { shape?: 'round'; label?: string; locked?: boolean }))[]
  tables: FloorTable[]
  max_dynamic_tables?: { rect?: number; round?: number }
}

export type AssignmentMap = {
  tables: Record<string, { res_id: string; name: string; pax: number; last_resort?: boolean }>
}

export type FloorPlanBase = {
  id: UUID
  name: string
  data: FloorPlanData
  created_at: string
  updated_at: string
}

export type FloorPlanInstance = {
  id: UUID
  service_date: string
  service_label?: string | null
  template_id?: UUID
  data: FloorPlanData
  assignments: AssignmentMap
  reservations?: { items: any[] }
  created_at: string
  updated_at: string
}
