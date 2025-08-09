import React from 'react'
import clsx from 'clsx'

export function ThemeCarousel({ themes, active, onSelect }: { themes: any[]; active: number; onSelect: (idx: number) => void }) {
  return (
    <div className="flex gap-3 overflow-x-auto py-2">
      {themes.map((t, i) => (
        <button key={t.slug + i} onClick={() => onSelect(i)} className={clsx('card min-w-[220px] p-3 text-left', active === i && 'ring-2 ring-accent')}>
          <div className="flex items-center justify-between mb-2">
            <div className="font-semibold">{t.name}</div>
            <span className="badge">{t.mode}</span>
          </div>
          <div className="flex -space-x-1 mb-2">
            {t.palette.slice(0, 6).map((c: string, j: number) => (
              <span key={j} className="w-6 h-6 rounded-full border border-black/10" style={{ background: c }} />
            ))}
          </div>
          <div className="text-xs opacity-70">fg {t.fg} • bg {t.bg}</div>
        </button>
      ))}
    </div>
  )
}

