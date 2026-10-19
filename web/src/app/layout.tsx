import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, IBM_Plex_Sans_Arabic, Space_Grotesk } from "next/font/google";
import { ThemeProvider } from "next-themes";

import { BetaLabel } from "@/components/layout/beta-label";
import { MotionProvider } from "@/components/layout/motion-provider";
import { SiteHeader } from "@/components/layout/site-header";
import { MemberProfileSync } from "@/components/welcome/member-profile-sync";
import { ReturningBanner } from "@/components/welcome/returning-banner";
import { ProgressProvider } from "@/lib/progress/provider";

import "./globals.css";

const display = Space_Grotesk({ variable: "--font-display", subsets: ["latin"], weight: ["500", "600", "700"] });
// Arabic lens cards only: the font files load when Arabic text first shows.
const arabic = IBM_Plex_Sans_Arabic({ variable: "--font-arabic", subsets: ["arabic"], weight: ["400", "600"] });
const body = IBM_Plex_Sans({ variable: "--font-body", subsets: ["latin"] }); // variable: weights 100–700 (reading text at 450)

export const viewport: Viewport = { viewportFit: "cover" };

export const metadata: Metadata = {
  title: { default: "MedPlat", template: "%s · MedPlat" },
  description: "Cours structurés, QCM et suivi de révision pour les étudiants en médecine.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="fr" suppressHydrationWarning className={`${display.variable} ${body.variable} ${arabic.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} disableTransitionOnChange>
          <ProgressProvider>
            <MotionProvider>
              <SiteHeader />
              <ReturningBanner />
              <MemberProfileSync />
              <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">{children}</main>
              {/* On tablets and desktop the beta notice sits in the header; on phones, under the content. */}
              <footer className="px-4 pb-8 pt-2 text-center md:portrait:hidden lg:hidden">
                <BetaLabel className="inline-flex" />
              </footer>
            </MotionProvider>
          </ProgressProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
