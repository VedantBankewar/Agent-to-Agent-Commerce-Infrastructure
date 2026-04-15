/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "on-primary-container": "#f48fff",
        "secondary-container": "#feb300",
        "error": "#ffb4ab",
        "surface-container": "#201f1f",
        "surface-container-highest": "#36343b",
        "on-secondary-container": "#6a4800",
        "surface-container-low": "#1c1b1b",
        "secondary-fixed-dim": "#ffba38",
        "surface-container-lowest": "#0e0e0e",
        "tertiary": "#c8c8b0",
        "on-tertiary-fixed": "#1b1d0e",
        "on-primary-fixed": "#35003f",
        "primary": "#f9abff",
        "on-error-container": "#ffdad6",
        "error-container": "#93000a",
        "surface-dim": "#131313",
        "on-background": "#e5e2e1",
        "on-error": "#690005",
        "surface-container-high": "#2a2a2a",
        "tertiary-fixed-dim": "#c8c8b0",
        "surface-bright": "#393939",
        "outline": "#998d9d",
        "secondary-fixed": "#ffdeac",
        "on-secondary": "#432c00",
        "primary-container": "#7b008f",
        "on-surface-variant": "#d0c2d3",
        "on-primary-fixed-variant": "#7b008f",
        "on-tertiary-container": "#b6b69f",
        "tertiary-fixed": "#e4e4cc",
        "on-tertiary": "#303221",
        "surface-tint": "#f9abff",
        "inverse-on-surface": "#313030",
        "background": "#131313",
        "on-primary": "#570066",
        "primary-fixed": "#ffd6fe",
        "on-tertiary-fixed-variant": "#474836",
        "tertiary-container": "#464836",
        "secondary": "#ffd799",
        "surface": "#131313",
        "surface-variant": "#353534",
        "on-surface": "#e5e2e1",
        "inverse-surface": "#e5e2e1",
        "on-secondary-fixed-variant": "#604100",
        "primary-fixed-dim": "#f9abff",
        "outline-variant": "#4d4351",
        "inverse-primary": "#9a25ae",
        "on-secondary-fixed": "#281900"
      },
      borderRadius: {
        "DEFAULT": "0.125rem",
        "lg": "0.25rem",
        "xl": "0.5rem",
        "full": "0.75rem"
      },
      fontFamily: {
        "headline": ["Plus Jakarta Sans", "sans-serif"],
        "body": ["Manrope", "sans-serif"],
        "label": ["Manrope", "sans-serif"]
      }
    }
  },
  plugins: [],
}
