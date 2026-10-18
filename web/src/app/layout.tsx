import type { Metadata } from "next";
import { Inter, Source_Serif_4 } from "next/font/google";
import { ThemeProvider } from "next-themes";

import { SiteHeader } from "@/components/layout/site-header";
import { ProgressProvider } from "@/lib/progress/provider";

import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const sourceSerif = Source_Serif_4({ variable: "--font-source-serif", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "MedPlat", template: "%s · MedPlat" },
  description: "Cours structurés, QCM et suivi de révision pour les étudiants en médecine.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="fr" suppressHydrationWarning className={`${inter.variable} ${sourceSerif.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <ProgressProvider>
            <SiteHeader />
            <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">{children}</main>
            <footer className="border-t border-border py-6 text-center text-xs text-muted">
              Contenus reconstruits à partir des cours de la faculté — brouillons non relus par un médecin.
            </footer>
          </ProgressProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
