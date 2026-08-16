import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // The dashboard chrome, drawn from the landing page's palette
        // (src/styles/landing.css) so the app and the marketing page read as
        // one product. `bark` replaces slate and `terra` replaces indigo at
        // the same scale positions, which keeps every existing contrast
        // relationship intact while shifting the hue warm.
        bark: {
          50: '#faf5ef',
          100: '#f7ede2', // --cream
          200: '#ead9c6',
          300: '#d5bfa5',
          400: '#ae9679',
          500: '#8a755a',
          600: '#5f4d38',
          700: '#40342a',
          800: '#261d16',
          900: '#150f0b', // --frame
          950: '#0c0806',
        },
        terra: {
          50: '#fdf3ec',
          100: '#fae0cd',
          200: '#f5c9a8',
          300: '#edaa78',
          400: '#e0894a', // --terra-3
          500: '#c85a2a', // --terra-2, primary action
          600: '#b6481f', // --terra-1
          700: '#93381a',
          800: '#6d2a14',
          900: '#451b0d',
          950: '#260e07',
        },
        honey: {
          300: '#ffd9a0',
          400: '#f2b96f', // --honey
          500: '#edad60',
          600: '#b06c2e', // --honey-deep
        },
        cream: '#f7ede2',
        surface: {
          DEFAULT: '#150f0b',
          raised: '#261d16',
          border: '#40342a',
        },
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 150ms ease-out',
        'slide-up': 'slide-up 200ms ease-out',
      },
    },
  },
  plugins: [],
};

export default config;
