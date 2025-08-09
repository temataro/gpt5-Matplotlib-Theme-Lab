import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#FAFAF7',
        fg: '#111111',
        accent: '#2E7FE8'
      },
      borderRadius: {
        xl2: '1rem'
      }
    },
  },
  plugins: [],
} satisfies Config


