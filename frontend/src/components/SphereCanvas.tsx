import { useEffect, useRef } from 'react'

type N = { id: string; type: string; degree: number; fx: number; fy: number; fz: number }
type L = { id: string; source: any; target: any; relation: string }
const sid = (x: any) => (typeof x === 'object' ? x.id : x)

/** Software-rendered rotating sphere (2D canvas, orthographic-with-perspective projection).
 *  Used when the browser cannot create a WebGL context. Click nodes/edges to toggle, drag to rotate. */
export default function SphereCanvas({ nodes, links, colors, exN, exE, dark, onNode, onLink }: {
  nodes: N[]; links: L[]; colors: Record<string, string>; exN: Set<string>; exE: Set<string>; dark: boolean
  onNode: (n: N) => void; onLink: (l: L) => void
}) {
  const wrap = useRef<HTMLDivElement>(null)
  const cv = useRef<HTMLCanvasElement>(null)
  const st = useRef({ yaw: 0, pitch: -0.35, drag: false, moved: false, lx: 0, ly: 0, auto: true })
  const proj = useRef<{ n: N; x: number; y: number; z: number; r: number }[]>([])
  const props = useRef({ nodes, links, colors, exN, exE, dark }); props.current = { nodes, links, colors, exN, exE, dark }

  useEffect(() => {
    const c = cv.current!, el = wrap.current!, ctx = c.getContext('2d')!
    let raf = 0
    const fit = () => { const d = devicePixelRatio || 1; c.width = el.clientWidth * d; c.height = el.clientHeight * d; c.style.width = el.clientWidth + 'px'; c.style.height = el.clientHeight + 'px'; ctx.setTransform(d, 0, 0, d, 0, 0) }
    fit(); const ro = new ResizeObserver(fit); ro.observe(el)

    const draw = () => {
      const { nodes, links, colors, exN, exE, dark } = props.current, s = st.current
      if (s.auto && !s.drag) s.yaw += 0.004
      const W = el.clientWidth, H = el.clientHeight, cx = W / 2, cy = H / 2, R = 150, sc = Math.min(W, H) / 400
      ctx.clearRect(0, 0, W, H)
      const cy_ = Math.cos(s.yaw), sy = Math.sin(s.yaw), cp = Math.cos(s.pitch), sp = Math.sin(s.pitch)
      const pts = new Map<string, { n: N; x: number; y: number; z: number; r: number }>()
      for (const n of nodes) {
        let x = n.fx * cy_ + n.fz * sy, z = -n.fx * sy + n.fz * cy_, y = n.fy
        const y2 = y * cp - z * sp, z2 = y * sp + z * cp
        const f = 700 / (700 - z2)
        pts.set(n.id, { n, x: cx + x * f * sc, y: cy + y2 * f * sc, z: z2, r: (3 + Math.min(n.degree, 6) * 0.7) * f * sc })
      }
      // sphere silhouette
      ctx.strokeStyle = dark ? 'rgba(255,255,255,.07)' : 'rgba(0,0,0,.08)'; ctx.lineWidth = 1
      ctx.beginPath(); ctx.arc(cx, cy, R * sc * 1.02, 0, 7); ctx.stroke()
      // links
      for (const l of links) {
        const a = pts.get(sid(l.source)), b = pts.get(sid(l.target)); if (!a || !b) continue
        const off = exE.has(l.id), depth = (a.z + b.z) / 2 / R
        ctx.strokeStyle = off ? (dark ? 'rgba(255,255,255,.05)' : 'rgba(0,0,0,.06)') : (dark ? `rgba(160,160,175,${0.18 + 0.22 * (depth + 1) / 2})` : `rgba(90,90,100,${0.2 + 0.25 * (depth + 1) / 2})`)
        ctx.lineWidth = off ? 0.6 : 1; ctx.setLineDash(off ? [3, 4] : [])
        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, k = 0.18
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.quadraticCurveTo(mx + (cx - mx) * k, my + (cy - my) * k, b.x, b.y); ctx.stroke()
      }
      ctx.setLineDash([])
      // nodes back-to-front
      const order = [...pts.values()].sort((p, q) => p.z - q.z); proj.current = order
      for (const p of order) {
        const off = exN.has(p.n.id), a = 0.35 + 0.65 * ((p.z / R + 1) / 2)
        ctx.globalAlpha = off ? 0.35 : a
        ctx.fillStyle = off ? (dark ? '#3a3a40' : '#cfcfd4') : colors[p.n.type] ?? '#9ca3af'
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 7); ctx.fill()
        if (p.z > -R * 0.35) {
          ctx.fillStyle = off ? (dark ? '#55555c' : '#b5b5bb') : (dark ? '#ededee' : '#111'); ctx.font = `${Math.max(9, 10.5 * (0.7 + 0.3 * a))}px Inter, sans-serif`; ctx.textAlign = 'center'
          ctx.fillText(p.n.id.length > 24 ? p.n.id.slice(0, 22) + '…' : p.n.id, p.x, p.y - p.r - 4)
        }
      }
      ctx.globalAlpha = 1
      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)
    return () => { cancelAnimationFrame(raf); ro.disconnect() }
  }, [])

  const pos = (e: React.PointerEvent | React.MouseEvent) => { const r = cv.current!.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top } }
  const down = (e: React.PointerEvent) => { const s = st.current; s.drag = true; s.moved = false; s.lx = e.clientX; s.ly = e.clientY; s.auto = false; cv.current!.setPointerCapture(e.pointerId) }
  const move = (e: React.PointerEvent) => {
    const s = st.current; if (!s.drag) return
    const dx = e.clientX - s.lx, dy = e.clientY - s.ly; if (Math.abs(dx) + Math.abs(dy) > 2) s.moved = true
    s.yaw += dx * 0.008; s.pitch = Math.max(-1.3, Math.min(1.3, s.pitch + dy * 0.008)); s.lx = e.clientX; s.ly = e.clientY
  }
  const up = (e: React.PointerEvent) => {
    const s = st.current; s.drag = false; if (s.moved) return
    const { x, y } = pos(e)
    for (const p of [...proj.current].reverse()) if (Math.hypot(p.x - x, p.y - y) <= p.r + 5) return onNode(p.n)
    const m = new Map(proj.current.map(p => [p.n.id, p]))
    let best: L | null = null, bd = 6
    for (const l of props.current.links) {
      const a = m.get(sid(l.source)), b = m.get(sid(l.target)); if (!a || !b) continue
      const dx = b.x - a.x, dy = b.y - a.y, t = Math.max(0, Math.min(1, ((x - a.x) * dx + (y - a.y) * dy) / (dx * dx + dy * dy || 1)))
      const d = Math.hypot(a.x + t * dx - x, a.y + t * dy - y); if (d < bd) { bd = d; best = l }
    }
    if (best) onLink(best)
  }
  return <div ref={wrap} className="absolute inset-0"><canvas ref={cv} onPointerDown={down} onPointerMove={move} onPointerUp={up} className="cursor-grab active:cursor-grabbing touch-none" /></div>
}
