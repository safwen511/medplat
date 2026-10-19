import { IBM_Plex_Sans, Manrope, Sora, Space_Grotesk } from "next/font/google";

import { FontSwitcher, type Pairing } from "./font-switcher";
import { Tokens } from "./tokens";

export const metadata = { title: "Styleguide", robots: { index: false } };

const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], weight: ["500", "600", "700"] });
const plexSans = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"] });
const sora = Sora({ subsets: ["latin"], weight: ["500", "600", "700"] });
const manrope = Manrope({ subsets: ["latin"], weight: ["400", "500", "600"] });

const PAIRINGS: Pairing[] = [
  {
    id: "a",
    label: "Space Grotesk + IBM Plex Sans (choisie)",
    display: spaceGrotesk.style.fontFamily,
    body: plexSans.style.fontFamily,
  },
  { id: "b", label: "Sora + Manrope", display: sora.style.fontFamily, body: manrope.style.fontFamily },
  {
    id: "c",
    label: "Clash Display + Satoshi (Fontshare)",
    display: "'Clash Display', sans-serif",
    body: "'Satoshi', sans-serif",
  },
];

export default function Styleguide() {
  return (
    <>
      {/* Fontshare fonts are not on Google Fonts; their stylesheet loads in the browser. */}
      <link
        rel="stylesheet"
        precedence="default"
        href="https://api.fontshare.com/v2/css?f[]=clash-display@500,600,700&f[]=satoshi@400,500,700&display=swap"
      />
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-16">
        <header className="flex flex-col gap-2">
          <h1 className="text-3xl">Styleguide</h1>
          <p className="text-muted">
            Étape 2 : jetons de design. Typographie retenue : Space Grotesk + IBM Plex Sans.
          </p>
        </header>
        <Tokens />
        <FontSwitcher pairings={PAIRINGS} />
      </div>
    </>
  );
}
