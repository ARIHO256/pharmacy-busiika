/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}', './apps/**/*.{html,js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f4f8fd',
          100: '#eaf3fc',
          200: '#cfe3f7',
          300: '#9ec8ed',
          400: '#63a4df',
          500: '#3b82d0',
          600: '#2468c4',
          700: '#1653a5',
          800: '#123f86',
          900: '#0a2d66',
        },
        clinical: {
          pharmacy: '#4f8a3d',
          laboratory: '#6a35b5',
          hospital: '#178a94',
          finance: '#e87822',
          warning: '#d99a16',
          danger: '#c83b3b',
        },
      },
      boxShadow: {
        clinical: '0 8px 28px rgb(15 35 65 / 10%)',
      },
    },
  },
  plugins: [],
}
