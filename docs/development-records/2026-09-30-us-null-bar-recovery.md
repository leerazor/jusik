# 미국 Yahoo 전체 null 가격행 복구

- 상태: 완료(파서 수정·제한된 원문 보완); 작업 `us-null-bar-recovery-20260930`. 구현 `0396ed6`, main 통합 `14b850ff1187e752b9cbd1d081157b74b059fa64`, 기록 2026-09-30T11:17Z.
- [고정 범위](../../../../.local/share/jusik/portfolio-audit/20260930-us-null-bar-recovery/scope.json)의 TNMG 보관 원문 SHA를 확인하고 기존 파서의 `incomplete OHLCV` 실패를 재현했다. 272개 timestamp 가운데 2026-09-08 한 행의 OHLCV 다섯 값이 모두 null이고, 분할 사건은 2025-12-23과 그 날짜에 각각 한 건이다. 보관 원문의 정확한 요청 옵션은 입증되지 않아 기존 캐시에 삽입하지 않았다.
- 날짜·시간대·범위·중복 검사를 마친 뒤 다섯 값이 모두 null인 행만 가격행 없이 진행한다. 일부 null, 비정상 가격·타입, null 행을 포함한 중복, 전부 빈 가격행은 계속 거부한다. [보관 원문 파서 검증](../../../../.local/share/jusik/portfolio-audit/20260930-us-null-bar-recovery/archive-parse.json)은 bars 271개·결손 1개·분할 2개와 두 사건의 공급자 관측시각 미상 상태를 기록한다.
- 새 미국 수집은 v5 정규화·pool hash·`completed-us-exclusions-v4.json`을 쓴다. v2~v4 reader·hash·marker 의미는 보존하고 v5의 preferred/warrant 재표시도 거부한다. `market_history_sources.py`의 공통 data contract는 변경하지 않았다. [시장 연구](../market-research.md), [현행 조건](../research-mandate.md), [로드맵](../investment-development-roadmap.md)을 갱신하고 manifest의 Markdown 두 해시 행만 동기화했다. mandate JSON·정책 네 행·투자 기준은 불변이다.
- core 회귀 13개, 기존 사건 관측·결손 평가 회귀 3개, Ruff check/format 5파일, 소스 2파일 strict mypy, mandate/dispatch 검사 통과. 독립 [core review](../../../../.local/share/jusik/portfolio-audit/20260930-us-null-bar-recovery/core-review.json) PASS 전에 실제 GET은 0회였다.
- core PASS 이후 [고정 요청](../../../../.local/share/jusik/portfolio-audit/20260930-us-null-bar-recovery/tnmg-get-scope.json)에 따라 canonical TNMG GET을 정확히 한 번 실행했다. [조회 결과](../../../../.local/share/jusik/portfolio-audit/20260930-us-null-bar-recovery/tnmg-get-result.json)는 HTTP 200, 30,242바이트, NAS/USD 일봉 271/272세션·9월8일 결손·분할 2건·관측시각 미상으로 보관 원문과 같은 형태다. 응답 bytes는 보관 원문과 다르므로 역사 revision을 단정하지 않는다. 검증된 원문만 전용 캐시에 저장해 141→142개가 되었고 marker는 없다. 재시도·collector·전략·NAV·주문은 실행하지 않았다.
- v4 오프라인 진단의 기존 실패 23개 중 TNMG 한 키만 원문을 재확보했다. 후속 캐시 기준은 `tnmg-cache-copy/manifest.json` SHA `5867888f69e27ecb8d94ff930f3589211d20d15b5b13b4cee6cbdcc2c2fb579f`다. 기존 준비 자료의 사건 관측 결손 125건과 별도로 TNMG 분할 2건의 관측시각은 미상이다. collector를 재실행하지 않아 최종 prepared의 사건 총수와 coverage는 평가하지 않았다.
- [최종 결속](../../../../.local/share/jusik/portfolio-audit/20260930-us-null-bar-recovery/verification.json)은 보호 원본 28개, 실행 script·sentinel·원문·캐시·문서 해시와 검사 결과를 연결한다. 최종 v5 prepared·전체 표본 coverage·사건의 역사 관측 근거·PIT·비용 차감 성과는 미검증이다. 같은 TNMG 키를 재조회하지 않고 남은 결손은 새 원천 근거가 있을 때 별도 범위로 다룬다.
- workflow: 보관 원문의 실제 실패를 먼저 확인하고 기존 v4 계약 패턴만 확장했다. 독립 core 검토를 단일 GET의 선행 gate로 사용했다. 이후 작업은 이번 원문 보완이 해결하지 못한 자료 인수 차단에 집중한다.

## 통합·검증·다음 작업

- 독립 최종 review PASS. main은 검증된 구현과 backend tree 및 변경 11파일이 동일하고, audit 산출물 11개·보호 원본 28개·core 소스 5개 해시가 일치한다. `integration.json`에서 focused 13개와 기존 사건/결손 3개·정적 검사 결과를 재사용한 이유를 기록했다. 통합 후 같은 테스트·GET은 반복하지 않았다.
- 실행기 service/timer inactive, 기존 paused 유지. 별도 캐시만 추가했으며 prepared·성과 결과·투자 기준·PAPER/live·주문·결제·자격증명·원격 push 변경은 없다. 환경 버전과 ignored 경로는 audit `verification.json`·`cleanup.json`에 보존하고 작업 워크트리·브랜치를 정리했다. 사용자 루트 HANDOFF는 보존했다.
- 최근 캐시 사본에 없는 거부 응답도 9/22 보관소에는 존재한다. 후속은 그 receipt/raw와 캐시142를 우선 재사용해 남은 요청 결손의 정확한 원인·기간·재개 조건을 좁힌다. 같은 TNMG/EPRX/ICUI GET을 반복하지 않는다. TNMG 9/8 가격 1일과 분할 2건의 관측시각 미상, 기존 사건 관측 결손 때문에 비용 포함 비교로 승격하지 않는다.
- workflow 판단: 기존 조사·계획·계약·검토 증거를 이어받아 실제 실패 한 건에 한정했다.
- 근거: 회귀 16개 통과, 실제 GET 1회, 캐시 141→142, main 동일성 검증 통과. 비교 기준이 없어 시간·토큰 절감량은 미측정이다.
- 다음 조정: 추가 기능보다 남은 표본/사건 자료의 인수 조건과 비용 비교를 막는 조건을 우선 확정한다.
