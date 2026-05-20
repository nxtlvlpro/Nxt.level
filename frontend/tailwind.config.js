/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          turquoise: "#06b6d4",
          orange: "#f97316",
          blue: "#3b82f6",
          dark: "#030708",
          panel: "#0d141c",
        },
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
      },
      fontFamily: {
        mono: ["'Roboto Mono'", "ui-monospace", "monospace"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        ticker: {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
        pulse_glow: {
          "0%, 100%": { boxShadow: "0 0 24px -8px rgba(6,182,212,0.45)" },
          "50%": { boxShadow: "0 0 40px -6px rgba(6,182,212,0.75)" },
        },
        flicker: {
          "0%, 100%": { opacity: "1" },
          "55%": { opacity: "0.85" },
        },
      },
      animation: {
        ticker: "ticker 40s linear infinite",
        glow: "pulse_glow 3.2s ease-in-out infinite",
        flicker: "flicker 4s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
