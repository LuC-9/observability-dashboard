/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg:     "#ffffff",
        panel:  "#f9fafb",
        grid:   "#e5e7eb",
        text:   "#111827",
        muted:  "#6b7280",
        blue:   "#3b82f6",
        green:  "#10b981",
        amber:  "#f59e0b",
        red:    "#ef4444",
        violet: "#8b5cf6",
      },
      maxWidth: {
        container: "1400px",
      },
    },
  },
  plugins: [],
};
