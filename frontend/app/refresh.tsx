"use client";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
export function Refresh() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <button
      disabled={pending}
      onClick={() => startTransition(() => router.refresh())}
      aria-busy={pending}
    >
      {pending ? "조회 중…" : "↻ 새로고침"}
    </button>
  );
}
