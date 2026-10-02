# Alpaca SIP 가격 증거 인계

- 작업 `alpaca-price-evidence-20261002`. [개발 기록](../development-records/2026-10-02-alpaca-price-evidence.md), [사용 계약](../alpaca-price-evidence.md), [최종 검증](/home/kwl/.local/share/jusik/portfolio-audit/20261002-alpaca-price-evidence/verification.json)부터 읽는다. local main 통합 `e94cdbcbc3d030489e8969878d54fe92fb4db74c`, 독립 review·통합 검증 완료.
- 기존 SIP 원문과 272세션만 사용해 9종목 1,683봉·RAPT 138 일치·0거래량 84개를 정규화했다. 7개 응답 0봉과 6개 개별 미조회를 별도 상태로 유지했다. 출력은 [결속된 증거](/home/kwl/.local/share/jusik/portfolio-audit/20261002-alpaca-price-evidence/results/atomic-final/binding.json)이며 준비 자료 승격이 아니다.
- 집중 pytest 15개·Ruff·strict mypy 통과, 실제 원문 오프라인 CLI 성공, 시장 호출 0회. 보호 입력과 기존 코드·캐시·연구 정책·runner 상태를 바꾸지 않았다.
- 남은 조건: 종목 동일성, 사건 `observed_at`, 역사적 가용시각, 가격 결손의 적격성, 비용·FX·NAV 근거가 필요하다. 이 검증 전 전략·수익률 입력으로 사용하지 않는다.

- 갱신 시각: 2026-10-02T01:40:25.022209+00:00; 기준 저장소 `/home/kwl/projects/jusik`, branch `main`. 작업 worktree/branch는 정리했고 결과·환경은 audit에 보존했다. `main-integration.json`, `review.json`, `cleanup.json`, `runtime-after.json`을 확인한다. 루트 사용자 `HANDOFF.md`는 보존했다.
- 다음 시작: 위 결과를 재생성하지 말고 `missing-sessions.json`의 실제 결손과 현 mandate를 읽어, 종목 동일성·기업행동 시각을 해결할 새 직접 근거가 있는 한정 과제를 선정한다. 외부 조회 전에 요청·상한·독립 검토를 고정한다. 유효한 비용 포함 성과 비교는 아직 없다.
