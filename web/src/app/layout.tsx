import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, Space_Grotesk } from "next/font/google";
import { ThemeProvider } from "next-themes";

import { BetaLabel } from "@/components/layout/beta-label";
import { SiteHeader } from "@/components/layout/site-header";
import { ProgressProvider } from "@/lib/progress/provider";

import "./globals.css";

const display = Space_Grotesk({ variable: "--font-display", subsets: ["latin"], weight: ["500", "600", "700"] });
const body = IBM_Plex_Sans({ variable: "--font-body", subsets: ["latin"], weight: ["400", "500", "600"] });

export const viewport: Viewport = { viewportFit: "cover" };

export const metadata: Metadata = {
  title: { default: "MedPlat", template: "%s · MedPlat" },
  description: "Cours structurés, QCM et suivi de révision pour les étudiants en médecine.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="fr" suppressHydrationWarning className={`${display.variable} ${body.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} disableTransitionOnChange>
          <ProgressProvider>
            <SiteHeader />
            <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">{children}</main>
            {/* On tablets and desktop the beta notice sits in the header; on phones, under the content. */}
            <footer className="px-4 pb-8 pt-2 text-center md:portrait:hidden lg:hidden">
              <BetaLabel />
            </footer>
          </ProgressProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
