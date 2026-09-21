# R1-05 저장 영수증 대사 v1

- 상태: 완료 (오프라인 기술 감사; 전체 R1-05/PIT/경제 acceptance 미승격)
- 기록 시각: 2026-09-22T23:17:00Z
- 작업 slug: `roadmap-r1-05-cached-receipt-reconciliation-v1`
- 기준/통합: `31ed0ad204992a64316f4afc8c8fc1d7b3bd8b58` / 통합 전
- 범위: 고정 result와 cache manifest, 연결된 137개 원문의 SHA/크기와 checkpoint 결속을 검증하고 101개 진단 행을 대사했다. 원문 본문·collector·입력·운영 상태는 변경하지 않았다.

## 변경과 결정

- audit `20260922-r1-05-1f24778b/reconciliation.json`·`reconciliation.csv`에 요청 기간/warmup, request·response exchange/currency 근거, Yahoo raw chart.meta·timestamp coverage, checkpoint/raw path·SHA·size·captured_at, coverage, 원인 근거·누락 증거와 외부 receipt 필요사항을 기록했다.
- `unknown`은 그대로 보존했다. 원문이 없는 parse/identity 진단은 provider receipt 없이는 원인을 확정하지 않았다. captured_at, 정규화 session, event occurrence_at, historical observed_at(null)을 구분했다.
- 100개 저장 표본과 101개 진단 행의 차이는 기존 checkpoint 표본 교체와 request-excluded 진단 보존으로 설명했으며 새 표본을 만들지 않았다.

## 문서·계약 영향

- 사용자 문서: 해당 없음 — 저장 감사 산출물만 추가했다.
- 운영 문서: 해당 없음 — 서비스·runner·설정은 변경하지 않았다.
- API·설정·데이터 계약: 해당 없음 — collector와 입력은 읽기 전용으로 사용했다.

## 검증

- 고정 Python helper — 입력 pin, raw SHA/size 137/137, checkpoint binding 137, 진단 101행, 제외 25개, reason counts, coverage 산술 통과.
- 생성 산출물 결정성은 동일 helper 2회 실행 후 산출물 SHA 비교로 통과했으며, 결과·manifest·raw는 재생성하지 않는다.
- 네트워크 호출 0, raw 본문 복사 0, simulation/GPU/PAPER/live/order/service 변경 0.
- Ruff/strict mypy: helper가 저장소 밖 임시 경로에만 있어 project source 검사 대상이 아니며, 실행 파일을 확인하지 못해 실행하지 않았다.

## 안전·운영 상태

- 실제 주문, 외부 배포, 원격 push, 서비스·DB·설정 변경은 수행하지 않았다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260922-r1-05-1f24778b`; manifest/result pin SHA와 산출물 해시는 `hashes.sha256`에 보존했다.
- 남은 작업·차단 조건: provider request/response receipt와 historical observed_at/publication timestamp가 없어 PIT·경제 acceptance는 미평가다.
- 다음 시작: Terra 독립 검토 후 audit 해시·결정성을 확인하고 local main 통합 검사를 수행한다.
