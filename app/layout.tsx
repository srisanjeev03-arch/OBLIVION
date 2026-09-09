import type { Metadata, Viewport } from 'next'
import { Analytics } from '@vercel/analytics/next'
import { Inter, Geist_Mono } from 'next/font/google'
import { ThemeProvider } from '@/lib/theme-context'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const geistMono = Geist_Mono({
  subsets: ['latin'],
  variable: '--font-mono-geist',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'OBLIVION — Erase. Verify. Prove.',
  description:
    'OBLIVION is an intelligent data erasure, recovery and verification platform for security and forensics teams.',
  generator: 'v0.app',
}

export const viewport: Viewport = {
  colorScheme: 'dark light',
  themeColor: '#08080a',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${inter.variable} ${geistMono.variable}`}
    >
      <head>
        {/* Apply persisted appearance before paint to avoid a flash. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var s=JSON.parse(localStorage.getItem('oblivion.appearance')||'{}');var r=document.documentElement;var t=s.theme||'dark';if(t==='system'){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}r.classList.add(t);r.setAttribute('data-density',s.density||'standard');r.setAttribute('data-corner',s.corner||'balanced');r.setAttribute('data-motion',s.motion||'full');if(s.accent){r.style.setProperty('--accent',s.accent);}if(s.accentFg){r.style.setProperty('--accent-fg',s.accentFg);}}catch(e){document.documentElement.classList.add('dark');}})();`,
          }}
        />
      </head>
      <body className="font-sans antialiased">
        <ThemeProvider>{children}</ThemeProvider>
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}
