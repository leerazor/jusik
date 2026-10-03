"use server";

import { revalidatePath } from "next/cache";
import { researchBackendUrl } from "@/lib/research";
import { approvedReadinessSchema, approvedUniverseSchema, type ApprovedInstrument, type ApprovedReadiness, type ApprovedUniverse } from "./contract";

export async function refreshApprovedReadiness(): Promise<ApprovedReadiness | null> {
  try {
    const response = await fetch(`${researchBackendUrl()}/api/research/approved-universe/readiness`, {
      cache: "no-store", signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) return null;
    return approvedReadinessSchema.parse(await response.json());
  } catch {
    return null;
  }
}

export type SaveState = {
  status: "idle" | "saved" | "invalid" | "confirm-clear" | "stale" | "error";
  message: string;
  snapshot: ApprovedUniverse | null;
  submitted: string | null;
};

export async function saveApprovedUniverse(_previous: SaveState, formData: FormData): Promise<SaveState> {
  const raw = formData.get("instruments");
  const revision = Number(formData.get("revision"));
  const failure = (status: SaveState["status"], message: string): SaveState => ({ status, message, snapshot: null, submitted: null });
  if (typeof raw !== "string" || !Number.isSafeInteger(revision) || revision < 0) {
    return failure("invalid", "저장 정보가 올바르지 않습니다. 페이지를 다시 열어 확인하세요.");
  }
  const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length === 0 && formData.get("confirm_clear") !== "on") {
    return failure("confirm-clear", "목록을 비우려면 확인란을 선택한 뒤 다시 저장하세요.");
  }
  if (lines.length > 100) return failure("invalid", "종목은 최대 100개까지 등록할 수 있습니다.");
  const instruments: ApprovedInstrument[] = [];
  for (const [index, line] of lines.entries()) {
    const parts = line.split(",").map((part) => part.trim().toUpperCase());
    if (parts.length === 2 && parts[0] === "KR") {
      instruments.push({ market: "KR", exchange: "KRX", symbol: parts[1] });
    } else if (parts.length === 3 && parts[0] === "US") {
      const exchange = parts[1];
      if (exchange !== "NAS" && exchange !== "NYS" && exchange !== "AMS") {
        return failure("invalid", `${index + 1}번째 줄: 미국 거래소는 NAS·NYS·AMS 중 하나입니다.`);
      }
      instruments.push({ market: "US", exchange, symbol: parts[2] });
    } else {
      return failure("invalid", `${index + 1}번째 줄: 한국은 KR,코드, 미국은 US,거래소,티커 형식으로 입력하세요.`);
    }
  }
  const parsed = approvedUniverseSchema.safeParse({ revision, updated_at: null, instruments });
  if (!parsed.success) return failure("invalid", "종목 코드 형식을 확인하세요. 입력한 내용은 아래에 그대로 남아 있습니다.");
  if (new Set(instruments.map((item) => `${item.market}:${item.exchange}:${item.symbol}`)).size !== instruments.length) {
    return failure("invalid", "중복 종목이 있습니다. 입력한 내용은 아래에 그대로 남아 있습니다.");
  }
  let response: Response;
  try {
    response = await fetch(`${researchBackendUrl()}/api/research/approved-universe`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ revision, instruments }),
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
  } catch {
    return failure("error", "저장 요청을 확인할 수 없습니다. 입력한 내용을 보존했습니다. 현재 목록을 확인한 뒤 다시 시도하세요.");
  }
  if (response.status === 409) return failure("stale", "다른 저장으로 목록이 바뀌었습니다. 작성한 입력은 아래에 남아 있습니다. 현재 목록을 다시 불러와 확인하세요.");
  if (response.status === 422) return failure("invalid", "종목 형식이나 중복을 확인하세요. 입력한 내용은 아래에 남아 있습니다.");
  if (!response.ok) return failure("error", "저장 요청을 확인할 수 없습니다. 입력한 내용을 보존했습니다.");
  try {
    const saved = approvedUniverseSchema.parse(await response.json());
    revalidatePath("/research/approved-universe");
    return { status: "saved", message: `종목 등록 완료 · 현재 목록 ${saved.revision}판. 저장은 목록만 등록하며 자동 비교나 주문을 시작하지 않습니다.`, snapshot: saved, submitted: raw };
  } catch {
    return failure("error", "저장 응답을 확인할 수 없습니다. 현재 목록을 다시 불러와 확인하세요.");
  }
}
