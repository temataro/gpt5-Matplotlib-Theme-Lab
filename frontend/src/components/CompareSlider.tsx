import React, { useRef, useEffect } from 'react'

export function CompareSlider({ left, right }: { left?: string; right?: string }) {
  const container = useRef<HTMLDivElement>(null)
  const slider = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = container.current!
    const s = slider.current!
    let down = false
    function setX(e: MouseEvent) {
      const rect = el.getBoundingClientRect()
      const x = Math.min(Math.max(e.clientX - rect.left, 0), rect.width)
      s.style.left = `${x}px`
      el.style.setProperty('--clip', `${x}px`)
    }
    function mdown(e: MouseEvent){ down = true; setX(e) }
    function mmove(e: MouseEvent){ if(down) setX(e) }
    function mup(){ down = false }
    el.addEventListener('mousedown', mdown)
    window.addEventListener('mousemove', mmove)
    window.addEventListener('mouseup', mup)
    return () => { el.removeEventListener('mousedown', mdown); window.removeEventListener('mousemove', mmove); window.removeEventListener('mouseup', mup) }
  }, [])

  return (
    <div ref={container} className="relative w-full h-[280px] rounded-2xl overflow-hidden border border-black/10" style={{ background: '#fff' }}>
      {left && <img src={left} className="absolute inset-0 w-full h-full object-contain" />}
      {right && <img src={right} className="absolute inset-0 w-full h-full object-contain" style={{ clipPath: 'inset(0 0 0 var(--clip, 50%))' }} />}
      <div ref={slider} className="absolute top-0 bottom-0 w-[2px] bg-black/60" style={{ left: '50%' }}></div>
    </div>
  )
}


