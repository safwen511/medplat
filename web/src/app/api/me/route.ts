import { cookies } from "next/headers";

import { ACCESS_COOKIE, accessEnabled, verifyMember, VISITS_COOKIE, visitsOf } from "@/lib/access";

/** The signed-in tester (first name, gender, year) and their visit count on this device. */
export async function GET() {
  const store = await cookies();
  const member = await verifyMember(store.get(ACCESS_COOKIE)?.value);
  if (!member) return Response.json({ gate: accessEnabled(), member: null }, { headers: { "Cache-Control": "no-store" } });
  return Response.json(
    {
      gate: true,
      member: { id: member.id, firstName: member.firstName, gender: member.gender, year: member.year, role: member.role },
      visits: visitsOf(store.get(VISITS_COOKIE)?.value, member.id) || 1,
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
