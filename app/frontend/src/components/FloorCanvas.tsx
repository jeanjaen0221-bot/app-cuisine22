import { useEffect, useMemo, useRef, useState } from 'react'
import type { AssignmentMap, FloorCircle, FloorPlanData, FloorRect, FloorTable } from '../types'

type Props = {
  data: FloorPlanData
  assignments?: AssignmentMap
  editable?: boolean
  showGrid?: boolean
  onChange?: (data: FloorPlanData) => void
  className?: string
  drawNoGoMode?: boolean
}

export default function FloorCanvas({ data, assignments, editable = true, showGrid = true, onChange, className, drawNoGoMode = false }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [size, setSize] = useState({ w: 0, h: 0 })
  const [scale, setScale] = useState(1)
  const [offset, setOffset] = useState({ x: 50, y: 50 })
  const [draggingId, setDraggingId] = useState<string | null>(null)
  const [isPanning, setIsPanning] = useState(false)
  const dragDelta = useRef({ x: 0, y: 0 })
  const [resizeHandle, setResizeHandle] = useState<'none' | 'right' | 'bottom' | 'corner'>('none')
  const [fixtureDraggingId, setFixtureDraggingId] = useState<string | null>(null)
  const [fixtureResize, setFixtureResize] = useState<{
    id: string
    shape: 'rect' | 'round'
    handle: 'right' | 'bottom' | 'corner' | 'radius'
  } | null>(null)
  const [noGoDraggingId, setNoGoDraggingId] = useState<string | null>(null)
  const [noGoResize, setNoGoResize] = useState<{ id: string; handle: 'right' | 'bottom' | 'corner' } | null>(null)
  const dragStart = useRef<{ x: number; y: number } | null>(null)
  const lastValid = useRef<{ x: number; y: number } | null>(null)
  const dragInvalid = useRef(false)
  const [draftNoGo, setDraftNoGo] = useState<FloorRect | null>(null)
  const drawStartNoGo = useRef<{ x: number; y: number } | null>(null)

  const room = data.room || { width: 1200, height: 800, grid: 50 }
  const tables = data.tables || []
  const walls = data.walls || []
  const cols = data.columns || []
  const noGo = data.no_go || []
  const fixtures = data.fixtures || []

  useEffect(() => {
    const el = canvasRef.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      setSize({ w: el.clientWidth, h: el.clientHeight })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  function worldToScreen(x: number, y: number) {
    return { x: x * scale + offset.x, y: y * scale + offset.y }
  }

  function noGoHandleAt(sx: number, sy: number): { id: string; handle: 'right' | 'bottom' | 'corner' } | null {
    const M = 12
    const list = [...noGo].reverse()
    for (const r of list) {
      const cr = worldToScreen(r.x + r.w, r.y + r.h)
      if (Math.abs(sx - cr.x) <= M && Math.abs(sy - cr.y) <= M) return { id: r.id, handle: 'corner' }
      const rr = worldToScreen(r.x + r.w, r.y + r.h / 2)
      if (Math.abs(sx - rr.x) <= M && Math.abs(sy - rr.y) <= M) return { id: r.id, handle: 'right' }
      const bb = worldToScreen(r.x + r.w / 2, r.y + r.h)
      if (Math.abs(sx - bb.x) <= M && Math.abs(sy - bb.y) <= M) return { id: r.id, handle: 'bottom' }
    }
    return null
  }

  function noGoHit(x: number, y: number) {
    const list = [...noGo].reverse()
    for (const r of list) {
      if (rectHit(x, y, r)) return r
    }
    return null
  }
  function screenToWorld(x: number, y: number) {
    return { x: (x - offset.x) / scale, y: (y - offset.y) / scale }
  }

  function rectHit(px: number, py: number, r: FloorRect) {
    return px >= r.x && py >= r.y && px <= r.x + r.w && py <= r.y + r.h
  }
  function circleHit(px: number, py: number, c: FloorCircle) {
    const dx = px - c.x
    const dy = py - c.y
    return dx * dx + dy * dy <= (c.r || 0) * (c.r || 0)
  }
  function tableHit(px: number, py: number, t: FloorTable) {
    if (t.r) return circleHit(px, py, { id: t.id, x: t.x, y: t.y, r: t.r })
    const w = t.w || 120
    const h = t.h || 60
    return rectHit(px, py, { id: t.id, x: t.x, y: t.y, w, h })
  }

  function handleAt(sx: number, sy: number): 'none' | 'right' | 'bottom' | 'corner' {
    const M = 12
    const br = worldToScreen(room.width, room.height)
    if (Math.abs(sx - br.x) <= M && Math.abs(sy - br.y) <= M) return 'corner'
    const rmid = worldToScreen(room.width, room.height / 2)
    if (Math.abs(sx - rmid.x) <= M && Math.abs(sy - rmid.y) <= M) return 'right'
    const bmid = worldToScreen(room.width / 2, room.height)
    if (Math.abs(sx - bmid.x) <= M && Math.abs(sy - bmid.y) <= M) return 'bottom'
    return 'none'
  }

  function fixtureHandleAt(sx: number, sy: number): { id: string; shape: 'rect' | 'round'; handle: 'right' | 'bottom' | 'corner' | 'radius' } | null {
    const M = 12
    const list = [...fixtures].reverse() as any[]
    for (const fx of list) {
      if ((fx as any).locked) continue
      if ('r' in fx) {
        const p = worldToScreen(fx.x + fx.r, fx.y)
        if (Math.abs(sx - p.x) <= M && Math.abs(sy - p.y) <= M) return { id: fx.id, shape: 'round', handle: 'radius' }
      } else {
        const cr = worldToScreen(fx.x + fx.w, fx.y + fx.h)
        if (Math.abs(sx - cr.x) <= M && Math.abs(sy - cr.y) <= M) return { id: fx.id, shape: 'rect', handle: 'corner' }
        const rr = worldToScreen(fx.x + fx.w, fx.y + fx.h / 2)
        if (Math.abs(sx - rr.x) <= M && Math.abs(sy - rr.y) <= M) return { id: fx.id, shape: 'rect', handle: 'right' }
        const bb = worldToScreen(fx.x + fx.w / 2, fx.y + fx.h)
        if (Math.abs(sx - bb.x) <= M && Math.abs(sy - bb.y) <= M) return { id: fx.id, shape: 'rect', handle: 'bottom' }
      }
    }
    return null
  }

  function fixtureHit(x: number, y: number) {
    const list = [...fixtures].reverse() as any[]
    for (const fx of list) {
      if ('r' in fx) {
        if (circleHit(x, y, { id: fx.id, x: fx.x, y: fx.y, r: fx.r })) return fx
      } else {
        if (rectHit(x, y, { id: fx.id, x: fx.x, y: fx.y, w: fx.w, h: fx.h })) return fx
      }
    }
    return null
  }

  function intersectsRectRect(a: FloorRect, b: FloorRect) {
    return !(a.x + a.w < b.x || b.x + b.w < a.x || a.y + a.h < b.y || b.y + b.h < a.y)
  }
  function intersectsCircleRect(c: FloorCircle, r: FloorRect) {
    const cx = Math.max(r.x, Math.min(c.x, r.x + r.w))
    const cy = Math.max(r.y, Math.min(c.y, r.y + r.h))
    const dx = c.x - cx
    const dy = c.y - cy
    return dx * dx + dy * dy <= (c.r || 0) * (c.r || 0)
  }
  function intersectsCircleCircle(a: FloorCircle, b: FloorCircle) {
    const dx = a.x - b.x
    const dy = a.y - b.y
    const ra = a.r || 0
    const rb = b.r || 0
    const rr = ra + rb
    return dx * dx + dy * dy <= rr * rr
  }

  function tableCollides(t: FloorTable) {
    if (t.r) {
      const c: FloorCircle = { id: t.id, x: t.x, y: t.y, r: t.r }
      // bounds
      if (c.x - (c.r || 0) < 0 || c.y - (c.r || 0) < 0 || c.x + (c.r || 0) > room.width || c.y + (c.r || 0) > room.height) return true
      for (const r of noGo) if (intersectsCircleRect(c, r)) return true
      for (const r of walls) if (intersectsCircleRect(c, r)) return true
      for (const col of cols) { if (intersectsCircleCircle(c, col)) return true }
      for (const f of fixtures) {
        if ('r' in (f as any)) { if (intersectsCircleCircle(c, f as any)) return true }
        else { if (intersectsCircleRect(c, f as any)) return true }
      }
      // collide with other tables
      for (const ot of tables) {
        if (ot.id === t.id) continue
        if (ot.r) {
          if (intersectsCircleCircle(c, { id: ot.id, x: ot.x, y: ot.y, r: ot.r })) return true
        } else {
          const rr: FloorRect = { id: ot.id, x: ot.x, y: ot.y, w: ot.w || 120, h: ot.h || 60 }
          if (intersectsCircleRect(c, rr)) return true
        }
      }
      return false
    } else {
      const w = t.w || 120
      const h = t.h || 60
      const rr: FloorRect = { id: t.id, x: t.x, y: t.y, w, h }
      // bounds
      if (rr.x < 0 || rr.y < 0 || rr.x + rr.w > room.width || rr.y + rr.h > room.height) return true
      for (const r of noGo) if (intersectsRectRect(rr, r)) return true
      for (const r of walls) if (intersectsRectRect(rr, r)) return true
      for (const col of cols) if (intersectsCircleRect(col, rr)) return true
      for (const f of fixtures) {
        if ('r' in (f as any)) { if (intersectsCircleRect(f as any, rr)) return true }
        else { if (intersectsRectRect(rr, f as any)) return true }
      }
      // collide with other tables
      for (const ot of tables) {
        if (ot.id === t.id) continue
        if (ot.r) {
          const oc: FloorCircle = { id: ot.id, x: ot.x, y: ot.y, r: ot.r }
          if (intersectsCircleRect(oc, rr)) return true
        } else {
          const orr: FloorRect = { id: ot.id, x: ot.x, y: ot.y, w: ot.w || 120, h: ot.h || 60 }
          if (intersectsRectRect(rr, orr)) return true
        }
      }
      return false
    }
  }

  function draw() {
    const el = canvasRef.current
    if (!el) return
    const ctx = el.getContext('2d')
    if (!ctx) return
    const W = el.width = el.clientWidth
    const H = el.height = el.clientHeight
    ctx.clearRect(0, 0, W, H)

    if (showGrid) {
      const g = room.grid || 50
      ctx.save()
      ctx.translate(offset.x % (g * scale), offset.y % (g * scale))
      ctx.strokeStyle = 'rgba(180,180,200,0.4)'
      ctx.lineWidth = 1
      for (let x = 0; x < W + g * scale; x += g * scale) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
      }
      for (let y = 0; y < H + g * scale; y += g * scale) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
      }
      ctx.restore()
    }

    ctx.save()
    ctx.translate(offset.x, offset.y)
    ctx.scale(scale, scale)

    ctx.strokeStyle = '#222'
    ctx.lineWidth = 2 / scale
    ctx.strokeRect(0, 0, room.width, room.height)

    const hs = 8 / scale
    ctx.fillStyle = '#222'
    ctx.fillRect(room.width - hs / 2, room.height - hs / 2, hs, hs)
    ctx.fillRect(room.width - hs / 2, room.height / 2 - hs / 2, hs, hs)
    ctx.fillRect(room.width / 2 - hs / 2, room.height - hs / 2, hs, hs)

    ctx.fillStyle = '#999'
    for (const w of walls) ctx.fillRect(w.x, w.y, w.w, w.h)

    ctx.fillStyle = '#666'
    for (const c of cols) { ctx.beginPath(); ctx.arc(c.x, c.y, c.r, 0, Math.PI * 2); ctx.fill() }

    ctx.fillStyle = '#bbb'
    for (const r of noGo) {
      ctx.fillRect(r.x, r.y, r.w, r.h)
      if (editable) {
        const hs2 = 6 / scale
        ctx.fillStyle = '#555'
        ctx.fillRect(r.x + r.w - hs2 / 2, r.y + r.h - hs2 / 2, hs2, hs2)
        ctx.fillRect(r.x + r.w - hs2 / 2, r.y + r.h / 2 - hs2 / 2, hs2, hs2)
        ctx.fillRect(r.x + r.w / 2 - hs2 / 2, r.y + r.h - hs2 / 2, hs2, hs2)
        ctx.fillStyle = '#bbb'
      }
    }

    if (draftNoGo) {
      ctx.save()
      ctx.globalAlpha = 0.35
      ctx.fillStyle = '#c66'
      ctx.fillRect(draftNoGo.x, draftNoGo.y, draftNoGo.w, draftNoGo.h)
      ctx.restore()
      ctx.save()
      ctx.strokeStyle = '#c00'
      ctx.setLineDash([6 / scale, 6 / scale])
      ctx.lineWidth = 2 / scale
      ctx.strokeRect(draftNoGo.x, draftNoGo.y, draftNoGo.w, draftNoGo.h)
      ctx.restore()
    }

    for (const fx of fixtures) {
      ctx.fillStyle = '#8b8'
      if ('r' in fx) { ctx.beginPath(); ctx.arc((fx as any).x, (fx as any).y, (fx as any).r, 0, Math.PI * 2); ctx.fill() }
      else ctx.fillRect((fx as any).x, (fx as any).y, (fx as any).w, (fx as any).h)
      const label = (fx as any).label
      if (label) {
        ctx.fillStyle = '#111'
        ctx.font = `${12/scale}px sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        const cx = 'r' in fx ? (fx as any).x : (fx as any).x + (fx as any).w/2
        const cy = 'r' in fx ? (fx as any).y : (fx as any).y + (fx as any).h/2
        ctx.fillText(label, cx, cy)
      }
      if (!(fx as any).locked && editable) {
        const hs2 = 6 / scale
        ctx.fillStyle = '#444'
        if ('r' in fx) {
          ctx.fillRect((fx as any).x + (fx as any).r - hs2 / 2, (fx as any).y - hs2 / 2, hs2, hs2)
        } else {
          ctx.fillRect((fx as any).x + (fx as any).w - hs2 / 2, (fx as any).y + (fx as any).h - hs2 / 2, hs2, hs2)
          ctx.fillRect((fx as any).x + (fx as any).w - hs2 / 2, (fx as any).y + (fx as any).h / 2 - hs2 / 2, hs2, hs2)
          ctx.fillRect((fx as any).x + (fx as any).w / 2 - hs2 / 2, (fx as any).y + (fx as any).h - hs2 / 2, hs2, hs2)
        }
      }
    }

    for (const t of tables) {
      const assigned = assignments?.tables?.[t.id]
      const isLocked = !!t.locked
      const coll = tableCollides(t)
      let color = t.kind === 'fixed' ? '#2c7' : t.kind === 'rect' ? '#39f' : '#f93'
      if (isLocked) color = '#2a5'
      ctx.fillStyle = color
      ctx.strokeStyle = coll ? '#e00' : '#111'
      ctx.lineWidth = 2 / scale
      if (t.r) {
        ctx.beginPath(); ctx.arc(t.x, t.y, t.r, 0, Math.PI * 2); ctx.fill(); ctx.stroke()
      } else {
        const w = t.w || 120, h = t.h || 60
        ctx.fillRect(t.x, t.y, w, h)
        ctx.strokeRect(t.x, t.y, w, h)
      }
      const cx = t.r ? t.x : t.x + (t.w || 120) / 2
      const cy = t.r ? t.y : t.y + (t.h || 60) / 2
      const cap = (t.capacity || (t.kind === 'rect' ? 6 : t.kind === 'round' ? 10 : 2)) + ''
      const lbl = (t.label || '').toString()
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      if (lbl) {
        ctx.fillStyle = '#fff'
        ctx.font = `${16/scale}px sans-serif`
        ctx.fillText(lbl, cx, cy)
      } else {
        ctx.fillStyle = '#fff'
        ctx.font = `${14/scale}px sans-serif`
        ctx.fillText(cap, cx, cy)
      }
      if (assigned) {
        ctx.fillStyle = '#000'
        ctx.font = `${12/scale}px sans-serif`
        ctx.textAlign = 'left'
        ctx.fillText(`${assigned.name} (${assigned.pax})`, (t.r ? t.x + (t.r||0) : t.x + (t.w||120)) + 6, t.y + 10)
      }
    }

    ctx.restore()
  }

  useEffect(() => { draw() })
  useEffect(() => { draw() }, [size, scale, offset, data, assignments, showGrid, draftNoGo])

  function onPointerDown(e: React.PointerEvent) {
    const rect = (e.target as HTMLCanvasElement).getBoundingClientRect()
    const sx = e.clientX - rect.left
    const sy = e.clientY - rect.top
    const { x, y } = screenToWorld(sx, sy)
    const fr = fixtureHandleAt(sx, sy)
    if (editable && fr) {
      const fx: any = (fixtures as any[]).find(f => f.id === fr.id)
      if (fx && !fx.locked) {
        setFixtureResize(fr)
      }
      return
    }
    const f = fixtureHit(x, y)
    if (editable && f) {
      if (!(f as any).locked) {
        setFixtureDraggingId((f as any).id)
        dragDelta.current = { x: x - (f as any).x, y: y - (f as any).y }
      }
      return
    }
    const ngr = noGoHandleAt(sx, sy)
    if (editable && ngr) {
      setNoGoResize(ngr)
      return
    }
    const ng = noGoHit(x, y)
    if (editable && ng) {
      setNoGoDraggingId(ng.id)
      dragDelta.current = { x: x - ng.x, y: y - ng.y }
      return
    }
    const hit = [...tables].reverse().find(t => tableHit(x, y, t))
    if (hit && editable && !hit.locked) {
      setDraggingId(hit.id)
      dragStart.current = { x: hit.x, y: hit.y }
      lastValid.current = { x: hit.x, y: hit.y }
      dragInvalid.current = false
      dragDelta.current = { x: x - hit.x, y: y - hit.y }
      return
    }
    const h = handleAt(sx, sy)
    if (editable && h !== 'none') {
      setResizeHandle(h)
      return
    }
    if (editable && drawNoGoMode) {
      if (x >= 0 && y >= 0 && x <= room.width && y <= room.height) {
        const snapGrid = showGrid && room.grid && room.grid > 0
        const sx0 = snapGrid ? snap(x) : x
        const sy0 = snapGrid ? snap(y) : y
        drawStartNoGo.current = { x: sx0, y: sy0 }
        setDraftNoGo({ id: 'draft', x: sx0, y: sy0, w: 0, h: 0 })
        return
      }
    }
    // Plan fixe: ne pas déplacer le fond
  }

  function snap(v: number) {
    const g = room.grid || 50
    return Math.round(v / g) * g
  }

  function onPointerMove(e: React.PointerEvent) {
    const rect = (e.target as HTMLCanvasElement).getBoundingClientRect()
    const sx = e.clientX - rect.left
    const sy = e.clientY - rect.top
    const { x, y } = screenToWorld(sx, sy)
    if (fixtureResize && editable) {
      const idx = (fixtures as any[]).findIndex(f => f.id === fixtureResize.id)
      if (idx >= 0) {
        const fx: any = (fixtures as any[])[idx]
        if (fixtureResize.shape === 'round') {
          const dx = x - fx.x
          const dy = y - fx.y
          let nr = Math.max(5, Math.sqrt(dx * dx + dy * dy))
          if (showGrid && room.grid && room.grid > 0) nr = snap(nr)
          fx.r = nr
        } else {
          let nw = fx.w
          let nh = fx.h
          if (fixtureResize.handle === 'right' || fixtureResize.handle === 'corner') nw = Math.max(10, x - fx.x)
          if (fixtureResize.handle === 'bottom' || fixtureResize.handle === 'corner') nh = Math.max(10, y - fx.y)
          if (showGrid && room.grid && room.grid > 0) {
            nw = snap(nw); nh = snap(nh)
          }
          fx.w = nw; fx.h = nh
        }
        onChange && onChange({ ...data, fixtures: [...(fixtures as any[])] })
      }
      return
    }
    if (fixtureDraggingId) {
      const fx: any = (fixtures as any[]).find(f => f.id === fixtureDraggingId)
      if (fx) {
        const nx = x - dragDelta.current.x
        const ny = y - dragDelta.current.y
        const snapGrid = showGrid && room.grid && room.grid > 0
        fx.x = snapGrid ? snap(nx) : nx
        fx.y = snapGrid ? snap(ny) : ny
        onChange && onChange({ ...data, fixtures: [...(fixtures as any[])] })
      }
      return
    }
    if (noGoResize && editable) {
      const idx = noGo.findIndex(r => r.id === noGoResize.id)
      if (idx >= 0) {
        const r = { ...noGo[idx] }
        let nw = r.w
        let nh = r.h
        if (noGoResize.handle === 'right' || noGoResize.handle === 'corner') nw = Math.max(10, x - r.x)
        if (noGoResize.handle === 'bottom' || noGoResize.handle === 'corner') nh = Math.max(10, y - r.y)
        if (showGrid && room.grid && room.grid > 0) { nw = snap(nw); nh = snap(nh) }
        const next = [...noGo]
        next[idx] = { ...r, w: nw, h: nh }
        onChange && onChange({ ...data, no_go: next })
      }
      return
    }
    if (noGoDraggingId) {
      const idx = noGo.findIndex(r => r.id === noGoDraggingId)
      if (idx >= 0) {
        const r = { ...noGo[idx] }
        const nx = x - dragDelta.current.x
        const ny = y - dragDelta.current.y
        const snapGrid = showGrid && room.grid && room.grid > 0
        const next = [...noGo]
        next[idx] = { ...r, x: snapGrid ? snap(nx) : nx, y: snapGrid ? snap(ny) : ny }
        onChange && onChange({ ...data, no_go: next })
      }
      return
    }
    if (resizeHandle !== 'none' && editable) {
      let nw = room.width
      let nh = room.height
      if (resizeHandle === 'right' || resizeHandle === 'corner') nw = Math.max(100, x)
      if (resizeHandle === 'bottom' || resizeHandle === 'corner') nh = Math.max(100, y)
      const snapGrid = showGrid && room.grid && room.grid > 0
      if (snapGrid) {
        nw = snap(nw)
        nh = snap(nh)
      }
      onChange && onChange({ ...data, room: { ...(room as any), width: nw, height: nh } })
      return
    }
    if (drawStartNoGo.current && editable && drawNoGoMode) {
      const p0 = drawStartNoGo.current
      let x0 = p0.x, y0 = p0.y
      let x1 = x, y1 = y
      if (showGrid && room.grid && room.grid > 0) { x1 = snap(x1); y1 = snap(y1) }
      const left = Math.min(x0, x1)
      const top = Math.min(y0, y1)
      const w = Math.abs(x1 - x0)
      const h = Math.abs(y1 - y0)
      setDraftNoGo({ id: 'draft', x: left, y: top, w, h })
      return
    }
    if (draggingId) {
      const t = tables.find(t => t.id === draggingId)
      if (!t) return
      const nx = x - dragDelta.current.x
      const ny = y - dragDelta.current.y
      const snapGrid = showGrid && room.grid && room.grid > 0
      if (t.r) {
        t.x = snapGrid ? snap(nx) : nx
        t.y = snapGrid ? snap(ny) : ny
      } else {
        t.x = snapGrid ? snap(nx) : nx
        t.y = snapGrid ? snap(ny) : ny
      }
      const invalidNow = tableCollides(t)
      dragInvalid.current = invalidNow
      if (!invalidNow) {
        lastValid.current = { x: t.x, y: t.y }
      }
      onChange && onChange({ ...data, tables: [...tables] })
      return
    }
    const fr = fixtureHandleAt(sx, sy)
    const ngr = noGoHandleAt(sx, sy)
    const h = handleAt(sx, sy)
    const el = canvasRef.current
    if (el) {
      if (fr) {
        el.style.cursor = fr.handle === 'corner' ? 'nwse-resize' : fr.handle === 'right' ? 'ew-resize' : fr.handle === 'bottom' ? 'ns-resize' : 'ew-resize'
      } else if (ngr) {
        el.style.cursor = ngr.handle === 'corner' ? 'nwse-resize' : ngr.handle === 'right' ? 'ew-resize' : 'ns-resize'
      } else if (drawNoGoMode) {
        el.style.cursor = 'crosshair'
      } else {
        el.style.cursor = h === 'corner' ? 'nwse-resize' : h === 'right' ? 'ew-resize' : h === 'bottom' ? 'ns-resize' : 'default'
      }
    }
  }

  function onPointerUp() {
    const currentDraggingId = draggingId
    if (drawStartNoGo.current && draftNoGo && editable && drawNoGoMode) {
      const minSize = 10
      if (draftNoGo.w >= minSize && draftNoGo.h >= minSize) {
        const id = `ng_${Date.now()}_${Math.random().toString(36).slice(2,7)}`
        const next = [...noGo, { id, x: draftNoGo.x, y: draftNoGo.y, w: draftNoGo.w, h: draftNoGo.h }]
        onChange && onChange({ ...data, no_go: next })
      }
      drawStartNoGo.current = null
      setDraftNoGo(null)
    }
    // Revert invalid drop before clearing ids/state
    if (dragStart.current && lastValid.current && dragInvalid.current && editable && currentDraggingId) {
      const t = tables.find(tt => tt.id === currentDraggingId)
      if (t) {
        t.x = lastValid.current.x
        t.y = lastValid.current.y
        onChange && onChange({ ...data, tables: [...tables] })
      }
    }
    setDraggingId(null)
    setIsPanning(false)
    setResizeHandle('none')
    setFixtureDraggingId(null)
    setFixtureResize(null)
    dragStart.current = null
    lastValid.current = null
    dragInvalid.current = false
    setNoGoDraggingId(null)
    setNoGoResize(null)
    const el = canvasRef.current
    if (el) el.style.cursor = 'default'
  }

  function onDoubleClick(e: React.MouseEvent) {
    const rect = (e.target as HTMLCanvasElement).getBoundingClientRect()
    const sx = e.clientX - rect.left
    const sy = e.clientY - rect.top
    const { x, y } = screenToWorld(sx, sy)
    const tHit = [...tables].reverse().find(t => tableHit(x, y, t))
    if (tHit && tHit.kind === 'fixed') {
      tHit.locked = !tHit.locked
      onChange && onChange({ ...data, tables: [...tables] })
      return
    }
    const fHit = [...fixtures].reverse().find(f => ('r' in (f as any))
      ? circleHit(x, y, { id: (f as any).id, x: (f as any).x, y: (f as any).y, r: (f as any).r })
      : rectHit(x, y, { id: (f as any).id, x: (f as any).x, y: (f as any).y, w: (f as any).w, h: (f as any).h })
    ) as any
    if (fHit) {
      if (e.altKey || e.shiftKey) {
        const name = window.prompt('Nom de l\'objet', fHit.label || '')
        if (name !== null) {
          fHit.label = name
          onChange && onChange({ ...data, fixtures: [...fixtures] })
        }
      } else {
        fHit.locked = !fHit.locked
        onChange && onChange({ ...data, fixtures: [...fixtures] })
      }
    }
  }

  function onWheel(e: React.WheelEvent) {
    e.preventDefault()
    const delta = -e.deltaY
    const factor = delta > 0 ? 1.1 : 0.9
    const newScale = Math.min(4, Math.max(0.25, scale * factor))
    const rect = (e.target as HTMLCanvasElement).getBoundingClientRect()
    const sx = e.clientX - rect.left
    const sy = e.clientY - rect.top
    const wx1 = (sx - offset.x) / scale
    const wy1 = (sy - offset.y) / scale
    const wx2 = (sx - offset.x) / newScale
    const wy2 = (sy - offset.y) / newScale
    setOffset({ x: offset.x + (wx2 - wx1) * newScale, y: offset.y + (wy2 - wy1) * newScale })
    setScale(newScale)
  }

  return (
    <div className={className} style={{ position: 'relative', width: '100%', height: '100%' }}>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '100%', touchAction: 'none', background: '#fafafa' }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
        onWheel={onWheel}
        onDoubleClick={onDoubleClick}
      />
    </div>
  )
}
