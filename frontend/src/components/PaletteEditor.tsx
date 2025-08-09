import React, { useState } from 'react'

function isHex(v: string) {
  return /^#?[0-9A-Fa-f]{6}$/.test(v)
}

export function PaletteEditor({ palette, onChange }: { palette: string[]; onChange: (p: string[]) => void }) {
  const [vals, setVals] = useState<string[]>(palette)
  function set(i: number, v: string) {
    const next = [...vals]
    next[i] = v.startsWith('#') ? v.toUpperCase() : ('#' + v.toUpperCase())
    setVals(next)
    onChange(next)
  }
  return (
    <div className="card p-3">
      <div className="mb-2 font-semibold">Color cycle (3–10 HEX)</div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        {vals.map((c, i) => (
          <div key={i} className="flex items-center gap-2">
            <input className="input" value={c} onChange={(e) => set(i, e.target.value)} />
            <span className="w-6 h-6 rounded-full border" style={{ background: isHex(c) ? (c.startsWith('#') ? c : '#' + c) : 'transparent' }} />
          </div>
        ))}
      </div>
      <div className="mt-2 flex gap-2">
        <button className="btn" onClick={() => { if (vals.length < 10) { const next = [...vals, '#888888']; setVals(next); onChange(next) } }}>Add</button>
        <button className="btn" onClick={() => { if (vals.length > 3) { const next = vals.slice(0, -1); setVals(next); onChange(next) } }}>Remove</button>
      </div>
    </div>
  )
}
