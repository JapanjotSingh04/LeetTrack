/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        base: {
          DEFAULT: '#0B0E14',
          raised: '#10141C',
          card: '#141924',
          border: '#232A38',
          borderMuted: '#1A2029',
        },
        ink: {
          DEFAULT: '#E7EAF2',
          muted: '#8B93A7',
          faint: '#5B6478',
        },
        accent: {
          DEFAULT: '#5B8DEF',
          hover: '#7BA1F2',
          muted: '#2B3B5E',
        },
        easy: { DEFAULT: '#3FB950', bg: '#132A19' },
        medium: { DEFAULT: '#E3A008', bg: '#2B2109' },
        hard: { DEFAULT: '#F85149', bg: '#2B1414' },
      },
      fontFamily: {
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        card: '10px',
      },
      boxShadow: {
        card: '0 1px 0 rgba(255,255,255,0.02) inset, 0 8px 24px -12px rgba(0,0,0,0.45)',
      },
    },
  },
  plugins: [],
}
