# Held-band 결정 준비 handoff

- Updated: 2026-09-27T06:46:06Z
- Workspace: `/home/kwl/projects/jusik`
- Branch / verified source-evidence integration: `main` / `4cc8c26352b3d3f9a17fd7874c88dfefaddc9903`
- 상태: held-band v2 결정 준비는 계속 진행 중입니다. KRX 공식 출처 후보 검토를 완료·통합했고, 다음 독립 runnable은 기존 approximate KRX cache의 오프라인 fixture profile입니다. mandate와 기존 agent/orchestration은 변경하지 않았습니다.

## 완료한 KRX 출처 검토

- [결정 준비 문서](../research/portfolio-held-band-decision-preparation-v1.md)와 [KRX source evidence 개발 기록](../development-records/2026-09-27-held-band-krx-source-evidence.md)에 공식 서비스 범위·승인 절차·이용약관·historical PIT 한계를 기록했습니다.
- KRX 공식 catalog는 KOSPI/KOSDAQ 일별매매 및 종목기본정보를 2010-01-04부터 제공한다고 표시합니다. KR 주식 scope를 나중에 선택할 경우 KRX는 첫 일별 가격 후보입니다. 공개 문서만으로는 당시 전체 eligible universe, listing/delisting 이력, 발표·수신 시각, correction history, strict PIT 완전성을 입증하지 못합니다.
- API key와 API별 관리자 승인이 필요합니다. 약관은 비상업 사용, 제3자 제공 금지, key당 일 10,000회 한도와 정확성·완결성·연속 제공 비보장을 명시합니다. 구매 상품은 별도 비용·목적 심사를 거칩니다. 사용자 자격과 현재 credential 상태는 이 조사에서 확인하지 않았습니다.
- 기존 KRX smoke는 2025-09-11 응답 960 universe행 중 무거래 31행을 제외해 929 bars로 정규화했고, 2025-09-11~2026-09-11 수집을 완료했습니다. Approximate pilot은 `insufficient`였고 성과 지표를 만들지 않았습니다. 기존 cache는 fixture/debug only이며 성과·OOS·후보/실거래 승인 근거가 아닙니다. 상세 기록은 [KRX smoke](../development-records/2026-09-19-r6-krx-smoke.md)를 봅니다.
- 독립 read-only review PASS. `git diff --check`, local link 확인, mandate SHA, v2 unresolved 20 null과 비실행 상태를 통합 main에서 확인했습니다. 제품 코드가 없어 pytest/Ruff/mypy는 실행하지 않았습니다.

## 미정·차단 조건

- Provisional: 기존 KRX 자료는 오프라인 pipeline/fixture 품질 점검에만 사용할 수 있습니다. 공개 endpoint metadata는 조사 및 source-agnostic schema 질문에만 반영합니다. 최종 시장·자료등급·source·합격기준은 동결하지 않았습니다.
- 신규 KRX API 수집은 공개 문서 조사 범위를 벗어납니다. API별 승인, 사용 목적 적합성, credential을 확인해야 합니다. 현재 key 유무는 검사하지 않았습니다. 유료 data/service는 실제 지출 승인 전 구매하지 않습니다.
- `FINAL_VALIDATION`/OOS만 승인된 preregistration freeze 뒤 적격하고 미노출된 미래 자료가 확보될 때까지 `PENDING/BLOCKED`입니다. v2 unresolved fields 20개는 `null`, `registered=false`, `approved=false`, `execution_allowed=false`로 유지됩니다.
- 최종 data acceptance·신규 투자 기준·시장/source 확정·preregistration freeze/실행은 사용자 승인 대상입니다. 현재 오프라인 fixture 작업은 이 결정들에 의존하지 않습니다.

## 다음 실행과 운영 상태

- 등록한 `portfolio-held-band-krx-cache-fixture-profile`에서 `/home/kwl/.local/share/jusik/portfolio-audit/20260919-r6-krx-smoke`를 원본 변경·외부 호출 없이 읽고, 기간별 membership/bar coverage·누락·orphan·duplicates·수치 품질·action/timestamp·manifest integrity를 프로파일링합니다. 산출물은 `/home/kwl/.local/share/jusik/portfolio-audit/20260927-held-band-krx-cache-fixture-profile`에 둡니다. 지표 성과 계산은 하지 않습니다.
- 최신 확인 상태: roadmap runner `paused=true`, service `inactive`, timer `active`; 기존 queue에는 READY task가 없고 BLOCKED task는 개별 상태로 남아 있습니다. manual offline profile은 독립 실행 가능합니다.
- KRX source branch `docs/portfolio-held-band-krx-source-evidence`는 보존했고 clean worktree를 제거했습니다. 사용자 작성 루트 `HANDOFF.md`는 수정하지 않았습니다.
- 재개 prompt: “이 handoff와 활성 `portfolio-held-band-krx-cache-fixture-profile` 등록을 읽고, 작업 worktree 상태와 원본 audit hash를 확인한 뒤 오프라인·읽기 전용 profile을 실행하라. 성과·OOS 판단과 source 수집은 하지 말라.”
