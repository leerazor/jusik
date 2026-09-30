# 미국 전체 null 가격행 복구 인계

- 작업 `us-null-bar-recovery-20260930`; [개발 기록](../development-records/2026-09-30-us-null-bar-recovery.md)과 [검증 결속](../../../../.local/share/jusik/portfolio-audit/20260930-us-null-bar-recovery/verification.json)이 최종 읽기 진입점이다. main 병합 `14b850ff1187e752b9cbd1d081157b74b059fa64`, 독립 최종 검토·main 해시 결속 PASS. 워크트리·브랜치 정리 완료.
- TNMG 보관 원문은 272 timestamp 중 2026-09-08 OHLCV 전부 null 1행과 분할 2건이 있었다. v5 파서는 해당 가격행만 결손으로 남겨 271 bars를 유지하고 사건 2건의 관측시각 미상도 유지한다. partial null·비정상 값·중복·전체 빈 자료는 거부한다.
- v5 수집 계약과 `completed-us-exclusions-v4.json`을 추가했으며 v2~v4 계약은 보존했다. core 회귀 13개와 기존 사건/결손 회귀 3개, Ruff·strict mypy·mandate/dispatch 검사 통과. 독립 core review PASS 이후에만 단일 GET을 실행했다.
- 실제 TNMG GET 1회는 HTTP 200, NAS/USD bars 271/272·분할 2건·관측시각 null로 검증돼 전용 cache 142개에 저장됐다. 후속 캐시 기준은 `tnmg-cache-copy/manifest.json`이며 사전 sentinel과 원문 SHA를 보존한다. 보관 원문은 캐시에 삽입하지 않았고 재시도·collector·금융 실험·주문·push는 없었다.
- 후속 캐시 정본의 manifest SHA는 `5867888f69e27ecb8d94ff930f3589211d20d15b5b13b4cee6cbdcc2c2fb579f`다. 기존 실패 23개 중 TNMG 한 키만 보완됐다. 기존 준비 자료의 사건 관측 결손 125건 외에 TNMG 분할 2건도 관측시각 미상이며, collector 재실행이 없어 최종 prepared 사건 총수·coverage는 미평가다.
- 최종 v5 prepared와 전체 coverage·PIT·성과 적격성은 평가하지 않았다. TNMG 동일 키 재조회 없이 사건의 당시 관측 근거와 다른 결손 자료는 독립 범위에서 검토한다.
- workflow: 기존 계약·단일 조회 절차를 재사용했다. 검토 PASS와 정확한 응답 형태를 캐시 인수 조건으로 고정했다. 후속은 자료 차단을 줄이는 새 근거가 있을 때만 시작한다.

## 다음 시작

1. 실행기·작업 소유권을 먼저 확인한다. 재사용 캐시는 `/home/kwl/.local/share/jusik/portfolio-audit/20260930-us-null-bar-recovery/tnmg-cache-copy`다.
2. 9/22 `20260922-yahoo-excluded-receipts-20260922/receipt.json`과 raw에는 최근 캐시에서 누락된 거부 응답도 있다. 남은 요청 결손은 이 보존 근거부터 분류하고 정확한 요청 옵션이 없는 보관 원문을 현재 캐시에 임의 삽입하지 않는다.
3. TNMG/EPRX/ICUI 조회와 동일 코드 검사를 반복하지 않는다. 새로운 근거가 있는 결손만 제한 보완한다. TNMG 가격 1일·분할 관측시각과 전체 자료 인수 조건을 해결하기 전 비용 비교 실행·PIT 승격은 보류한다.

통합 근거 `integration.json`, 독립 검토 `final-review.json`, 환경/정리 `verification.json`·`cleanup.json`은 같은 audit에 있다. 과거 검증은 구현/통합 시점의 문서 해시이며 이 종료 기록 갱신 후 문서 해시와 구분한다.
