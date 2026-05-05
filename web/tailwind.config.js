/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#F7F6F3",
        surface: "#FAFAF9",
        ink: "#1A1A1A",
        charcoal: "#37352F",
        slate: "#5D5B54",
        steel: "#787671",
        stone: "#A4A097",
        line: "#E5E3DF",
        "line-soft": "#EDE9E4",
        "line-strong": "#C8C4BE",
        brand: {
          navy: "#0A1530",
          purple: {
            DEFAULT: "#5645D4",
            300: "#D6B6F6",
            800: "#391C57",
          },
          teal: "#2A9D99",
          blue: "#0075DE",
          red: "#E03131",
          orange: "#DD5B00",
          pink: "#FF64C8",
          yellow: "#F5D75E",
        },
        tint: {
          peach: "#FFE8D4",
          rose: "#FDE0EC",
          mint: "#D9F3E1",
          lavender: "#E6E0F5",
          sky: "#DCECFA",
          yellow: "#FEF7D6",
          yellowBold: "#F9E79F",
          cream: "#F8F5E8",
        },
      },
      boxShadow: {
        panel: "0 16px 48px rgba(15, 15, 15, 0.16)",
        soft: "0 4px 12px rgba(15, 15, 15, 0.08)",
        mockup: "0 24px 48px -8px rgba(15, 15, 15, 0.20)",
      },
    },
  },
  plugins: [],
};
