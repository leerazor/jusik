# SEC pure action review priority packet

- 상태: review 보조 packet 완료·operator facts/ledger 적용 차단
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `sec-pure-action-review-priority-20260920`
- 기준/통합: `ecbc8de` / 통합 예정
- 범위: 기존 52개 SEC event-near queue에서 candidate kind가 정확히 하나인 dividend/split 후보만 결정적으로 추려 operator review 순서를 보조합니다. 사실을 추출하거나 action ledger에 적용하지 않았습니다.

## 변경과 결정

- 52개 중 순수 `dividend`/`split` 후보 8개를 symbol·accession·raw SHA·snippet·source URL·required fields와 함께 packet으로 보존했습니다.
- merger/suspension/delisting 및 다중 kind 후보는 packet에서 제외했지만 queue 원본은 변경하지 않았습니다.
- 모든 항목은 `unsupported_candidate`, operator review 필요, `automatic_ledger_application=false` 상태입니다.

## 검증

- queue source gate 기존 검증: 52/52 source-ready, exit 0.
- priority packet SHA-256: `fad944da3774a5edaf2f315c861fd70ae615791510874d4c1b13aa2e805cbfb1`.

## 안전·운영 상태

- SEC 원문·queue를 수정하지 않았으며 실주문·PAPER/live·remote push·Windows 종료를 수행하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-us-market-collection-recheck/sec-evidence/pure-action-review-priority.json`.
- 남은 조건: operator가 event/effective date, amount/ratio, share basis, PIT link를 확인해 `ReviewManifest`를 작성해야 R1-04 적용 검토가 가능합니다.
- 다음 시작: priority 8개 원문을 operator review하거나 ECOS API key가 제공되면 FX probe를 수행합니다.
