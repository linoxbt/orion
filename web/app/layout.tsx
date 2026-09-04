import type { Metadata } from "next";
import { Instrument_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { MotionProvider } from "@/components/motion-provider";
import { DynamicProvider } from "@/components/auth/dynamic-provider";

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
    "Orion calls your provider and negotiates the rate down. Cable, mobile, medical. Five bills a month free, or 50 cents a month for unlimited."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${grotesk.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      <body>
        <DynamicProvider>
          <MotionProvider>{children}</MotionProvider>
        </DynamicProvider>
      </body>
    </html>
  );
}
