/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#693381",
          light: "#9361a6",
        },
        graylight: "#f3f4f6",
      },
      fontFamily: {
        sans: ["Inter", "Roboto", "ui-sans-serif", "system-ui"],
      },
      boxShadow: {
        soft: "0 2px 10px rgba(0,0,0,0.08)",
      },
      borderRadius: {
        xl: "1rem",
      },
    },
  },
  plugins: [],
}
