"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export function OperationsRefresh() {
  const router = useRouter();
  useEffect(() => {
    const timer = window.setInterval(() => router.refresh(), 10_000);
    return () => window.clearInterval(timer);
  }, [router]);
  return null;
}
