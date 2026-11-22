/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"], mono: ["JetBrains Mono", "ui-monospace", "Consolas", "monospace"] },
      colors: {
        brand: { 50: "#eef2ff", 100: "#e0e7ff", 400: "#818cf8", 500: "#6366f1", 600: "#4f46e5", 700: "#4338ca" },
      },
      keyframes: { pop: { "0%": { opacity: 0, transform: "translateY(4px)" }, "100%": { opacity: 1, transform: "none" } } },
      animation: { pop: "pop .18s ease-out" },
    },
  },
  plugins: [],
};
