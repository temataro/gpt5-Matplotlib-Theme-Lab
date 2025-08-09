import React from 'react'
import Editor from '@monaco-editor/react'

export function RcEditor({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="card p-2">
      <Editor
        height="260px"
        defaultLanguage="json"
        value={value}
        onChange={(v) => onChange(v || '{}')}
        options={{ fontSize: 12, minimap: { enabled: false }, lineNumbers: 'on', scrollBeyondLastLine: false }}
      />
    </div>
  )
}

