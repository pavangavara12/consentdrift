/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        risk: {
          low: '#10B981',       // emerald-500
          medium: '#F59E0B',    // amber-500
          high: '#EF4444',      // red-500
          insufficient: '#6B7280' // gray-500
        }
      }
    },
  },
  plugins: [],
}
