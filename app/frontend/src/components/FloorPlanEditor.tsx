import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Stage, Layer, Group, Rect, Circle, Line, Text, Transformer } from 'react-konva'
import type { FloorPlanLayout, FloorPlanFixedTable, FloorPlanObstacle, FloorPlanZone, FloorPlanServiceElement } from '../types'

export type FloorPlanEditorProps = {
  layout: FloorPlanLayout
  width: number
  height: number
  scale: number
  onLayoutChange: (next: FloorPlanLayout) => void
}

type Sel = { type: 'table'; id: string; index: number } | { type: 'obstacle'; id: string; index: number } | { type: 'zone'; id: string; index: number } | { type: 'service'; id: string; index: number } | null

const GRID = 40
function snap(v: number) { return Math.round(v / GRID) * GRID }
function makeId(prefix: string) { return `${prefix}-${Date.now().toString(36)}-${Math.floor(Math.random()*1000)}` }

export default function FloorPlanEditor({ layout, width, height, scale, onLayoutChange }: FloorPlanEditorProps) {
  const stageRef = useRef<any>(null)
  const [selected, setSelected] = useState<Sel>(null)
  const [transformNode, setTransformNode] = useState<any>(null)
  const [isPanning, setIsPanning] = useState<boolean>(false)
  const [stagePos, setStagePos] = useState({ x: 0, y: 0 })

  const tables = layout.fixedTables || []
  const obstacles = layout.obstacles || []
  const zones = layout.zones || []
  const services = layout.serviceElements || []

  // --- API helpers ---
  const updateTable = useCallback((index: number, patch: Partial<FloorPlanFixedTable>) => {
    const next = { ...layout, fixedTables: [...tables] }
    next.fixedTables[index] = { ...next.fixedTables[index], ...patch }
    onLayoutChange(next)
  }, [layout, tables, onLayoutChange])

  const removeTable = useCallback((index: number) => {
    const next = { ...layout, fixedTables: [...tables] }
    next.fixedTables.splice(index, 1)
    onLayoutChange(next)
  }, [layout, tables, onLayoutChange])

  const addTable = useCallback(() => {
    const next = { ...layout, fixedTables: [...tables] }
    const id = makeId('F')
    next.fixedTables.push({ id, x: snap(width/2), y: snap(height/2), seats: 2, rotation: 0, label: '' })
    onLayoutChange(next)
    setSelected({ type: 'table', id, index: next.fixedTables.length - 1 })
  }, [layout, tables, onLayoutChange, width, height])

  const addObstacleRect = useCallback(() => {
    const next = { ...layout, obstacles: [...obstacles] }
    const id = makeId('O')
    next.obstacles!.push({ id, type: 'rect', x: snap(width/2-80), y: snap(height/2-40), width: 160, height: 80 })
    onLayoutChange(next)
    setSelected({ type: 'obstacle', id, index: next.obstacles!.length - 1 })
  }, [layout, obstacles, onLayoutChange, width, height])

  const addObstacleCircle = useCallback(() => {
    const next = { ...layout, obstacles: [...obstacles] }
    const id = makeId('O')
    next.obstacles!.push({ id, type: 'circle', x: snap(width/2), y: snap(height/2), radius: 60 })
    onLayoutChange(next)
    setSelected({ type: 'obstacle', id, index: next.obstacles!.length - 1 })
  }, [layout, obstacles, onLayoutChange, width, height])

  const addZone = useCallback((kind: FloorPlanZone['kind'] = 'reservable') => {
    const next = { ...layout, zones: [...zones] }
    const id = makeId('Z')
    const x = snap(width/2-120), y = snap(height/2-80)
    next.zones!.push({ id, kind: kind, points: [
      { x, y }, { x: x+240, y }, { x: x+240, y: y+160 }, { x, y: y+160 }
    ] })
    onLayoutChange(next)
    setSelected({ type: 'zone', id, index: next.zones!.length - 1 })
  }, [layout, zones, onLayoutChange, width, height])

  const removeSelected = useCallback(() => {
    if (!selected) return
    if (selected.type === 'table') return removeTable(selected.index)
    if (selected.type === 'obstacle') {
      const next = { ...layout, obstacles: [...obstacles] }
      next.obstacles!.splice(selected.index, 1)
      onLayoutChange(next)
      setSelected(null)
      return
    }
    if (selected.type === 'zone') {
      const next = { ...layout, zones: [...zones] }
      next.zones!.splice(selected.index, 1)
      onLayoutChange(next)
      setSelected(null)
      return
    }
  }, [selected, layout, obstacles, zones, onLayoutChange, removeTable])

  const toggleLockSelected = useCallback(() => {
    if (!selected || selected.type !== 'table') return
    const t = tables[selected.index]
    updateTable(selected.index, { locked: !t.locked })
  }, [selected, tables, updateTable])

  const incSeats = useCallback((delta: number) => {
    if (!selected || selected.type !== 'table') return
    const t = tables[selected.index]
    const nextSeats = Math.max(1, Math.min(20, (t.seats || 0) + delta))
    updateTable(selected.index, { seats: nextSeats })
  }, [selected, tables, updateTable])

  // --- Hotkeys ---
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === 'INPUT' || (e.target as HTMLElement)?.tagName === 'TEXTAREA') return
      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault(); removeSelected(); return
      }
      if (selected?.type === 'table' && (e.key.startsWith('Arrow'))) {
        e.preventDefault()
        const step = e.shiftKey ? 10 : GRID
        const idx = selected.index
        const t = tables[idx]
        if (!t) return
        const dx = e.key === 'ArrowRight' ? step : e.key === 'ArrowLeft' ? -step : 0
        const dy = e.key === 'ArrowDown' ? step : e.key === 'ArrowUp' ? -step : 0
        updateTable(idx, { x: snap((t.x || 0) + dx), y: snap((t.y || 0) + dy) })
        return
      }
      if (e.key.toLowerCase() === 't') { e.preventDefault(); addTable(); return }
      if (e.key.toLowerCase() === 'o') { e.preventDefault(); addObstacleRect(); return }
      if (e.key.toLowerCase() === 'c') { e.preventDefault(); addObstacleCircle(); return }
      if (e.key.toLowerCase() === 'z') { e.preventDefault(); addZone('reservable'); return }
      if (e.key.toLowerCase() === 'f') { e.preventDefault(); addZone('forbidden'); return }
      if (e.key.toLowerCase() === 'r') {
        if (selected?.type === 'table') {
          const t = tables[selected.index]
          updateTable(selected.index, { rotation: ((t.rotation || 0) + 15) % 360 })
        }
      }
      if (e.key.toLowerCase() === 'l') {
        e.preventDefault(); toggleLockSelected(); return
      }
      if (e.key.toLowerCase() === 'd') {
        if (selected?.type === 'table') {
          e.preventDefault()
          const t = tables[selected.index]
          const next = { ...layout, fixedTables: [...tables] }
          const id = makeId('F')
          next.fixedTables.splice(selected.index + 1, 0, { ...t, id, x: snap((t.x || 0) + GRID), y: snap((t.y || 0) + GRID) })
          onLayoutChange(next)
          setSelected({ type: 'table', id, index: selected.index + 1 })
          return
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selected, addTable, removeSelected, addObstacleRect, addObstacleCircle, addZone, tables, updateTable, toggleLockSelected])

  // Attach transformer to selected table
  useEffect(() => {
    if (!transformNode) return
    const layer = transformNode.getLayer()
    layer?.batchDraw()
  }, [transformNode, selected])

  // --- Render helpers ---
  const gridLines = useMemo(() => {
    const lines: JSX.Element[] = []
    for (let x = 0; x <= width; x += GRID) {
      lines.push(<Line key={`vx-${x}`} points={[x, 0, x, height]} stroke="#e5e7eb" strokeWidth={1} />)
    }
    for (let y = 0; y <= height; y += GRID) {
      lines.push(<Line key={`hz-${y}`} points={[0, y, width, y]} stroke="#e5e7eb" strokeWidth={1} />)
    }
    return lines
  }, [width, height])

  const onBlankClick = () => setSelected(null)

  const onStageWheel = (e: any) => {
    if (!stageRef.current) return
    e.evt.preventDefault()
    const oldScale = scale
    const pointer = stageRef.current.getPointerPosition()
    const mousePointTo = {
      x: (pointer.x - stageRef.current.x()) / oldScale,
      y: (pointer.y - stageRef.current.y()) / oldScale,
    }
    const direction = e.evt.deltaY > 0 ? -1 : 1
    const scaleBy = 1.04
    const newScale = Math.max(0.25, Math.min(3, direction > 0 ? oldScale * scaleBy : oldScale / scaleBy))
    // We don't control scale here (prop). Let parent handle zoom via its own controls.
    // So only prevent default panning via wheel.
  }

  const onDragMoveSnap = (e: any) => {
    const node = e.target
    node.position({ x: snap(node.x()), y: snap(node.y()) })
  }

  return (
    <div className="border rounded overflow-auto bg-white">
      <Stage
        ref={stageRef}
        width={width * scale}
        height={height * scale}
        scaleX={scale}
        scaleY={scale}
        x={stagePos.x}
        y={stagePos.y}
        draggable={isPanning}
        onWheel={onStageWheel}
        onMouseDown={(e: any) => { if (e.target === e.target.getStage()) onBlankClick() }}
        onDragEnd={(e: any) => setStagePos({ x: e.target.x(), y: e.target.y() })}
        style={{ cursor: isPanning ? 'grab' : 'default' }}
      >
        <Layer listening={false}>
          {/* background */}
          <Rect x={0} y={0} width={width} height={height} fill="#f8fafc" />
          {gridLines}
        </Layer>

        {/* Zones layer */}
        <Layer>
          {(zones || []).map((z, i) => {
            const pts: number[] = []
            for (const p of z.points || []) { pts.push(p.x, p.y) }
            const color = z.kind === 'forbidden' ? 'rgba(239,68,68,0.15)' : z.kind === 'reservable' ? 'rgba(16,185,129,0.12)' : 'rgba(59,130,246,0.10)'
            return (
              <Group key={z.id} onClick={() => setSelected({ type: 'zone', id: z.id, index: i })}>
                <Line points={pts} closed fill={color} stroke="#94a3b8" strokeWidth={1} />
              </Group>
            )
          })}
        </Layer>

        {/* Obstacles layer */}
        <Layer>
          {(obstacles || []).map((o, i) => (
            o.type === 'rect' ? (
              <Rect key={o.id}
                x={o.x || 0} y={o.y || 0}
                width={o.width || 0} height={o.height || 0}
                fill="#cbd5e1"
                draggable
                onDragMove={onDragMoveSnap}
                onDragEnd={(e: any) => {
                  const next = { ...layout, obstacles: [...obstacles] }
                  next.obstacles![i] = { ...o, x: snap(e.target.x()), y: snap(e.target.y()) }
                  onLayoutChange(next)
                }}
                onClick={() => setSelected({ type: 'obstacle', id: o.id, index: i })}
              />
            ) : (
              <Circle key={o.id}
                x={o.x || 0} y={o.y || 0}
                radius={o.radius || 0}
                fill="#cbd5e1"
                draggable
                onDragMove={onDragMoveSnap}
                onDragEnd={(e: any) => {
                  const next = { ...layout, obstacles: [...obstacles] }
                  next.obstacles![i] = { ...o, x: snap(e.target.x()), y: snap(e.target.y()) }
                  onLayoutChange(next)
                }}
                onClick={() => setSelected({ type: 'obstacle', id: o.id, index: i })}
              />
            )
          ))}
        </Layer>

        {/* Tables layer */}
        <Layer>
          {(tables || []).map((t, i) => (
            <Group key={t.id}
              x={t.x} y={t.y}
              draggable={!t.locked}
              onDragMove={onDragMoveSnap}
              onDragEnd={(e: any) => updateTable(i, { x: snap(e.target.x()), y: snap(e.target.y()) })}
              onClick={(e: any) => { setSelected({ type: 'table', id: t.id, index: i }); setTransformNode(e.target.getParent()) }}
              rotation={t.rotation || 0}
            >
              <Rect offsetX={30} offsetY={18} width={60} height={36} fill="#6d28d9" cornerRadius={4} />
              <Text text={(t.label || t.id) + `(${t.seats})`} fill="white" fontSize={12} align="center" offsetX={30} offsetY={8} width={60} height={16} y={-8} />
            </Group>
          ))}
          {selected?.type === 'table' && transformNode && (
            <Transformer
              nodes={[transformNode]}
              rotateEnabled={!tables[(selected as any).index]?.locked}
              enabledAnchors={[]}
              rotationSnaps={[0, 15, 30, 45, 60, 75, 90, 120, 135, 150, 180, 210, 225, 240, 270, 300, 315, 330]}
              boundBoxFunc={(oldBox: any, newBox: any) => newBox}
              onTransformEnd={() => {
                const node = transformNode
                const rot = node.rotation() || 0
                const idx = (selected as any).index
                updateTable(idx, { rotation: Math.round(rot) })
              }}
            />
          )}
        </Layer>
      </Stage>

      <div className="p-2 border-t bg-slate-50 flex flex-wrap items-center gap-2">
        <span className="text-xs text-slate-600">Raccourcis: T=Table, O=Obstacle, C=Colonne, Z=Zone réservable, F=Zone interdite, Flèches=Déplacer (⇧=fin), D=Dupliquer, L=Lock, Del=Supprimer, R=Rotation +15°</span>
        <div className="flex-1" />
        <button className="btn" onClick={addTable}>+ Table fixe</button>
        <button className="btn" onClick={addObstacleRect}>+ Mur/Rect</button>
        <button className="btn" onClick={addObstacleCircle}>+ Colonne</button>
        <button className="btn" onClick={() => addZone('reservable')}>+ Zone réservable</button>
        <button className="btn" onClick={() => addZone('forbidden')}>+ Zone interdite</button>
        {selected?.type === 'table' && <>
          <button className="btn" onClick={() => incSeats(-1)}>−1 place</button>
          <button className="btn" onClick={() => incSeats(+1)}>+1 place</button>
          <button className="btn" onClick={toggleLockSelected}>{tables[selected.index]?.locked ? 'Déverrouiller' : 'Verrouiller'}</button>
        </>}
        <button className="btn" onClick={() => setIsPanning(p => !p)}>{isPanning ? 'Arrêter le déplacement' : 'Déplacer la scène'}</button>
        {selected && <button className="btn" onClick={removeSelected}>Supprimer sélection</button>}
      </div>
    </div>
  )
}
