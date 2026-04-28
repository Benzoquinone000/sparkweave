/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#F7FAFC",
        ink: "#111827",
        line: "#DDE5E8",
        brand: {
          teal: "#0F766E",
          blue: "#2563EB",
          red: "#E60012",
        },
      },
      boxShadow: {
        panel: "0 14px 34px rgba(17, 24, 39, 0.08)",
        soft: "0 8px 22px rgba(17, 24, 39, 0.06)",
      },
    },
  },
  plugins: [],
};
