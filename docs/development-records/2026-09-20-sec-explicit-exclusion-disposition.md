# SEC operator 명시적 제외 disposition

- 상태: 완료·operator review gate 보강
- 기록 시각: 2026-09-20T09:00:00Z
- 작업 slug: `sec-explicit-exclusion-disposition-20260920`
- 기준/통합: `a6d0e69` / 다음 통합 커밋
- 범위: SEC batch form에 operator가 false-positive 후보를 `exclude`와 사유로 명시할 수 있는 fail-closed disposition을 추가했습니다. action facts와 ledger 자동 적용은 변경하지 않았습니다.

## 변경과 결정

- `operator_disposition`은 기존 호환 기본값 `action`과 `exclude`만 허용합니다.
- `exclude`는 `operator_verified=true`와 비어 있지 않은 `exclusion_reason`을 요구합니다.
- 제외 행도 정본 queue identity, source URL/raw SHA, 원문 source verification을 통과해야 하며, 검토 보고서에 `excluded_accessions`로 명시됩니다.
- 제외 행에는 amount/date/ratio/revision/content hash를 요구하지 않고, 어떤 action에도 자동 ledger 적용하지 않습니다.

## 검증

- SEC evidence/action/public catalog bundle — `50 passed`
- explicit exclusion fixture: verified exclusion `ready=true`, reason 누락 `ready=false`
- Ruff, strict mypy, diff check 통과
- 기존 blank priority form은 여전히 `ready=false`이며 기존 action 기본 동작을 보존합니다.

## 안전·운영 상태

- 실제 주문·PAPER/live 승격·network collection·remote push·Windows 종료 없음.
- runner paused, service inactive, timer disabled 유지.

## 재개 조건

- 사용자가 각 priority 원문을 확인해 실제 action이면 `action` facts를 채우고, false-positive면 `exclude`와 근거를 채운 뒤 validator를 재실행합니다.
- `ready=true`는 review completeness일 뿐 action ledger/NAV/PAPER 승인을 의미하지 않습니다.
