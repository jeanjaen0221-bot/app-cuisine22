// Temporary debug trace utility. Enable with localStorage.setItem('debugFloor', '1')
const enabled = () => {
  try {
    return typeof window !== 'undefined' && (window as any).DEBUG_FLOOR === true || localStorage.getItem('debugFloor') === '1'
  } catch {
    return false
  }
}

export function dlog(tag: string, msg: string, extra?: any) {
  if (!enabled()) return
  const ts = new Date().toISOString().split('T')[1].replace('Z', '')
  if (extra !== undefined) {
    // eslint-disable-next-line no-console
    console.log(`[FLOOR ${ts}] ${tag}: ${msg}`, extra)
  } else {
    // eslint-disable-next-line no-console
    console.log(`[FLOOR ${ts}] ${tag}: ${msg}`)
  }
}

export function dtime<T>(tag: string, label: string, fn: () => T): T {
  const start = performance.now()
  try {
    return fn()
  } finally {
    const dur = Math.round(performance.now() - start)
    dlog(tag, `${label} took ${dur}ms`)
  }
}

export function setDebugFloor(on: boolean) {
  try {
    if (on) localStorage.setItem('debugFloor', '1')
    else localStorage.removeItem('debugFloor')
  } catch {}
  ;(window as any).DEBUG_FLOOR = on
}
