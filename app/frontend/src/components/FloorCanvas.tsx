import { useEffect, useMemo, useRef, useState } from 'react'
import type { AssignmentMap, FloorCircle, FloorPlanData, FloorRect, FloorTable } from '../types'

type Props = {
  data: FloorPlanData
  assignments?: AssignmentMap
  editable?: boolean
  showGrid?: boolean
  onChange?: (data: FloorPlanData) => void
  className?: string
}

export default function FloorCanvas({ data, assignments, editable = true, showGrid = true, onChange, className }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [size, setSize] = useState({ w: 0, h: 0 })
  const [scale, setScale] = useState(1)
  const [offset, setOffset] = useState({ x: 50, y: 50 })
  const [draggingId, setDraggingId] = useState<string | null>(null)
  const [isPanning, setIsPanning] = useState(false)
  const dragDelta = useRef({ x: 0, y: 0 })

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
      for (const r of noGo) if (intersectsCircleRect(c, r)) return true
      for (const r of walls) if (intersectsCircleRect(c, r)) return true
      for (const f of fixtures) {
        if ('r' in (f as any)) { if (intersectsCircleCircle(c, f as any)) return true }
        else { if (intersectsCircleRect(c, f as any)) return true }
      }
      return false
    } else {
      const w = t.w || 120
      const h = t.h || 60
      const rr: FloorRect = { id: t.id, x: t.x, y: t.y, w, h }
      for (const r of noGo) if (intersectsRectRect(rr, r)) return true
      for (const r of walls) if (intersectsRectRect(rr, r)) return true
      for (const f of fixtures) {
        if ('r' in (f as any)) { if (intersectsCircleRect(f as any, rr)) return true }
        else { if (intersectsRectRect(rr, f as any)) return true }
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

    ctx.fillStyle = '#999'
    for (const w of walls) ctx.fillRect(w.x, w.y, w.w, w.h)

    ctx.fillStyle = '#666'
    for (const c of cols) { ctx.beginPath(); ctx.arc(c.x, c.y, c.r, 0, Math.PI * 2); ctx.fill() }

    ctx.fillStyle = '#bbb'
    for (const r of noGo) ctx.fillRect(r.x, r.y, r.w, r.h)

    for (const fx of fixtures) {
      ctx.fillStyle = '#8b8'
      if ('r' in fx) { ctx.beginPath(); ctx.arc((fx as any).x, (fx as any).y, (fx as any).r, 0, Math.PI * 2); ctx.fill() }
      else ctx.fillRect((fx as any).x, (fx as any).y, (fx as any).w, (fx as any).h)
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
      const cap = (t.capacity || (t.kind === 'rect' ? 6 : t.kind === 'round' ? 10 : 2)) + ''
      ctx.fillStyle = '#fff'
      ctx.font = `${14/scale}px sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      const cx = t.r ? t.x : t.x + (t.w || 120) / 2
      const cy = t.r ? t.y : t.y + (t.h || 60) / 2
      ctx.fillText(cap, cx, cy)
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
  useEffect(() => { draw() }, [size, scale, offset, data, assignments, showGrid])

  function onPointerDown(e: React.PointerEvent) {
    const rect = (e.target as HTMLCanvasElement).getBoundingClientRect()
    const sx = e.clientX - rect.left
    const sy = e.clientY - rect.top
    const { x, y } = screenToWorld(sx, sy)
    const hit = [...tables].reverse().find(t => tableHit(x, y, t))
    if (hit && editable && !hit.locked) {
      setDraggingId(hit.id)
      dragDelta.current = { x: x - hit.x, y: y - hit.y }
    } else {
      setIsPanning(true)
      dragDelta.current = { x: sx - offset.x, y: sy - offset.y }
    }
  }

  function snap(v: number) {
    const g = room.grid || 50
    return Math.round(v / g) * g
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!draggingId && !isPanning) return
    const rect = (e.target as HTMLCanvasElement).getBoundingClientRect()
    const sx = e.clientX - rect.left
    const sy = e.clientY - rect.top
    if (isPanning) {
      setOffset({ x: sx - dragDelta.current.x, y: sy - dragDelta.current.y })
      return
    }
    const { x, y } = screenToWorld(sx, sy)
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
    onChange && onChange({ ...data, tables: [...tables] })
  }

  function onPointerUp() {
    setDraggingId(null)
    setIsPanning(false)
  }

  function onDoubleClick(e: React.MouseEvent) {
    const rect = (e.target as HTMLCanvasElement).getBoundingClientRect()
    const sx = e.clientX - rect.left
    const sy = e.clientY - rect.top
    const { x, y } = screenToWorld(sx, sy)
    const hit = [...tables].reverse().find(t => tableHit(x, y, t))
    if (!hit) return
    // Toggle lock state on fixed tables: double-click to unlock/lock
    if (hit.kind === 'fixed') {
      hit.locked = !hit.locked
      onChange && onChange({ ...data, tables: [...tables] })
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
