import { IBM_Plex_Sans, Manrope, Sora, Space_Grotesk } from "next/font/google";

import { FontSwitcher, type Pairing } from "./font-switcher";

export const metadata = { title: "Styleguide", robots: { index: false } };

const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], weight: ["500", "600", "700"] });
const plexSans = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"] });
const sora = Sora({ subsets: ["latin"], weight: ["500", "600", "700"] });
const manrope = Manrope({ subsets: ["latin"], weight: ["400", "500", "600"] });

const PAIRINGS: Pairing[] = [
  {
    id: "a",
    label: "Space Grotesk + IBM Plex Sans",
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
      <FontSwitcher pairings={PAIRINGS} />
    </>
  );
}
