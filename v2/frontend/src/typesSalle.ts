// Format du plan de salle (repris tel quel de l'ancienne version, pour garder les plans existants).

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
  dynamic?: boolean
}

export type FloorRect = { id: string; x: number; y: number; w: number; h: number }
export type FloorCircle = { id: string; x: number; y: number; r: number }

export type FloorZone = { id: string; label: string; x: number; y: number; w: number; h: number; color?: string }

export type LargeTableConfig = {
  pax_threshold_right?: number
  pax_threshold_vertical?: number
  vertical_span_max?: number
}

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
  fixed_chair_stock?: number
  large_table_config?: LargeTableConfig
  zones?: FloorZone[]
}

export type AssignmentMap = {
  tables: Record<string, { res_id: string; name: string; pax: number; last_resort?: boolean }>
  alerts?: string[]
}
