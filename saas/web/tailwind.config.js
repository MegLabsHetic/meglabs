/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#0d59f2",
        "background-light": "#f5f6f8",
        "background-dark": "#101622",
      },
      fontFamily: { display: ["Inter", "sans-serif"] },
      borderRadius: { DEFAULT: "0.25rem", lg: "0.5rem", xl: "0.75rem", full: "9999px" },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};
