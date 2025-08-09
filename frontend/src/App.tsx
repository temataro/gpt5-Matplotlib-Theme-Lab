import React, { useEffect, useState } from 'react'
import { generateThemes, renderTheme, downloadAll } from './utils/api'
import { ThemeCarousel } from './components/ThemeCarousel'
import { RcEditor } from './components/RcEditor'
import { PaletteEditor } from './components/PaletteEditor'
import { CompareSlider } from './components/CompareSlider'

type Img = { filename: string; b64png: string }

export default function App() {
  const [themes, setThemes] = useState<any[]>([])
  const [active, setActive] = useState(0)
  const [rcText, setRcText] = useState<string>('{}')
  const [images, setImages] = useState<Img[]>([])
  const [selected, setSelected] = useState<Img | null>(null)
  const [loading, setLoading] = useState(false)

  const theme = themes[active]

  useEffect(() => { (async () => {
    const fd = new FormData()
    fd.set('fg', '#111111')
    fd.set('bg', '#FAFAF7')
    fd.set('accent', '#2E7FE8')
    fd.set('dpi', '180')
    const out = await generateThemes(fd)
    setThemes(out)
    setRcText(JSON.stringify(out[0].rc_global, null, 2))
  })() }, [])

  async function doRender(idx = active) {
    if (!themes[idx]) return
    setLoading(true)
    try {
      const t = { ...themes[idx], rc_global: JSON.parse(rcText) }
      const res = await renderTheme(t)
      setImages(res.images)
      setSelected(res.images[0] ?? null) // promote first image to Large Preview
    } finally { setLoading(false) }
  }

  function applyPalette(pal: string[]) {
    if (!theme) return
    const rc = JSON.parse(rcText)
    rc['axes.prop_cycle'] = { key: 'color', values: pal }
    setRcText(JSON.stringify(rc, null, 2))
  }

  return (
    <div className="max-w-[1200px] mx-auto p-4 space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Matplotlib Theme Lab</h1>
        <div className="flex gap-2">
          <button className="btn" onClick={() => doRender()} disabled={loading}>{loading ? 'Rendering…' : 'Render Active'}</button>
          <button className="btn" onClick={() => theme && downloadAll({ ...theme, rc_global: JSON.parse(rcText) })}>Download all</button>
        </div>
      </header>

      <ThemeCarousel
        themes={themes}
        active={active}
        onSelect={(i) => { setActive(i); setRcText(JSON.stringify(themes[i].rc_global, null, 2)); setImages([]); setSelected(null) }}
      />

      {/* FULL-WIDTH LARGE PREVIEW */}
      <section className="card p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="font-semibold">Large Preview</div>
          <div className="text-xs opacity-70">{selected?.filename ?? '—'}</div>
        </div>
        {selected ? (
          <div className="w-full h-[65vh] bg-white/70 border border-black/10 rounded-xl overflow-hidden flex items-center justify-center">
            <img
              src={`data:image/png;base64,${selected.b64png}`}
              className="max-h-full max-w-full object-contain"
              alt={selected.filename}
            />
          </div>
        ) : (
          <div className="text-sm opacity-70 py-8">No image selected. Render and click a thumbnail below.</div>
        )}
      </section>

      {/* CONTROLS + THUMBNAILS BELOW */}
      {theme && (
        <div className="grid lg:grid-cols-2 gap-4">
          {/* Left: controls */}
          <div className="space-y-3">
            <div className="card p-3">
              <div className="font-semibold mb-2">Theme details</div>
              <div className="text-sm opacity-80">Name: {theme.name} • Mode: {theme.mode}</div>
              <div className="flex items-center gap-2 mt-2">
                <span className="badge">FG {theme.fg}</span>
                <span className="badge">BG {theme.bg}</span>
                <span className="badge">Accent {theme.accent}</span>
              </div>
            </div>

            <PaletteEditor palette={theme.palette} onChange={applyPalette} />

            <div className="space-y-2">
              <div className="font-semibold">rcParams diff (editable)</div>
              <RcEditor value={rcText} onChange={setRcText} />
            </div>
          </div>

          {/* Right: thumbnails + compare */}
          <div className="space-y-3">
            {/* Thumbnails grid */}
            <div className="card p-3">
              <div className="flex items-center justify-between">
                <div className="font-semibold">Thumbnails</div>
                <button className="btn" onClick={() => doRender()} disabled={loading}>Re-render</button>
              </div>
              {images.length === 0 && (
                <div className="text-sm opacity-70 py-8">
                  No images yet. Click <b>Render Active</b> to generate the 10 demo figures.
                </div>
              )}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-3">
                {images.map((im) => (
                  <button
                    key={im.filename}
                    onClick={() => setSelected(im)}
                    className="text-left border border-black/10 rounded-xl overflow-hidden hover:ring-2 hover:ring-accent/70 transition"
                    title="Click to view larger"
                  >
                    <img src={`data:image/png;base64,${im.b64png}`} className="w-full h-[140px] object-contain bg-white" />
                    <div className="p-2 text-xs opacity-70 truncate">{im.filename}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="card p-3">
              <div className="font-semibold mb-2">Compare any two (drag)</div>
              <CompareSlider
                left={images[0] && `data:image/png;base64,${images[0].b64png}`}
                right={images[1] && `data:image/png;base64,${images[1].b64png}`}
              />
            </div>
          </div>
        </div>
      )}

      <footer className="text-xs opacity-60 pt-4">
        Matplotlib 3.9 • mathtext STIX • 180 DPI • Minimal spines • Full-width Large Preview
      </footer>
    </div>
  )
}
