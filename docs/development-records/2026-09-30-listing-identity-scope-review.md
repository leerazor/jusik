# LIME·MDA 기간별 identity 보호 범위 검토

- 상태: 수집기 자동 결속·coverage 재분류 보류. 기존 고정 자료의 결론은 보존.
- 작업 slug: `listing-identity-scope-review`.
- 기준: 로컬 `main` `cbb47287f878675938d0195b25adf10d32eb0fbe`.
- 범위: [기존 누락 대조](2026-09-29-listing-identity-evidence.md)와 [증권 식별자 원문](2026-09-29-security-identity-evidence.md)을 입력으로 코드 조사와 읽기 전용 범위 검토만 수행했습니다.

## 결정과 근거

기존 캐시는 LIME 221세션·MDA 145세션의 현대 미국 거래 시작 전 결손과 시작 후 결손 0개를 이미 재현했습니다. `market_data_collector.py`의 Alpha listing 파서는 issuer/security 키를 보존하지 않으며 Yahoo 파서는 symbol·시장·통화·상품 종류를 확인합니다. 현재 `CollectionDiagnostics`는 종목별 사유를 기록하지만 기간별 증권 identity를 증명하지 않습니다.

고정 자료만으로 같은 366세션을 재표시하는 오프라인 보고서는 다음 사용 가능한 결과를 늘리지 않습니다. 따라서 새 진단 모듈은 만들지 않습니다. 특히 티커·회사명만으로 역사적 증권을 결속하거나 366개 결손을 정상 coverage로 재분류하지 않습니다. 실제 수집기 보호 작업은 해당 listing 행과 가격 행에 issuer/security identity, 미국 시장·통화, 효력 기간, 당시 provider `observed_at`을 연결하는 원문 receipt가 확보되면 별도 범위로 검토합니다. 구 Lime 식별자 충돌도 해결해야 합니다.

## 검증과 운영

- `explore`는 collector·진단 모델·테스트의 경로와 기존 동작을 읽기 전용으로 확인했습니다. `plan`은 위 입력의 구현 가능 범위와 인수 조건을 독립 검토했습니다. 역할별 중앙 모델 사전검사 통과. 사후 실행 로그 검사는 이 대화의 명시적 부모·자식 JSONL 경로를 확보하지 못해 완료로 주장하지 않습니다.
- 코드·테스트·원본 캐시·mandate·서비스 설정·투자 기준은 변경하지 않았습니다. 새 테스트 대상은 없습니다. R1-05는 `waiting_external`이며 경제 평가는 `NOT_EVALUATED`입니다.
- 실제 주문·PAPER/live 승격·추가 결제·원격 push 없음. 사용자 소유 미추적 루트 `HANDOFF.md`는 보존합니다.

## 재개 조건

기간별 issuer/security identity와 효력 기간을 Alpha/Yahoo 행에 결속할 신뢰 가능한 receipt가 생기면 그 원본·SHA·관측 시각을 고정하고 범위를 다시 검토합니다. 현재와 같은 입력으로 오프라인 366세션 보고서를 반복하지 않습니다.
