/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Postmodern theme typography
        mono: ['"JetBrains Mono"', 'monospace'],
        display: ['"Space Grotesk"', 'sans-serif'],
        body: ['"IBM Plex Sans Condensed"', 'sans-serif'],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        // Surface hierarchy
        'surface-1': "hsl(var(--surface-1))",
        'surface-2': "hsl(var(--surface-2))",
        'surface-3': "hsl(var(--surface-3))",
        // Status colors
        'status-active': "hsl(var(--status-active))",
        'status-warning': "hsl(var(--status-warning))",
        'status-info': "hsl(var(--status-info))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      zIndex: {
        '10': '10',
        '20': '20',
        '25': '25',
        '30': '30',
        '32': '32',
        '33': '33',
        '35': '35',
        '40': '40',
        '45': '45',
        '50': '50',
        '60': '60',
        '70': '70',
      },
    },
  },
  plugins: [],
}
