import { cookies } from "next/headers";

import { ACCESS_COOKIE, accessEnabled, verifyMember, VISITS_COOKIE } from "@/lib/access";

/** The signed-in tester (first name, gender, year) and their visit count on this device. */
export async function GET() {
  const store = await cookies();
  const member = await verifyMember(store.get(ACCESS_COOKIE)?.value);
  if (!member) return Response.json({ gate: accessEnabled(), member: null }, { headers: { "Cache-Control": "no-store" } });
  return Response.json(
    {
      gate: true,
      member: { firstName: member.firstName, gender: member.gender, year: member.year, role: member.role },
      visits: Number(store.get(VISITS_COOKIE)?.value) || 1,
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
