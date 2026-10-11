/** @type {import('tailwindcss').Config} */
const v = (n) => `rgb(var(--${n}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: v("bg"), surface: v("surface"), ink: v("ink"), muted: v("muted"),
        water: v("water"), soil: v("soil"), leaf: v("leaf"), sun: v("sun"), alert: v("alert"),
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      borderRadius: { card: "10px" },
    },
  },
  safelist: ["text-water", "text-alert", "text-ink", "text-leaf", "text-soil", "border-water", "border-leaf", "border-sun", "border-alert", "border-soil", "border-muted", "border-t-soil", "border-t-water"],
  plugins: [],
};
