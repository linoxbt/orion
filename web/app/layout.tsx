import type { Metadata } from "next";
import { Instrument_Serif, Inter, IBM_Plex_Mono } from "next/font/google";
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

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Orion - Stop overpaying for the same service",
  description:
    "Orion calls your provider and negotiates your bill down, using the same retention levers a professional negotiator would. You only pay a share of what it actually saves you.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${display.variable} ${sans.variable} ${mono.variable}`}
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
