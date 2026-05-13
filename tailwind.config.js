/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./eurovibe/**/*.py"],
  theme: {
    extend: {
      colors: {
        euro: {
          bg: "#09051f",
          elevated: "#151034",
          soft: "#21164a",
          text: "#fffafd",
          muted: "#bdb5d6",
          cyan: "#42e8ff",
          magenta: "#ff4fd8",
          gold: "#ffd86b",
        },
      },
      borderRadius: {
        card: "8px",
      },
    },
  },
  plugins: [],
};
