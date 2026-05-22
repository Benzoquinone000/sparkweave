/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#F7F8FA",
        surface: "#FBFCFD",
        ink: "#1A1A1A",
        charcoal: "#2F3136",
        slate: "#5D6470",
        steel: "#737985",
        stone: "#9AA0A8",
        line: "#E3E6EB",
        "line-soft": "#EDF0F4",
        "line-strong": "#C3C9D2",
        brand: {
          navy: "#0A1530",
          purple: {
            DEFAULT: "#475467",
            300: "#D0D5DD",
            800: "#344054",
          },
          teal: "#4B8B84",
          blue: "#3C78A8",
          red: "#E03131",
          orange: "#B65E2E",
          pink: "#A35B7F",
          yellow: "#E8CC54",
        },
        tint: {
          peach: "#FFF3EA",
          rose: "#FCEEF4",
          mint: "#EDF8F2",
          lavender: "#F3F4F7",
          sky: "#EEF6FC",
          yellow: "#FFF8DE",
          yellowBold: "#F4E7AA",
          cream: "#FAF7EF",
        },
      },
      boxShadow: {
        panel: "0 18px 44px -32px rgba(15, 23, 42, 0.24), 0 1px 2px rgba(15, 23, 42, 0.04)",
        soft: "0 8px 20px -16px rgba(15, 23, 42, 0.18), 0 1px 2px rgba(15, 23, 42, 0.04)",
        mockup: "0 22px 50px -34px rgba(15, 23, 42, 0.26)",
      },
    },
  },
  plugins: [],
};
