import type { Metadata } from "next";
import { Instrument_Serif, Instrument_Sans, Inter, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { MotionProvider } from "@/components/motion-provider";
import { ThemeProvider, themeInitScript } from "@/components/theme-provider";
import { DynamicProvider } from "@/components/auth/dynamic-provider";

// Editorial pairing: a serif carries the headlines and the money figures, a
// neutral grotesque carries everything you actually read, and the mono is
// reserved for machine values - task ids, call SIDs, confirmation numbers.
const display = Instrument_Serif({
  subsets: ["latin"],
  weight: ["400"],
  style: ["normal", "italic"],
  variable: "--font-display",
  display: "swap",
});

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

// The landing page's own face. Instrument Sans is one of the families
// stacks.co actually ships (their Matter is licensed and not redistributable),
// so this is the closest honest match rather than a lookalike guess.
const grotesk = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-grotesk",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Orion - Stop overpaying for the same service",
  description:
    "Orion calls your provider and negotiates the rate down. Cable, mobile, medical. Five bills a month free, or $15 a month for unlimited."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${display.variable} ${sans.variable} ${grotesk.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <ThemeProvider>
          <DynamicProvider>
            <MotionProvider>{children}</MotionProvider>
          </DynamicProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
