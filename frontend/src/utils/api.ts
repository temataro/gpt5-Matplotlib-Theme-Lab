import ky from 'ky'

export async function generateThemes(payload: FormData) {
  return ky.post('/api/themes/generate', { body: payload }).json<any>()
}

export async function renderTheme(theme: any) {
  const fd = new FormData()
  fd.set('theme_json', JSON.stringify(theme))
  return ky.post('/api/render', { body: fd }).json<any>()
}

export async function downloadAll(theme: any) {
  const fd = new FormData()
  fd.set('theme_json', JSON.stringify(theme))
  const blob = await ky.post('/api/download', { body: fd }).blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${theme.slug || 'theme'}_bundle.zip`
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 5000)
}

