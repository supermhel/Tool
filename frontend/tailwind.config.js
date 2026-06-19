/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0c0f17",
        panel: "#161b27",
        panel2: "#1c2330",
        line: "#252d3d",
        line2: "#313b50",
        muted: "#9aa6bd",
        faint: "#6b7690",
        acc: "#5b8cff",
        acc2: "#36d1b7",
        vio: "#a78bfa",
        warn: "#ffb454",
        good: "#46d39a",
        bad: "#ff6b6b",
      },
    },
  },
  plugins: [],
};
