import Link from "next/link";

import { Button } from "@/components/ui/button";

/** One calm screen: a short serif headline, one sentence, one action. */
export default function Home() {
  return (
    <div className="mx-auto flex min-h-[calc(100svh-14rem)] max-w-xl flex-col items-center justify-center gap-8 py-12 text-center">
      <div className="flex flex-col gap-5">
        <h1 className="text-4xl leading-tight text-balance sm:text-5xl">Révise tes certifs, sereinement.</h1>
        <p className="text-lg text-muted text-pretty">
          Les cours de ton année à la Faculté de Médecine de Sfax, réorganisés à partir des diapos et du
          polycopié, avec des questions pour t&apos;entraîner.
        </p>
      </div>
      <Button asChild size="lg" className="min-w-48">
        <Link href="/acces">Commencer</Link>
      </Button>
    </div>
  );
}
