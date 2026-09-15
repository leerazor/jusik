# 워크트리 작업 등록부

## r0-baseline-freeze

- 상태: 완료 (R0-01)
- 목표와 완료 조건: 기존 미국 기준 main·run·입력 manifest·결과 해시를 재현 기록으로 고정. 관련 검사·독립 검토·로컬 main 통합 후에만 완료합니다.
- 담당 Luna: /root/r0_freeze (code, gpt-5.6-luna), 단일 구현 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-r0-baseline-freeze
- 작업 브랜치: docs/r0-baseline-freeze
- 기준 커밋 SHA: 008ca02; 원래 연구 실행 SHA와 현재 재현 SHA는 증거에서 구분
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: docs/investment-development-roadmap.md R0-01; 기존 미국 기준 audit; 공통 계약 의존성은 plan 후 순차 확정
- 수정 허용 범위: 해당 체크 ID의 계약·재현 도구·관련 테스트와 문서. 전략·수집 정책·PAPER·실주문·운영 DB 변경 금지
- 포트·테스트 DB·출력 경로: 서버 없음; 작업별 임시 DB·환경; /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-baseline-freeze
- 검증 명령과 결과: 입력3개 hash·모델parse·cache84개 hash/size·pytest45개 통과; 통합 main parse/hash/diff 통과
- 결과 커밋 SHA: 2a2de61b26acb73723bc09b1b6a76b42809819d8
- 검토 결과와 남은 문제: /root/r0_review 중요 지적 없음; 경제적 목표 not-evaluated
- 병합 직전 main SHA: 7949c9f
- 통합 커밋 SHA와 정리 여부: 86beeeabf998b4b4e720290ac65019e6486545c0; 증거 보존·worktree 제거 완료, branch 보존
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: docs/development-records/2026-09-15-r0-baseline-freeze.md
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/HANDOFF.md

## r0-shared-contract

- 상태: 완료 (R0-02)
- 목표와 완료 조건: 자료·결과의 경로·시각·coverage·오류·등급 계약을 단일 소유자로 고정. 관련 검사·독립 검토·로컬 main 통합 후에만 완료합니다.
- 담당 Luna: /root/r0_freeze (code, gpt-5.6-luna), shared 계약 단일 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-r0-shared-contract
- 작업 브랜치: feat/r0-shared-contract
- 기준 커밋 SHA: 935a31e
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: docs/investment-development-roadmap.md R0-02; 기존 미국 기준 audit; 공통 계약 의존성은 plan 후 순차 확정
- 수정 허용 범위: 해당 체크 ID의 계약·재현 도구·관련 테스트와 문서. 전략·수집 정책·PAPER·실주문·운영 DB 변경 금지
- 포트·테스트 DB·출력 경로: 서버 없음; 작업별 임시 DB·환경; /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-shared-contract
- 검증 명령과 결과: pytest46·Ruff·mypy2개·Zod fixture·frontend lint/typecheck/build·예비 replay·diff 통과
- 결과 커밋 SHA: 176a948a4cdae1ef39b3e4c6ea70ed8692636638
- 검토 결과와 남은 문제: r0_review 중요 지적 없음; 경제적 목표 not-evaluated
- 병합 직전 main SHA: f72743f
- 통합 커밋 SHA와 정리 여부: 5f91bbac41b5ac60a2e97c368c3116e5c6daac29; 증거 보존·worktree 제거 완료
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: docs/development-records/2026-09-15-r0-shared-contract.md
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/HANDOFF.md

## r0-deterministic-replay

- 상태: 진행 (R0-03; R0-02/04 계약 통합 후 R0-05 UI와 독립 병렬)
- 목표와 완료 조건: 격리된 재실행 명령과 catalogue로 metrics·trades·equity 일치 검증. 관련 검사·독립 검토·로컬 main 통합 후에만 완료합니다.
- 담당 Luna: /root/r0_replay (code, gpt-5.6-luna), replay 단일 구현 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-r0-deterministic-replay
- 작업 브랜치: feat/r0-deterministic-replay
- 기준 커밋 SHA: dc7656d; 등록 커밋 이후 생성
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: docs/investment-development-roadmap.md R0-03; 기존 미국 기준 audit; R0-02/04 계약 통합 완료; R0-05 표시 코드는 replay 입력과 독립. 새 replay 문서로 공유 문서 충돌 방지
- 수정 허용 범위: 해당 체크 ID의 계약·재현 도구·관련 테스트와 문서. 전략·수집 정책·PAPER·실주문·운영 DB 변경 금지
- 포트·테스트 DB·출력 경로: 서버 없음; 작업별 임시 DB·환경; /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-deterministic-replay
- 검증 명령과 결과: 배정 시 확정, 미실행
- 결과 커밋 SHA: 없음
- 검토 결과와 남은 문제: 미검토; 경제적 목표 not-evaluated
- 병합 직전 main SHA: 미정
- 통합 커밋 SHA와 정리 여부: 미통합·생성 예정
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: docs/development-records/2026-09-15-r0-deterministic-replay.md (예정)
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/HANDOFF.md (예정)

## r0-currency-contract

- 상태: 완료 (R0-04)
- 목표와 완료 조건: 독립 원화 계좌·초기 자본·USD/KRW 단위·환전 방향 명시. 관련 검사·독립 검토·로컬 main 통합 후에만 완료합니다.
- 담당 Luna: /root/r0_freeze (code, gpt-5.6-luna), shared 계약 단일 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-r0-currency-contract
- 작업 브랜치: feat/r0-currency-contract
- 기준 커밋 SHA: 967df2f
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: docs/investment-development-roadmap.md R0-04; 기존 미국 기준 audit; 공통 계약 의존성은 plan 후 순차 확정
- 수정 허용 범위: 해당 체크 ID의 계약·재현 도구·관련 테스트와 문서. 전략·수집 정책·PAPER·실주문·운영 DB 변경 금지
- 포트·테스트 DB·출력 경로: 서버 없음; 작업별 임시 DB·환경; /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-currency-contract
- 검증 명령과 결과: pytest48·Ruff·mypy2개·Zod fixture·frontend lint/typecheck/build·diff 통과
- 결과 커밋 SHA: 62ae5ac2dbae4c431cbd1f9d11f806e24d04447c
- 검토 결과와 남은 문제: r0_review 중요 지적 없음; 경제적 목표 not-evaluated
- 병합 직전 main SHA: 96698df
- 통합 커밋 SHA와 정리 여부: f949a635bc6e750b6d2b50a5a0beb889890f0111; 증거 보존·worktree 제거 완료
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: docs/development-records/2026-09-15-r0-currency-contract.md
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/HANDOFF.md

## r0-grade-contract

- 상태: 완료 (R0-05)
- 목표와 완료 조건: strict·approximate·fixture·PAPER의 결과·화면 표시 규칙과 호환 fixture 고정. 관련 검사·독립 검토·로컬 main 통합 후에만 완료합니다.
- 담당 Luna: /root/r0_freeze (code, gpt-5.6-luna), 단일 구현 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-r0-grade-contract
- 작업 브랜치: docs/r0-grade-contract
- 기준 커밋 SHA: 7ea9825
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: docs/investment-development-roadmap.md R0-05; 기존 미국 기준 audit; 공통 계약 의존성은 plan 후 순차 확정
- 수정 허용 범위: 해당 체크 ID의 계약·재현 도구·관련 테스트와 문서. 전략·수집 정책·PAPER·실주문·운영 DB 변경 금지
- 포트·테스트 DB·출력 경로: 서버 없음; 작업별 임시 DB·환경; /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-grade-contract
- 검증 명령과 결과: npm fixture·lint·typecheck·build·Playwright등급/상태heading·diff 통과
- 결과 커밋 SHA: 455ccdc76c5289726b22c8b579fed49d27b13ecb
- 검토 결과와 남은 문제: r0_review 중요 지적 없음; 경제적 목표 not-evaluated
- 병합 직전 main SHA: cd161ec
- 통합 커밋 SHA와 정리 여부: 01f2d6850e9a991d8eb0688127cc8f8fec8eb523; 증거 보존 후 제거 예정
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: docs/development-records/2026-09-15-r0-grade-contract.md
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/HANDOFF.md

## investment-development-roadmap

- 상태: 완료 (계획 문서); R0~R7 후속 기능은 미완료
- 목표와 완료 조건: 미국 손실 진단을 우선으로 단계별 목표·체크리스트·증거·병렬 소유권·통합 기준을 문서화하고 다음 개발의 기준 문서로 연결합니다. 이번 범위는 계획 문서이며 후속 기능의 완료를 의미하지 않습니다.
- 담당 Luna: roadmap_code, 문서 단일 구현 소유자. 감독은 등록부만 관리합니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-investment-development-roadmap
- 작업 브랜치: docs/investment-development-roadmap
- 기준 커밋 SHA: c2ada5c6a8770ac81519a3d41b8aff693e5723d1
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: 미국 1년 파일럿과 KRX 인증 통과 후 zero-OHLC 수집 실패, 현재 mandate, 사용자 계획·체크리스트·병렬 개발 요청
- 수정 허용 범위: docs/investment-development-roadmap.md, docs/architecture.md 안내 링크, 해당 개발 기록. 거래 정책·코드·mandate·사용자 agent-tooling 변경 제외
- 포트·테스트 DB·출력 경로: 서버·DB 미사용. 외부 audit /home/kwl/.local/share/jusik/portfolio-audit/20260915-investment-development-roadmap
- 검증 명령과 결과: 작업/통합 main의 문서 검사에서 40개 고유 미완료 체크 ID·8단계·2개 로컬 링크와 diff 검사를 통과했습니다. 미국 artifact hash를 대조했고, 독립 review에서 의존성과 실제 grade별 final 계약을 확인했습니다. 문서 전용이므로 제품 테스트·lint·typecheck·build는 실행하지 않았습니다.
- 결과 커밋 SHA: 03ce143f51e7ee847ad4d5cacf3ee876a50fdb8f, 08aee0e12dda4fd4282aa3bc370443b0ce9a6777
- 검토 결과와 남은 문제: 독립 review 최종 중요 지적 없음. 후속 실제 구현은 체크리스트에서 미완료로 유지하며 R0 기준 재현·공통 계약부터 착수합니다. 이후 R1/R2/R3 병렬, R4 계산은 UI 완료를 기다리지 않습니다.
- 병합 직전 main SHA: c2ada5c6a8770ac81519a3d41b8aff693e5723d1
- 통합 커밋 SHA와 정리 여부: 1d6ebfce1ecf2620a0c670e24866e5608f67572a; 통합 검증·증거·handoff 보존 후 전용 worktree 제거 완료, branch 보존
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: docs/development-records/2026-09-15-investment-development-roadmap.md 갱신
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260915-investment-development-roadmap/HANDOFF.md 저장

## market-data-live-contract-fixes

- 상태: 완료
- 목표와 완료 조건: 실제 provider smoke에서 확인한 KRX Open API 요청 계약과 Alpha Vantage 종목 정규화 오류를 수정합니다. 공식 KRX endpoint·`AUTH_KEY` header·`basDd`를 사용하고, 미국 목록에서 보통주가 아닌 상품과 비정상 표시명을 한 행 단위로 제외해 전체 수집을 보존합니다. 사용자가 저장한 안전한 env alias를 지원한 뒤 KR/US 소규모 실제 smoke를 재실행합니다.
- 담당 Luna: /root/luna_investor (code, gpt-5.6-luna), 단일 구현 소유자. explore→plan→code→review 순서로 진행합니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-market-data-live-contract-fixes
- 작업 브랜치: fix/market-data-live-contract-fixes
- 기준 커밋 SHA: e608835832f2a3f9b3ba0ecfa247ddafd54a93b4
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: free-market-data-collector 완료 main 8521268, durable docs main 8602e3b. 실제 smoke에서 구현 KRX URL은 HTTP 403, 공식 KRX KOSPI·KOSDAQ endpoint는 현재 키로 401, Alpha 응답은 긴 warrant 명칭 때문에 전체 validation 실패했습니다.
- 수정 허용 범위: collector source URL/request/response parser, listing security-type/name normalization, collector env loading·CLI, 관련 테스트·문서·mandate/checksum·개발 기록. 전략·PAPER·broker/order·프런트는 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 3366/8366, worktree-local test environment. 실제 smoke raw/cache/output은 `/home/kwl/.local/share/jusik/portfolio-audit/20260915-market-data-live-contract-fixes`에 비밀정보 없이 저장합니다. 운영 주문은 사용하지 않습니다.
- 검증 명령과 결과: 작업 및 통합 main에서 관련 pytest 99개, Ruff, strict mypy 9개 source, `git diff --check`, Next.js production build가 통과했습니다. 독립 review는 KRX 손상 envelope, 설정 오류 비노출, 인증 실패 비캐시, Yahoo NASDAQ `NCM` identity를 직접 probe하고 최종 P1/P2 없음으로 판정했습니다. 실제 US 2종목 smoke는 재개 시 manifest 불변과 `ready:true`를 확인했고, 안정 완료일 기준 1년·100종목 수집과 웹 API 파일럿 실행을 완료했습니다.
- 결과 커밋 SHA: 9a3bf3a, e8a7465, feb836f, aeeed81.
- 검토 결과와 남은 문제: KRX KOSPI·KOSDAQ 공식 endpoint는 현재 키를 `krx authentication was rejected`로 거부하므로 한국 자료와 실행은 준비되지 않았습니다. US 1년 표본은 100개 중 40개가 완전한 무배당·무분할 이력으로 남았고 60개는 기업행사·부분/무응답·identity 불일치로 제외됐습니다. 무료 근사 표본의 선택 편향과 배당 미반영 한계를 유지하며 PAPER·실주문에는 사용하지 않습니다.
- 병합 직전 main SHA: e69f85876e4b25f7ba689c228a1ad1bfbee6d59a
- 통합 커밋 SHA와 정리 여부: fee4eddb21e022fe3a89c4d269a7ed53fc03a06d. 통합 검증과 handoff 보존 후 전용 워크트리를 제거했습니다.
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: `docs/development-records/2026-09-15-market-data-live-contract-fixes.md` 갱신 완료
- handoff 저장 경로와 갱신 여부: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-market-data-live-contract-fixes/HANDOFF.md` 및 루트 `HANDOFF.md` 갱신 완료

## free-market-data-collector

- 상태: 완료
- 목표와 완료 조건: 무료·공개 원천에서 한국·미국의 날짜별 종목 구성, 조정 가능한 과거 OHLCV와 미국 KRW/USD 환율을 실제로 수집해 기존 approximate prepared dataset을 생성합니다. 원본 응답과 provenance를 보존하고, 호출 제한·중단 재개·부분 실패를 안전하게 처리하며, 현재 종목을 과거에 소급하지 않습니다.
- 담당 Luna: /root/luna_investor (code, gpt-5.6-luna), 단일 구현 소유자. explore→plan→code→review 순서로 진행합니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-free-market-data-collector
- 작업 브랜치: feat/free-market-data-collector
- 기준 커밋 SHA: f15a3ffcbedc0355e406277acac2ef4b4d994a06
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: approximate-market-data 완료 main 0d56e251751793543b1e941f9fec474182b27998, 기존 `ApproximateDataset`·`import-file`·readiness 계약, 최신 연구 mandate. 사용자는 무료 데이터 수집기부터 진행하도록 승인했습니다.
- 수정 허용 범위: market-data 수집 adapter·정규화·raw/cache manifest·재개 가능한 CLI, 관련 config·환경 예시·테스트·시장 연구 문서와 mandate. 전략·PAPER·broker/order·프런트 실행 계약은 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 3365/8365, 워크트리 내부 임시 raw/cache와 pytest tmp_path. 운영 DB·공유 cache·실제 주문은 사용하지 않습니다. 실제 smoke는 비밀값을 기록하지 않고 별도 임시 디렉터리에 제한합니다.
- 검증 명령과 결과: 통합 main에서 collector·approximate·market research·API·mandate 관련 pytest 104개, Ruff와 strict mypy 8개 source가 통과했습니다. 독립 review는 KRX 공식 POST/trdDd 계약, 날짜별 LIST_SHRS 기업행사 proxy, 한국 canonical symbol, 미국 Alpha Vantage membership·Yahoo OHLCV·FRED 사전 관측 환율, 미래 checkpoint 독립성, retry별 호출 예산, cache hash·완료 marker·원자적 출력과 비밀정보 비노출을 probe로 확인하고 최종 P1/P2 없음으로 판정했습니다. 자격증명 없는 CLI smoke는 exit 2, ready false, 기존 출력 보존을 확인했습니다.
- 결과 커밋 SHA: 0102858, a52387e, b43f0ef, 57b27d9, e591f21, 6722606.
- 검토 결과와 남은 문제: KRX는 날짜별 KOSPI·KOSDAQ 일별매매정보를 사용하고 상장주식 수 변화·거래행 누락·종목 소멸을 이벤트 이후 제외합니다. 미국은 시작 시점 historical listing에서 표본을 고정하고 이후 checkpoint를 과거에 소급하지 않으며 Yahoo 가격과 거래 시점 전에 이용 가능한 FRED 환율만 사용합니다. 현재 KRX·Alpha Vantage·FRED 키와 KRX 서비스 승인이 없어 실제 provider smoke와 1년 파일럿 데이터 생성은 아직 실행하지 않았습니다.
- 병합 직전 main SHA: d5b633075f85f871d20bf41311edde0af31860d6
- 통합 커밋 SHA와 정리 여부: 1407d71fe5b4327b8e81c0429a38055e63f30bd0. 통합 검증·배포·handoff 후 전용 워크트리를 정상 제거합니다.
- 통합 검증 실패 원인과 복구 결과: 첫 재배포에서 ngrok 새 터널의 basic-auth 확인이 일시적으로 실패해 전체 프로세스가 안전 종료됐습니다. 같은 정책의 독립 probe에서 1초부터 인증 적용을 확인한 뒤 제품 변경 없이 재시작하여 외부 비인증 401을 재확인했습니다.
- 개발 기록 경로와 갱신 여부: `docs/development-records/2026-09-15-free-market-data-collector.md`에 완료 범위, 계약, 검증, 안전 상태와 재개 조건을 기록합니다.
- handoff 저장 경로와 갱신 여부: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-free-market-data-collector/HANDOFF.md` 및 루트 `HANDOFF.md`를 갱신합니다.

## approximate-market-data

- 상태: 완료
- 목표와 완료 조건: 논문급 전수 PIT 대신 개인 투자 판단용 무료 근사 자료로 한국·미국의 1년 파일럿과 3년 최종 연구를 실행할 수 있게 합니다. 현재 후보의 과거 고정은 금지하고, 과거 연간 종목 목록의 결정적 표본 안에서 거래일마다 거래량 상위 20개를 재발굴합니다. 근사 등급·coverage·누락·배당/상폐/환율 가정을 결과와 웹에 공개하며 strict·fixture·PAPER·실거래와 혼합하지 않습니다.
- 담당 Luna: /root/luna_investor (code, gpt-5.6-luna), 단일 구현 소유자. explore·plan·구현·독립 review와 지적 수정 재검토를 완료했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-approximate-market-data
- 작업 브랜치: feat/approximate-market-data
- 기준 커밋 SHA: b5117e4899a2be37bda6033297034db691ff632d
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: staged-market-validation 완료 main b850984, 사용자 승인 “논문을 쓰는 것이 아니므로 과도하게 정교한 데이터 없이 실용적으로 진행”. 현재 후보를 과거로 소급하지 않는 기존 결정은 유지합니다.
- 수정 허용 범위: approximate market history source·모델·저장소·전략 분기·service/API/CLI/config/cache, 관련 fixture·테스트, `/research/market` coverage UI·타입, `.env.dev.example`, mandate·시장 연구 문서. strict PIT, 기존 PAPER·operations·broker/order 경로는 보존합니다.
- 포트·테스트 DB·출력 경로: 작업 서버 3364/8364, 워크트리 내부 Python/Node 환경, pytest 임시 DB·fixture·cache. 실제 무료 source smoke는 별도 임시 cache/artifact만 사용하고 운영 DB·실제 주문은 사용하지 않습니다.
- 고정 계약: research grade는 strict와 approximate를 분리합니다. approximate 기본 표본은 과거 연간 목록에서 고정 seed로 시장별 최대 100개이며 매일 표본 내 거래량 순위를 재계산합니다. pilot/final은 같은 source·표본·정규화·누락 정책 계약만 연결합니다. 개별 비보유 종목 자료 누락은 제외 수와 coverage를 기록하고 허용하지만, 거래일 전체 모집단·초기 FX·숫자/통화 오류는 차단합니다.
- 검증 명령과 결과: 통합 main에서 관련 pytest 82개, Ruff, strict mypy 8개 모듈, frontend lint/typecheck/production build와 `git diff --check`가 통과했습니다. 독립 review는 일별 membership의 다음 시가 인과성, 수수료·슬리피지·세금·SMA 청산·20종목 한도·낙폭 latch, strict 분리, 파일 import의 provenance·기간 검증을 확인했고 최종 P1/P2 없음으로 판정했습니다. iPad 1024×1366 브라우저에서 네 등급·시장 준비 카드와 실행 폼을 확인했고 console error 0건이었습니다.
- 결과 커밋 SHA: 8228f3c, dd1b1c5, 45eba8f, e09181c, 3044bbe, 1cdd7e2, 96835de, 3f4e822, 12185b7.
- 검토 결과와 남은 문제: 실제 네트워크 수집기를 구현한 것이 아니라 검증된 prepared response file의 `import-file`과 운영 cache 소비 경로를 구현했습니다. 현재 준비 파일과 KRX·Alpha Vantage·Yahoo·FRED 자료가 없어 KR/US approximate readiness는 false이며 실제 1년·3년 수익률을 생성하지 않았습니다. 웹은 파일 부재와 invalid 파일을 구분하고, 근사 표본·coverage·누락·배당/상폐 한계를 표시합니다. PAPER·실주문은 변경하지 않았습니다.
- 병합 직전 main SHA: 60117dcad87682c75c2eb3cc3f252f11ffbcc004
- 통합 커밋 SHA와 정리 여부: 기능 통합 20117bf5b946139c86754ac360376993d7f5c3b1, 검증 수정 통합 7cba46b2b4032b1135264027a5c93aaa8af1f81b, readiness 통합 c9089b893a918d0968b1d52653096bacf9799588. 검증과 handoff 보존 후 이번 워크트리를 정상 제거합니다.
- 통합 검증 실패 원인과 복구 결과: 기준 저장소 가상환경 경로 차이, cwd 상대 checksum 테스트, strict mypy의 불필요 ignore를 수정했습니다. 운영 API에서 발견한 cache·달력·KR/US FX 상태/문구 모순과 invalid 파일 오표시도 수정하고 재배포·재검증했습니다.
- handoff 저장 경로와 갱신 여부: `/home/kwl/.local/share/jusik/portfolio-audit/20260914-approximate-market-data/HANDOFF.md` 및 루트 `HANDOFF.md`를 갱신합니다.

## staged-market-validation

- 상태: 완료
- 목표와 완료 조건: 시장 PIT 연구를 1년 파일럿과 정책 고정 3년 최종 검증으로 분리합니다. 파일럿은 자료·인과성 검증 전용이며 모델 선택이나 PAPER/실거래 활성화 근거가 될 수 없습니다. 최종 실행은 완료된 같은 시장 파일럿을 참조하고 동일 정책·자본·비용·원천 계약을 강제하며, 평가 시작 전 20개 완료 거래일의 준비 자료까지 검증합니다.
- 담당 Luna: /root/luna_investor (code, gpt-5.6-luna), 단일 구현 소유자. explore·plan·구현·독립 review와 지적 수정 재검토를 완료했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-staged-market-validation
- 작업 브랜치: feat/staged-market-validation
- 기준 커밋 SHA: 9a22fd044433aac4a1fd2ce0e432fcf8138c69f3
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: point-in-time-discovery 완료 main 40a022f, 최신 research mandate, 사용자 승인 “1년 파일럿 후 동일 정책 3년 최종 검증”. 실제 provider 자료는 계속 부족하므로 production 실행은 fail-closed입니다.
- 수정 허용 범위: market research request/run/result/store/service/strategy/API, 관련 fixture·테스트, `/research/market` 단계 UI와 타입, mandate·시장 연구 문서. 기존 PAPER·operations·broker/order 경로와 일반 연구 엔진은 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 작업 서버 3363/8363, 워크트리 내부 Python/Node 환경, pytest 임시 DB와 fixture. 운영 DB·공유 연구 DB·실제 주문·기존 서버는 사용하지 않습니다.
- 고정 계약: pilot은 end date의 정확한 1년 전부터, final은 정확한 3년 전부터 평가하며 윤년 2월29일은 대상연도 2월28일로 맞춥니다. final은 completed·ready·complete pilot ID가 필수이고 market, current policy hash, 자본·수수료·세금·슬리피지, canonical data contract hash가 같아야 합니다. input hash는 기간별로 다릅니다. 시작 전 20개 완료 시장 세션은 지표 warmup이며 거래·equity를 만들지 않고, 신규 상장 전 bar를 요구하지 않습니다.
- 검증 명령과 결과: 통합 main에서 market research·research API·runner planning pytest 51개, Ruff format/check, strict mypy 7개 모듈, frontend lint/typecheck/production build와 `git diff --check`가 통과했습니다. 운영 API는 KR/US 모두 실제 PIT provider 필수 자료 부족을 반환했고, iPad 1024×1366 브라우저에서 1년 파일럿→3년 최종 UI와 console error 0건을 확인했습니다. 외부 ngrok은 기존 인증 정책에 따라 비인증 401입니다.
- 결과 커밋 SHA: 7d33b34, cc78b2e, 318f9d6, fe038fe, 5c2fe6e, cbffc59.
- 검토 결과와 남은 문제: 신규상장 warmup 예외, 고정 가정·legacy 우회, 시장 불일치 UI, 과거 staged 행 읽기 호환성, final 후보 표시 진실성, 중첩 가변 list 역직렬화를 수정했습니다. 독립 최종 검토 P1/P2 없음. 실제 1년·3년 성과 산출은 membership·OHLCV·기업행사·PIT FX 공급원 연결 뒤 별도 실행합니다.
- 병합 직전 main SHA: bfb31f6a13ab081d09a1cb1f48d2116f1268c7ed
- 통합 커밋 SHA와 정리 여부: bb02962fbce5257c47f0ac729c05a337237862c6. 통합 검증과 handoff 보존 후 작업 워크트리를 정상 제거합니다.
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- handoff 저장 경로와 갱신 여부: `/home/kwl/.local/share/jusik/portfolio-audit/20260914-staged-market-validation/HANDOFF.md` 및 루트 `HANDOFF.md`를 갱신합니다.

## point-in-time-discovery

- 상태: 완료
- 목표와 완료 조건: 한국·미국을 각각 1억원의 독립 계좌로 모의 운용합니다. 과거 각 거래일 종가까지 공개된 전체 시장 자료로 개별주 거래량 상위 20개를 다시 산출하고, 진입·청산 신호를 다음 거래일 시가에 체결해 수익률을 계산합니다. 전체 종목 OHLCV·당시 상장 상태·기업행사·환율 중 필수 자료가 누락되면 결과를 만들지 않고 준비 상태와 원인을 표시합니다. 현재 후보를 과거에 고정하는 경로는 허용하지 않습니다.
- 담당 Luna: /root/luna_investor (code, gpt-5.6-luna), 단일 구현 소유자. explore·plan·독립 review와 수정 재검토를 완료했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-point-in-time-discovery
- 작업 브랜치: feat/point-in-time-discovery
- 기준 커밋 SHA: 30c221107d79868cb3605fd0cb6c4c48ab484d95
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: 최신 `docs/research-mandate.json`, 기존 investor 거래량 발굴 규칙과 research portfolio 비용·환율·검증 계약. KRX Open API와 미국 전시장 자료 공급자의 자격증명은 현재 없으므로 실제 3년 성과를 만들지 않습니다.
- 수정 허용 범위: point-in-time 시장 원장·source adapter·동적 발굴/백테스트 모델과 API, investor/research 웹 연결, 설정 예시·사용자 문서·mandate 및 관련 테스트. 기존 PAPER·실주문·operations 실행 계약은 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 작업 서버 3362/8362, 워크트리 내부 Python/Node 환경, pytest 임시 DB와 fixture. 운영 DB·공유 연구 DB·실제 주문·기존 서버는 사용하지 않습니다.
- 고정 연구 규칙: 시장별 최대 20종목, 신규 진입은 당시 NAV 5%, 거래량 순위 우선, 현금 부족 시 건너뛰고 기록, 기존 보유는 후보 이탈만으로 매도하지 않음. 20일 고점 돌파 및 당일 거래량이 직전 완료 20일 평균 초과 시 다음 시가 진입, 종가가 SMA20 아래인 상태가 2거래일 연속이면 다음 시가 청산. 미국 계좌는 시작 시점 환율과 비용으로 USD를 조성하고 USD 원장과 KRW 평가 곡선을 함께 제공합니다. KRW NAV 기준 최대 낙폭 20%입니다.
- 검증 명령과 결과: main 관련 pytest 43개, 신규·mandate 35개, Ruff check/format, strict mypy 8개 모듈, frontend lint/typecheck/production build 통과. 전체 pytest는 957개 통과·기존 현재 시각 의존 3개 실패였습니다. iPad 크기 운영 브라우저에서 두 시장의 필수 자료 부족 상태, 연구 단계·메뉴와 console error 0개를 확인했습니다.
- 결과 커밋 SHA: 59e5a74, cc54ea5, 706b7ba, 28203a2, 97e8035, 74218f5. 후속 연결 수정은 main에 ae30e0c로 cherry-pick했습니다.
- 검토 결과와 남은 문제: 미래 일봉·FX, 기업행사 무시, 체결일 자료 누락, 시장·통화 혼합, readiness 조작, artifact 불일치, final-day 낙폭 청산 미체결과 잘못된 backend URL을 수정했습니다. 독립 최종 검토 P1/P2 없음. 실제 3년 실행은 KRX 승인 자료와 미국의 검증 가능한 전시장 OHLCV·historical membership/actions·PIT FX가 모두 준비된 뒤 별도 수행합니다.
- 병합 직전 main SHA: 84de414fbb664cd5534d69d65f5c3e8fafd2d120
- 통합 커밋 SHA와 정리 여부: 기능 통합 052ba5f5a1c8b7168c849a7cb7ac68b57183c458, 최종 코드 ae30e0c73e6778c700bf87c3ae4f79af5a1a98cc. 검증·handoff 보존 후 이번 워크트리를 정상 제거합니다.
- 통합 검증 실패 원인과 복구 결과: 운영 브라우저에서 연구 화면이 일반 backend 8000을 조회해 자료를 못 불러오는 문제를 발견했습니다. 기존 `researchBackendUrl`로 수정·추가 통합·재배포 후 한국·미국 readiness 표시를 확인했습니다. 전체 pytest의 3개 실패는 이번 diff 밖의 날짜·현재 시각 의존 기존 테스트입니다.
- handoff 저장 경로와 갱신 여부: `/home/kwl/.local/share/jusik/portfolio-audit/20260914-point-in-time-discovery/HANDOFF.md` 및 루트 `HANDOFF.md`를 갱신합니다.

## volume-discovery

- 상태: 완료
- 목표와 결과: 승인한 거래량 기준으로 한국·미국 개별주 후보를 각각 최대 20개 제공하고 ETF를 별도로 분리했습니다. 미국 NAS/NYS/AMS를 숫자 거래량으로 통합 정렬하고 직전 완료 20거래일 평균 대비 거래량 배수를 웹에 표시합니다.
- 담당: /root/luna_investor (gpt-5.6-luna), 단일 구현 소유자. explore·plan·독립 review 완료. 원본 turn context 대조로 code 11개 turn과 review 9개 turn 모델을 확인했습니다. 사후 helper의 지연 settings marker 한계와 동등 검증 근거는 audit에 보존했습니다.
- 워크트리·브랜치: /home/kwl/projects/jusik-volume-discovery, feat/volume-discovery. 통합 검증 및 산출물 보존 후 정상 제거했습니다. 기존 미완료 워크트리 6개는 보존했습니다.
- 기준 및 병합 직전 main: 11a9e61. 결과 커밋: e3c6dda, 335baee, 5b6cff0. 기능 통합: 2127399afeb26a9cdc6d17fdbf7c4b4616459220. 형식 수정 최종 통합: db11b1ba847570429632e23f97e7980c281fc1c7.
- 변경 범위: investor 후보 데이터·모델·fixture·관련 검사, 웹 후보 목록·계약과 사용자 안내. 실제 동시 조회 실패를 재현한 뒤 kis.py의 credential별 인증 공유까지 범위를 좁혀 추가했습니다. 기존 가치·매도 분석, 논거 저장, 연구·주문 로직과 운영 DB는 보존했습니다.
- 검증: main pytest 99개, strict mypy 8개 모듈, Ruff 6개 파일, frontend lint/typecheck 및 운영 production build 통과. 형식 수정 후 영향 테스트 63개 재통과. 기존 논거 합성 브라우저 20개, 후보 화면 35개, 운영 브라우저 49개 검사 통과.
- 실제 자료: 새 프로세스 첫 동시 조회 8.06초, 한국·미국 주식 각 20개, ETF 18/20개. 미국 주식 NAS 12/NYS 7/AMS 1. NVDA 20일 평균을 별도 원자료로 재계산해 일치 확인했습니다.
- 검토 및 복구: 코스닥 코드 대체 조회 누락, 동시 인증 충돌, 분할 당일 배수 계산, 공유 작업 취소 전파, 미검사 건수와 합성 수치 불일치를 수정했습니다. 독립 최종 검토 P1/P2 없음. main 형식 검사에서 테스트 파일 2개가 실패하여 동일 Luna가 수정했고 재검사가 통과했습니다.
- 한계: KIS 첫 페이지 수집 후보를 정렬하며 전체 시장 순위를 보장하지 않습니다. Yahoo 분류 미확인 후보는 제외하고, 일별 이력·분할 등으로 배수가 불확실하면 사유와 함께 보류합니다. KIS 순위 수량과 Yahoo 배수 분자·시각을 구분해 공개합니다.
- 운영: /investor와 종목 상세를 운영 웹에 반영했습니다. 자동 실행기 paused, service/timer inactive 유지. 테스트 3351/8351 및 브라우저 종료. 실제 주문·원격 push 없음. 기존 사용자 미추적 파일 보존.
- 증거와 handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260914-volume-discovery/HANDOFF.md. 검사 결과·diff·환경 버전·실제 자료·화면·합성 DB를 보존하고 루트 HANDOFF.md 최신 안내를 추가했습니다.

## investor-workflow

- 상태: 완료
- 목표와 완료 조건: 한국·미국 후보 발굴, 가치·추세 진입 판단, 투자 논거 저장과 보유·매도 검토를 코드와 웹에 연결했습니다. local main 통합·독립 검토·운영 웹 반영·handoff와 작업 정리를 완료했습니다.
- 담당 Luna: /root/luna_investor (gpt-5.6-luna), 구현 소유자 한 명. explore·plan·code·review 순서로 진행했습니다. reviewer 사후 helper는 7개 turn을 통과했고 Luna 8개 turn의 원본 child turn_id/model을 별도 확인했습니다. 지연된 settings marker로 인한 helper 오류는 audit에 원문 근거와 함께 기록했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-investor-workflow. 통합 검증·산출물 보존 후 정상 제거했습니다.
- 작업 브랜치: feat/investor-workflow. 모든 결과 커밋 통합 후 정상 삭제했습니다.
- 기준 커밋 SHA: d578bf62bb6bbb98a7ba0c5edddd93d4ba3a12de.
- 통합 대상 브랜치: local main. 첫 병합 직전 9fd1851, 기능 통합 3466db260c190f9d6b0efa3cda4687402112ef8d, 헤더 수정 추가 통합 5b58c5e2e10561d583656f130498a471f41f3f0c.
- 입력과 범위: 사용자 투자자 관점 로직 구현 요청. 기존 KIS 조회와 Yahoo 가격·조정 일봉을 사용하며 시장 전수 평가나 자동 내재가치 산정으로 표시하지 않습니다. 사용자 EPS·목표 PER·안전마진 가정으로 가격 범위를 계산합니다. 연구 결과·PAPER10%·주문 실행 경계를 보존했습니다.
- 결과 커밋 SHA: 4b02b8a, 99f22e2, bd6c589, d733108, af3c077, a53ca4b, 6a756c3. 최초 중간 커밋 b747498은 작업자가 정리했으며, 이후 후속 수정은 별도 커밋으로 보존했습니다.
- 검증 결과: main 관련 pytest 90개, 변경 Python 9개 Ruff/format 및 8개 strict mypy 통과. frontend lint/typecheck와 운영 production build 통과. fixture 브라우저 25개, 운영 화면 14개와 최종 겹침 검사 12개 통과. 실제 KR/US 후보 각 20개, 삼성전자/NVIDIA/코스닥 086520의 사용 가능한 시세와 확정 일봉 확인.
- 검토와 복구: 종목 동일성·회계기간·코스닥·저장 후 최신 재평가·시세 지연·통화·종류 검증·오류 URL 인코딩을 보완했습니다. 운영 이미지에서 발견한 전역 header 높이 상속 겹침도 수정 후 확인했습니다. 최종 독립 검토 중요 지적 없음.
- 포트·테스트 DB·산출물: fixture 8341 및 테스트 웹 3341 종료. 전용 환경·테스트 DB 3개를 정리했으며, 필요한 결과·패치·환경 정보 등 audit 77개 파일의 SHA를 확인했습니다. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260914-investor-workflow.
- 운영 상태: /investor와 기존 /research HTTP 200. 자동 실행기 paused와 service/timer inactive 유지. 기존 미추적 파일과 6개 미완료 워크트리 보존. 원격 push와 실제 주문 없음.
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260914-investor-workflow/HANDOFF.md. 루트 HANDOFF.md에 최신 안내를 추가하고 기존 인계를 보존합니다.

## agent-tooling — 2026-09-13

- 상태: 완료
- 목표와 완료 조건: Serena MCP, Playwright CLI와 Context7 도구를 검증하고, Codex 역할 지정과 압축 보고 및 감독 스킬을 적용합니다. 관련 검사와 독립 검토 후 로컬 main에 통합합니다.
- 담당 Luna: 프로젝트 구현 `/root/project_tooling`, 개인 스킬 `/root/skill_tooling`, 사용자 환경 도구 설치 `/root/install_tools`. 파일 소유 범위를 분리했습니다.
- 워크트리 절대 경로: `/home/kwl/projects/jusik-agent-tooling`
- 작업 브랜치: `feat/agent-tooling`
- 기준 커밋 SHA: `a20e766f7e708574b82a14e55c382382eddfc3d8`.
- 통합 대상 브랜치: `main`
- 입력과 선행 작업: 사용자 승인된 추천 도구와 사용량 감사. 자동 runner와 timer는 기존 중지 상태를 유지합니다.
- 수정 허용 범위: 프로젝트 `.codex/agents`, 감독 운영 문서와 AGENTS 안내. 검증 helper와 테스트는 개인 `jusik-supervisor` 스킬에 둡니다. 제품·전략·주문·운영 데이터와 runner 실행 코드는 범위 밖입니다.
- 포트·테스트 DB·출력 경로: 전용 임시 fixture와 `~/.local/share/jusik/tooling-audit/20260913-agent-tooling/`. 도구 설치 smoke는 별도 `20260913-tools/`입니다.
- 검증 명령과 결과: 통합 pytest 14개, 탐색 스킬 Node 테스트 4개, Ruff, strict mypy, 스킬 validator 3개, TOML 역할 매핑과 역할별 preflight 4개를 통과했습니다. 실제 Luna/Terra child audit와 Serena·Playwright·Context7 실행 검증도 통과했습니다. `~/.local/share/jusik/tooling-audit/20260913-agent-tooling/integration-checks.json`과 `../20260913-tools/VERIFICATION.md`에 근거를 보존했습니다.
- 결과 커밋 SHA와 검토 결과: `77aae489da4d895e048592603aeef3a5de0ccbcf`까지 프로젝트 문서를 반영했습니다. 독립 review에서 로그 검증의 정상 세션 거부·근거 없는 turn 허용을 수정한 뒤 최종 PASS를 받았습니다. helper는 사전/사후 검사이며 spawn을 가로채는 장치는 아닙니다.
- 병합 직전 main SHA와 통합 검증: `c6397cad504b40a79b1cbc2ac07460b761fae7e1`. 위 통합 검사 모두 통과했습니다. 제품·프런트엔드 변경이 없어 제품 빌드는 적용 대상이 아닙니다.
- 통합 커밋 SHA와 정리 여부: `13dce8ef52adbc5f9b1e1f3ff3f5d8ac13c375fb`. 필요한 스킬 사본·SHA·검증 로그·인계를 보존한 뒤 이번 워크트리와 병합한 로컬 작업 브랜치를 제거했습니다. 기존 연구 워크트리 6개는 보존했습니다.
- handoff 저장 경로와 갱신 여부: `~/.local/share/jusik/tooling-audit/20260913-agent-tooling/HANDOFF.md`에 저장하고 루트 인계에 링크를 추가합니다. 자동 연구는 paused, service와 timer는 inactive로 유지합니다. 사용자 요청에 따라 모든 저장을 마친 뒤 Windows 종료 명령을 수행합니다.

기준 저장소에서 Astra만 갱신합니다. 작업 배정 시 [운영 절차의 기록 양식](worktree-workflow.md#작업-지시와-기록)을 사용하고, 상태가 바뀔 때 실제 Git 상태와 검증 결과를 반영합니다.

## 활성 작업

없습니다. 자동 개발 큐와 실행 중인 작업은 전용 runner DB와 웹 연구 이력에서 확인합니다.

## 완료 작업

### entry-amount-distribution-v1

- 상태: 완료
- 목표와 완료 조건: 기존 32개 결과의 진입 금액 분포 분석을 재사용해 저장소에 통합하고 재현·독립 리뷰·게시·handoff를 완료합니다. 거래 제약은 구현하지 않습니다.
- 담당 Luna: entry_amount (gpt-5.6-luna), 단일 구현 소유자
- 워크트리: /home/kwl/projects/jusik-entry-amount-distribution-v1; 브랜치 feat/entry-amount-distribution-v1
- 기준: a725004; 통합 대상 로컬 main
- 입력과 계획: b73bef5d 시도의 완료된 explore/plan, analysis/analyze.py·test_analyze.py와 독립 계산을 재사용합니다. 새 조사는 현재 코드 호환성에 한정합니다. 고정 원본 32개·manifest를 읽기 전용으로 검증합니다.
- 수정 허용 범위: backend/jusik/research_entry_amount_distribution.py, 대응 테스트, docs/research/entry-amount-distribution-v1.md. 등록부·게시·handoff는 Astra 소유입니다.
- 환경: 워크트리 전용 .venv 및 validation, 서버·DB 없음. 영구 audit entry-amount-distribution-v1-5ed7695c
- 검증: focused pytest, Ruff, strict mypy, 고정 입력 재현 및 기존 독립 수치 대조, 독립 review, main 재실행
- 중단 조건: 입력 해시·회계·수량 불일치. 임계값 선택·추가 전략 실험은 범위 밖입니다.
- 결과 커밋: 6719c36fe61f09dc134f86d90fe31d6c7c81014c. 병합 직전 main a725004, 통합 f8143f9eb103510c9835e0593264d8e42d557c64
- 검토: 독립 review 통과. 재현 명령 줄 연결 수정 후 재검토 완료
- 통합 검증: 관련 pytest 28개(기존 경고 2개), backend 전체 Ruff check/format, strict mypy 75개 소스 통과. 32개 결과·820 BUY, 독립 1,728개 수치 및 기존 기계 산출물 3개 바이트 일치
- 보존: 원본 36개 JSON·기존 backend 모듈 SHA 동일. 실주문·push·PAPER 엔진/DB·GPU 변경 없음
- 웹: entry-amount-distribution-20260912, 5개 문서·API/웹 다운로드 10개 해시 및 제목 확인. 기존 이력 보존. mount root 교체 실패는 파일 단위 게시로 복구
- 환경·결과·handoff를 영구 audit entry-amount-distribution-v1-5ed7695c에 보존하고 archive-manifest.json 해시 대조 후 worktree remove 완료. 브랜치 보존
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/entry-amount-distribution-v1-5ed7695c/handoff.md 및 루트 HANDOFF.md. 통합 검사 실패 없음. UI 변경 없음으로 frontend build 생략


### 2026-09-12 병합 워크트리 정리

- 사용자 지시에 따라 독립 하위 작업은 최대 4명으로 병렬 진행하고, main 병합·통합 검증 후 완료 워크트리를 제거하는 원칙을 운영 문서에 반영했습니다.
- `development-runner`, `entry-attribution`, `experiment-guard`, `unheld-entry-experiment` 4개가 main의 조상이며 미커밋 변경과 사용 중인 프로세스가 없음을 확인했습니다.
- validation 결과 132개 파일을 SHA-256으로 대조해 `20260911T221657Z-worktree-cleanup/`에 보관했습니다. 각 환경의 패키지 버전도 보관했습니다.
- `git worktree remove`로 4개 폴더와 내부 가상환경·캐시를 제거했습니다. 강제 옵션은 사용하지 않았으며 커밋과 브랜치 이력은 유지했습니다.
- 아래 완료 항목의 워크트리 보존 기록은 당시 상태입니다. 현재 재현 자료의 위치는 위 cleanup audit과 기존 연구 audit입니다.
- 설정 갱신 중 자동 실행기를 일시 중지했으며, 진행 중이던 진입 금액 분석은 이전 시도 기록과 함께 재시도하도록 복구합니다. PAPER와 GPU 서비스는 변경하지 않습니다.

### development-runner

- 상태: 완료
- 목표: 영속 연구 큐를 Codex supervisor에 전달하는 자동 실행기를 설치하고 반복 실행·중단·웹 이력을 검증합니다.
- 담당 Luna: `/root/work_attribution` (새 작업으로 재배정)
- 워크트리: `/home/kwl/projects/jusik-development-runner`, `feat/development-runner`, 기준 `cb075f2b09d2dbbfa55c5c58ba2dfca6dcb72313`
- 결과 커밋: `406a897`, 수정 `312761f`, 최종 `fd2df78`. append-only 이력
- 병합 직전 main: `2c9a7ef`; 로컬 통합: `a49b30a`
- 범위: 신규 runner/store/테스트, systemd service/timer, 운영 문서와 README 안내. 감독이 AGENTS 운영 안내를 추가했습니다.
- 검증: 신규 13개 테스트, 독립 리뷰 통과. main 전체 pytest 523개(기존 경고 2개), Ruff 116개 파일, strict mypy 74개 소스 통과. UI 변경이 없어 frontend build는 미실행
- 실제 검증: Codex Astra 호출·Luna 위임·완료 schema 호환성, 가짜 작업의 systemd 단독 2회 및 타이머 자동 2회, 시작/완료 이력 전송, SIGTERM interrupted 저장과 자식 종료, 분리된 자식의 cgroup timeout 종료를 확인했습니다.
- 설정: 작업당 90분, UTC 하루 8회 시작, 종료 뒤 약 2분 간격. 금액 상한은 아니며 실패/중단 작업은 명시적 retry 전까지 보존합니다.
- 운영 설치: 사용자 `jusik-development-runner.service`와 `.timer`, 별도 상태 DB·비공개 로그, 기존 연구 history journal 연동. 사용자 linger 활성화. 초기 연구 5개 큐와 선행 조건을 등록했습니다.
- 리뷰 수정: 1초 이상 실행의 stdin 재전송 오류, 살아 있는 이전 process group 확인, SIGTERM/SIGINT 중단과 빠른 자식 종료 race를 수정하고 회귀 검증했습니다.
- 완료의 의미: runner는 commit·artifact hash를 확인하며 tests/review 결과는 agent 보고로 구분합니다. 기존 PAPER·GPU·실주문 경로는 변경하지 않습니다. 작업별 자세한 연구 결과는 후속 supervisor가 웹에 게시합니다.
- 증거: `20260911T211748Z-autodev-install/`의 main-pytest.log, timer-fixture-result.json, signal-fixture-result.json, cgroup-smoke-result.json, preservation-latest.json
- 보존·정리: 고정 19개 파일·9개 원장 테이블·GPU 상태 보존 확인. 재현용 워크트리와 독립 `.venv`는 보존하며 임시 검증 unit은 제거했습니다. 운영 unit만 유지합니다.
- handoff: 기준 저장소 `HANDOFF.md` 최신 절 갱신. 원격 push·PR은 이번 범위에서 수행하지 않았습니다.

### entry-attribution

- 상태: 완료
- 목표와 완료 조건: 고정된 미보유 진입 실험 32개의 종목별 회계 손익 및 월별 포트폴리오 손익·거래·비용을 독립 재계산하고 16쌍의 차이를 웹에 공개합니다. 재계산 잔차는 0.000001원 이하여야 합니다.
- 담당 Luna: `/root/work_attribution`
- 워크트리 절대 경로: `/home/kwl/projects/jusik-entry-attribution`
- 작업 브랜치: `feat/entry-attribution`
- 기준 커밋: `ff607a7`
- 통합 대상: 로컬 `main`
- 입력과 선행 작업: 이전 32회 `unheld-entry-real32`의 고정 results/preregistration SHA 및 개별 artifact SHA. explore와 plan 완료
- 수정 허용 범위: 새 `research_entry_attribution.py`, 해당 테스트, `docs/research-entry-attribution.md`만 수정합니다. 전략·엔진·PAPER·API·UI는 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 서버·DB 없음. 전용 `.venv`와 `validation/` 사용, 기존 입력은 읽기 전용
- 검증 방법: 종목·월 합계와 기존 지표의 일치, split 현금정산·비용·UTC 경계·변조·누락·중복·불완전 입력 테스트, 실제 32개/16쌍 분석, 결정성 비교, Ruff·mypy·독립 review·main 통합 검증
- 보존 증거: `20260911T185925Z-entry-attribution/before.json`
- 결과 커밋: `603d50f61182b939c1d23d1083b135748c285d26`
- 병합 직전 main: `ff607a7`; 코드 통합 `e893698`, 최종 코드 상태 `d59a095a1d5d54421868865f0cb09b4321c880ef`
- 이력 보존: 작업자가 최초 리뷰 커밋 `6040b37`을 amend한 사실을 확인했습니다. 감독은 최종 검토 트리를 유지하면서 최초 스냅샷도 추가 병합의 조상으로 보존했고 이후 수정은 새 커밋으로 남기도록 재지시했습니다. 최종 트리는 검토한 `603d50f`와 동일합니다.
- 검증 결과: 신규 12개·관련 41개 테스트, 독립 리뷰 통과. main 전체 pytest 510개(기존 경고 2개), Ruff check/format 112개 파일, mypy 72개 소스 통과. UI 미변경으로 빌드는 미실행
- 실제 결과: 32개 artifact / 16쌍 / 종목 222행 / 월 126행. 별도 계산과 손익 값 1,044개가 정확히 일치하고 최대 회계 잔차는 `2.4375E-31 KRW`. 전용 두 실행 및 main 재실행의 산출물 4개가 동일
- 해석: 체결 금액에는 슬리피지가 반영돼 있으므로 수수료와 FX 비용만 현금흐름에서 차감합니다. 내재 슬리피지는 별도 표시합니다. 회계 귀속을 추가 매매의 인과적 이익이나 MDD 원인으로 해석하지 않습니다.
- 웹: `/research/history`의 `entry-attribution-20260912`. 판단·상세 보고서·종목/월 전체 CSV·검증 보고서 5개, API/웹 다운로드 10개 SHA와 화면 제목 확인. 이전 51개 이력과 78개 artifact 보존
- 보존: 고정 파일 19개·원장 9개 테이블·계약 mtime·GPU 프로세스 상태 일치. 운영 전략과 PAPER 계약 미변경
- 산출물·정리: 워크트리 `validation/real-run-13`, `real-run-14` 및 영구 audit `20260911T185925Z-entry-attribution/verified-analysis`, `main-analysis`. 독립 환경과 재현 자료를 위해 워크트리를 보존하며 미커밋 소스·작업 서버는 없음
- handoff: 기준 저장소 `HANDOFF.md` 최신 기여 분석 절 갱신. 이번 범위에서 원격 push·PR은 수행하지 않음

## 이전 완료 작업

## experiment-guard

- 상태: 완료
- 목표와 완료 조건: 실험 엔진의 허용된 단일 변경과 대조군 전체 JSON 일치를 검증하는 읽기 전용 helper를 구현하고 독립 검토 및 main 통합 검증을 통과합니다.
- 담당 Luna: `/root/work_guard`
- 워크트리 절대 경로: `/home/kwl/projects/jusik-experiment-guard`
- 작업 브랜치: `feat/experiment-guard`
- 기준 커밋 SHA: `e663641`
- 통합 대상 브랜치: 로컬 `main`
- 입력과 선행 작업: `20260911T060908Z-rebalance-band/next-hypothesis.md`, 조사 및 계획 완료
- 수정 허용 범위: `backend/jusik/research_experiment_guard.py`, 해당 테스트, `docs/research-experiment-guard.md`
- 포트·테스트 DB·출력 경로: 서버와 DB 없음. 전용 워크트리 `.venv` 및 pytest 임시 경로 사용
- 검증 명령과 결과: focused pytest 9개, Ruff check/format, mypy 통과. 독립 review의 두 P2 수정 후 재검토 통과. main 병합 후 같은 검사 통과
- 보존 기준: 운영 엔진·원장·평가 계약·GPU 서비스 미변경. 시작 증거는 `20260911T132132Z-worktree-development/before.json`
- 결과 커밋 SHA: `41e3bbbac8f573a840d53d366cdef543af277792`
- 병합 직전 main SHA: `e663641`
- 통합 커밋 SHA: `8e421e55f2648455f6325b87738c48e12ceb0b79`
- 통합 보존 검사: 고정 파일 19개, 원장 9개 테이블, 계약 mtime, GPU PID·재시작 상태 일치
- 워크트리: 후속 검토에서 독립 가상환경과 구현 이력을 재현하기 위해 보존. 미커밋 소스와 작업 서버 없음
- handoff: 기준 저장소 `HANDOFF.md`의 워크트리 개발 절

## unheld-entry-experiment

- 상태: 완료
- 담당 Luna: `/root/work_unheld`
- 워크트리 절대 경로: `/home/kwl/projects/jusik-unheld-entry-experiment`
- 작업 브랜치: `feat/unheld-entry-experiment`
- 기준 커밋: `ad06daa`
- 통합 대상: 로컬 `main`
- 목표와 완료 조건: 미보유 진입만 2%p 밴드 예외로 처리한 격리 엔진을 32회 비교하고 대조군 16개 전체 결과 일치, 경계 fixture 및 웹 보고서를 검증합니다.
- 입력과 선행 작업: experiment-guard의 첫 운영 검증과 통합 완료. 이전 rebalance-band audit의 고정 입력·대조군·사전 판정식 사용
- 수정 허용 범위: 새 실험 runner, 테스트, 별도 문서와 격리 산출물. 운영 엔진·기존 모델·PAPER 경로는 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 서버·DB 없음. 전용 `.venv` 및 워크트리 `validation/`, 공유 입력은 읽기 전용
- 검증: 행동·지표 fixture, 32회 비교, 대조군 16개 전체 일치, Ruff·mypy·독립 review·main 통합 검사, 웹 history 산출물 해시 확인
- 종료 조건: 결과를 성공 여부와 무관하게 공개하고 등록부·handoff와 운영 보존 증거를 갱신합니다.
- 결과 커밋: `eb9c0eed84b3657eb1a79af62b5d134457139205`
- 병합 직전 main: `ad06daa`
- 통합 커밋: `78045f84027243390728ef8c796a31f480d43e2b`
- 검증 결과: 신규 10개·기존 포트폴리오 19개 테스트 통과, 독립 리뷰 수정 및 재검토 통과. main 전체 pytest 498개(기존 경고 2개), Ruff check/format 110개 파일, mypy 71개 소스 통과. UI 미변경으로 프런트엔드 빌드는 미실행
- 실험 결과: 32/32 완료, 대조군 16개 전체 JSON 일치. 비용 1배 연속 수익률 16.3268% / 27.8639%, MDD 7.3744% / 7.2249%(대조군 / 변형군). 체결 171 / 308건이며 첫 fold 악화도 공개. 두 비용 조건의 사전 관심 기준 충족은 후향 연구 결과이고 PAPER 승격이 아님
- 웹: `/research/history`의 `unheld-entry-20260911`. 요약·전체 수치·16쌍 비교·검증 보고서 4개를 게시하고 API/웹 다운로드 8개 해시 및 화면 제목 확인. 첫 작업 이력과 모든 이전 이력 보존
- 보존 검증: 고정 파일 19개·원장 9개 테이블·계약 mtime·GPU 서비스 상태 일치. 통합 코드와 실험 runner/helper hash 일치
- 산출물: 워크트리 `validation/real32` 및 영구 audit `20260911T132132Z-worktree-development/unheld-entry-real32`. 최초 `/tmp/jusik-unheld-real32`도 삭제하지 않음
- 워크트리: 독립 가상환경과 실험 재현 자료를 위해 보존. 미커밋 소스와 작업 서버 없음. 원격 push·PR은 이번 범위에서 수행하지 않음
- handoff: 기준 저장소 `HANDOFF.md`의 워크트리 개발 절 갱신

## 첫 운영 검증

`experiment-guard`에서 완료했습니다. 운영 문서와 등록부를 기준 커밋에 포함했고, Luna가 전용 폴더·브랜치·가상환경에서 구현했습니다. 독립 검토, Astra의 로컬 main 병합, 통합 검사와 운영 상태 보존 검사를 통과했으며 handoff를 기록했습니다. 서버·DB·포트는 사용하지 않았습니다.

## runner-git-access

- 상태: 완료
- 목표와 완료 조건: 자동 실행기의 Git 메타데이터 쓰기를 명시적으로 허용하고 실제 Codex의 워크트리 생성·커밋·main 병합·정리 및 보호 경로 차단을 검증한 뒤 기존 작업을 재개합니다.
- 담당 Luna: 별도 Codex CLI `gpt-5.6-luna` (내장 agent의 세션 한도로 대체)
- 워크트리 절대 경로: `/home/kwl/projects/jusik-runner-git-access`
- 작업 브랜치: `fix/runner-git-access`
- 기준 커밋 SHA: `8268a2d`
- 통합 대상 브랜치: 로컬 `main`
- 입력과 선행 작업: 조사·계획 완료. 실제 Codex named permissions profile 쓰기 시험 통과
- 수정 허용 범위: development_runner.py, 관련 테스트, docs/development-runner.md
- 포트·테스트 DB·출력 경로: 전용 venv와 validation. 운영 runner는 pause 상태. 영구 audit `20260911T234908Z-runner-git-access/`
- 검증 명령과 결과: runner 22개, main 전체 pytest 532개(기존 경고 2개), Ruff check/format 115개 파일, strict mypy 74개 소스 통과. 실제 Codex exec 및 통합 helper 설정의 Git lifecycle·보호 경로·artifact 쓰기 검증 통과
- 검토 결과와 남은 문제: 독립 검토의 artifact 경로·기존 권한·테스트 격리 지적 수정 후 재검토 통과. 사용자 설정·quota·기존 산출물·PAPER·GPU 보존. 전용 환경의 선택 PyTorch 미설치로 최초 전체 검사 12개 실패, 최종 main 전체 검사 통과
- 결과 커밋 SHA: `9e0fcb1`, `21a9856`, `f6ba0aa`
- 병합 직전 main SHA: `e054390`
- 통합 커밋 SHA와 정리 여부: `58f5443a8f43428a717b707bb80cbb667db44706`. 검증 로그·환경 버전 보존 및 해시 확인 후 워크트리 제거 완료. 브랜치 보존
- 웹: `/research/history`의 `runner-git-access-20260912`. 기존 seed 52개·artifact 83개 보존, API/웹 다운로드 SHA와 제목 확인
- handoff 저장 경로와 갱신 여부: 기준 저장소 HANDOFF.md 복구 절과 영구 audit activation.json에서 재개 상태 확인


## future-observation-protocol-v1-63c4

- 상태: 완료
- 목표와 완료 조건: 후향 자료와 분리된 미래 관측 설계를 문서화하고 미확보 자료를 구분합니다. 독립 검토, 로컬 main 통합, 검사와 영구 handoff를 완료합니다.
- 담당 Luna: /root/protocol_luna (gpt-5.6-luna)
- 워크트리 절대 경로: /home/kwl/projects/jusik-future-observation-63c4
- 작업 브랜치: docs/future-observation-63c4
- 기준 커밋 SHA: a6863b756e24e0d3549b46f0453583e60070a5d0
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore·plan 완료, 이전 시도 protocol-draft.md 및 현재 prospective/boundary 코드
- 수정 허용 범위: docs/research-future-observation-protocol.md, docs/research.md의 링크
- 포트·테스트 DB·출력 경로: 서버·운영 DB 사용 없음. 검사는 격리 임시 경로 사용
- 검증 명령과 결과: main 문서 링크·계약 일치·git diff --check·변경 범위·보존 해시 통과. prospective/boundary pytest 40개 통과(기존 경고 2개), Ruff check/format 8개 파일, strict mypy 4개 소스 통과. 문서 변경으로 frontend build 비적용
- 결과 커밋 SHA: d80abd9c8d8bdc0bfb1733891967f5675d18432b
- 검토 결과와 남은 문제: 독립 review 초기 지적 수정 후 최종 통과. 미래 관측·운영 등록·성과 검증은 완료되지 않았으며 설계 범위 밖
- 병합 직전 main SHA: a6863b756e24e0d3549b46f0453583e60070a5d0
- 통합 커밋 SHA와 정리 여부: 69894b0e89b227ae24aa1a15fb0b30c234d7f514. 영구 audit에 증거 16개·SHA-256·handoff 보존 및 해시 확인 후 clean 워크트리 제거 완료. 브랜치 보존
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/future-observation-protocol-v1-63c4e3f2380b4e149d60d17db90459c7/handoff.md 저장 완료
- 웹: runner completion/outbox를 통한 상태 기록 대상. 직접 게시·history 변경은 하지 않았습니다. 기존 미추적 HANDOFF.md를 보존했습니다.


## paper-signal-evidence-v1-722b

- 상태: 완료
- 목표와 완료 조건: 저장된 실시간 PAPER 시세 근거를 읽기 전용 수집하고 출처·제한을 문서화합니다. 독립 검토, main 통합, 검사, 영구 근거와 handoff 보존을 완료합니다.
- 담당 Luna: paper_luna (gpt-5.6-luna), 문서 단일 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-paper-signal-722b
- 작업 브랜치: docs/paper-signal-722b
- 기준 커밋 SHA: 0676b70 (작업 등록 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore·plan 순차 완료. 이전 시도 collector와 기존 research_signal_validation 재사용
- 수정 허용 범위: docs/research/paper-signal-evidence-v1.md (Luna); 등록부·영구 audit 수집·검증·handoff (Astra)
- 포트·테스트 DB·출력 경로: 서버 없음. 테스트는 임시 DB, 수집은 audit/private 복사본만 사용
- 영구 산출물: /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-evidence-v1-722bb6f1d10a42318b502092d64dac39
- 검증 계획: snapshot integrity와 재분석 일치, validation/kis_stream pytest, Ruff check/format, strict mypy, 문서 독립 review와 main 통합 재검사
- 중단 조건: 원본 수집 중 변경·무결성 실패·해시 불일치. 운영 DB·engine·broker·주문·GPU·remote 변경 금지

- 결과 커밋 SHA: 4f0542f (Luna)
- 병합 직전 main SHA: 0676b70
- 통합 커밋 SHA: e9d7b5da40218a36a84fd6e7552cfc88f7dc7c1a
- 검토 결과: 독립 snapshot 재분석·별도 집계 일치. 문서 경로·환경 설명 수정 후 독립 검토 통과
- 검증 결과: 통합 전후 pytest 29개 통과(기존 경고 2개), Ruff check/format 4파일, strict mypy 2소스 통과. 문서 hash 일치·diff check·baseline 보존 확인. frontend build 해당 없음
- 관측 결과: 저장 관찰 21,937건, 판단·체결 0건. 선택일 2026-09-11의 6,240분 중 6,164분 관측, 미래 시각 이상 249건. current_feed=null, operational_unproven 유지
- 정리: 필요한 근거 99파일과 SHA-256·handoff를 영구 audit에 먼저 보존·검증했다. clean worktree 제거 완료, 브랜치 보존. 최종 보존 목록은 manifest.json 참조
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-evidence-v1-722bb6f1d10a42318b502092d64dac39/handoff.md
- 웹: runner completion/outbox의 상태 기록 대상이며 직접 게시하지 않았다. 기존 미추적 HANDOFF.md 보존


## portfolio-stress-e16e

- 상태: 차단 (오프라인 검토·문서 통합 완료, 미래 성과 미확보)
- 목표와 완료 조건: 고정 오프라인 스트레스 재계산과 문서 검토·main 통합·검사·영구 handoff. 미래 성과는 자료 부족으로 차단합니다.
- 담당 Luna: stress_luna (gpt-5.6-luna), 문서 단일 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-stress-e16e
- 작업 브랜치: docs/portfolio-stress-e16e
- 기준 커밋 SHA: 29c5327768e298a284171cce8ec933e1a274ed29 (등록 준비 전 main; 실제 기준은 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore 조사와 bounded plan 완료. 기존 고정 baseline과 robustness CLI
- 수정 허용 범위: docs/research/portfolio-stress-robustness-v1.md (Luna); 등록부·audit·검사 (Astra)
- 포트·테스트 DB·출력 경로: 서버 없음, 테스트는 임시 DB. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-stress-robustness-v1-e16e783562a544cf8fdef38180db34b0
- 검증 계획: 고정 SHA, 7 folds/147회 평가, 시간 분리, 관련 pytest·Ruff·strict mypy·독립 review
- 중단 조건: 고정 입력 hash 불일치 또는 계산 실패. 엔진·PAPER·주문·remote·GPU 변경 금지

- 결과 커밋 SHA: c52b08d65aa4fda62793b23da3f64f4300c2419e
- 병합 직전 main SHA: a7e18e71d5cd305d0c73e93d978e6c6772dd3834
- 통합 커밋 SHA: a63ef98b8fd46d09a3a5f3e13dc29db0a3fff54c
- 검토 결과: 독립 검토 통과. source/code/spec/산출물 해시, 9개 요약 수치, fold 시간 분리, 이전 결과 일치 검증. 재현 경로와 미래 평가 표현 수정
- 검증 결과: 통합 전후 pytest 31개 통과(기존 경고 2개), Ruff check/format 및 strict mypy 통과. diff check·문서 hash·기존 HANDOFF와 엔진 보존 확인. frontend build 비적용
- 연구 결과: 7/7 folds, 147회 평가, 774 union dates. 생성 시각 외 이전 결과 일치. 2026-09-12 기준 미래 평가 기간이 아직 시작되지 않아 성과 검증 차단
- 정리: 필요한 근거·SHA-256·handoff 26파일을 영구 audit에 보존하고 검증한 후 clean merged worktree 제거 완료. 브랜치 보존
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-stress-robustness-v1-e16e783562a544cf8fdef38180db34b0/handoff.md
- 웹: runner completion/outbox 상태 기록 대상. 직접 게시·PAPER DB 변경 없음. 기존 미추적 HANDOFF.md 보존


## paper-signal-timestamp-forensics-a77e

- 상태: 완료
- 목표와 완료 조건: 동결 snapshot의 6,164개 정규장 표본과 미래 시각 이상 249건을 재현하는 오프라인 CLI, 전체 anomaly CSV, 그룹별 요약, 경계 테스트와 한국어 문서를 구현합니다. 독립 검토, local main 통합 검사, 웹 보고서와 영구 근거 보존 후 종료합니다.
- 담당 Luna: timestamp_luna (gpt-5.6-luna), 신규 모듈·테스트·문서 단일 구현 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-signal-timestamp-a77e
- 작업 브랜치: feat/signal-timestamp-a77e
- 기준 커밋 SHA: fa127374e6e3ee351fedb514ffb0db1769615437 (등록 전 main; 실제 worktree 기준은 이 등록의 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore 독립 재계산 완료, plan 순차 검토. paper-signal-evidence-v1-722bb6f1d10a42318b502092d64dac39의 snapshot/provenance/validation만 읽기 전용 입력으로 사용합니다.
- 수정 허용 범위: backend/jusik/research_signal_timestamp_forensics.py, backend/tests/test_research_signal_timestamp_forensics.py, docs/research/paper-signal-timestamp-forensics-v1.md (Luna); 등록부·audit·웹 seed·handoff (Astra)
- 포트·테스트 DB·출력 경로: 신규 서버 없음. worktree 내부 .venv와 .artifacts, pytest tmp 경로를 격리합니다. 운영 DB에 연결하지 않습니다.
- 영구 산출물: /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-timestamp-forensics-v1-a77ec18fbf634b3694afa8da08ef11c6
- 검증 명령과 결과: 새 pytest 및 research_validation 회귀, Ruff check/format, strict mypy, 두 번 frozen replay의 바이트 일치와 입력 SHA 보존, 독립 review, main 통합 후 동일 검사 예정
- 중단 조건: 입력 hash 불일치 또는 구현 범위 밖 변경 필요. 미래 데이터는 본 오프라인 도구 완료의 조건이 아닙니다. PAPER·collector·order·parser·clockmonitor·GPU·runner·quota·remote를 변경하지 않습니다.
- 결과 커밋 SHA: 92527281cdadd5101478987d233db5b5931ec909, ab56a15d80bdc02772a13460c2d1c0588ac99e26
- 병합 직전 main SHA: a6610f047b0c460a61cef0cd7cee9794dd4013f6
- 통합 커밋 SHA: 3f1a0f59edc9643210647e14fc6090918a1bfded
- 검토 결과: Terra 독립 검토 통과. 정확한 -2s-1µs fixture와 URI 인코딩 지적을 회귀 테스트와 함께 수정했습니다.
- 통합 검증 결과: pytest 20개(기존 Starlette/AnyIO 경고 2개), Ruff check/format, 프로젝트 설정 strict mypy 2파일, git diff 검사 통과. 두 main 재생 3출력 바이트 일치, 249개 ID/시각/정확한 지연 및 전 종목 latency/coverage와 독립 집계 일치. frontend build 비적용.
- 결과: 6,164개 정규장 저장 분 표본, future 249건, stale 0건, median -130ms/p95 668ms/max 4939ms. 원 snapshot 및 기존 소스·HANDOFF 해시를 유지했습니다. 원인은 확정하지 않았습니다.
- 웹: /research/history에 한국어 보고서·checks 게시 완료. API/웹 4개 첨부 다운로드 SHA와 페이지 제목 확인. 기존 seed의 54개 이력·89개 첨부를 보존했습니다.
- 정리: evidence·SHA-256·환경·handoff 등 105개 파일을 영구 audit에 보존·검증한 뒤 생성물을 정리하고 git worktree remove로 병합 worktree 제거 완료. 브랜치 보존.
- 통합 검증 실패 원인과 복구 결과: 통합 검사 실패 없음. 사전 감독 mypy의 잘못된 cwd를 backend로 바꾸어 프로젝트 Pydantic plugin 및 strict 설정 적용 후 통과했습니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-timestamp-forensics-v1-a77ec18fbf634b3694afa8da08ef11c6/handoff.md. 기존 루트 미추적 HANDOFF.md는 그대로 보존했습니다.
- 후속 후보: 독립 근거의 68개 다중 종목 이상 분을 이용한 오프라인 동시 발생/연속 episode 분석 1개. 범위·입력·테스트·종료 조건은 영구 followup.json에 기록했습니다.


## small-entry-draft-a55b

- 상태: 완료
- 목표와 완료 조건: 신규 소액 진입 사전등록 초안 명세·검증기·테스트를 만들고 독립 검토, local main 통합 검사, 한국어 웹 게시와 영구 근거 보존을 완료합니다. 금융 승인이나 정책 실행은 포함하지 않습니다.
- 담당 Luna: draft_luna (gpt-5.6-luna), 신규 세 파일 단일 구현 소유자. 초기 작업자는 파일 수정 전에 중단했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-small-entry-draft-a55b
- 작업 브랜치: feat/small-entry-draft-a55b
- 기준 커밋 SHA: 8882bd8287759edc047adc296da129cded8950dc (등록 전 main; 생성 기준은 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore 완료, 순차 bounded plan. 완료 entry amount 분석과 original unheld-band는 역사 맥락으로만 사용합니다. 과거 blocked 작업은 보존합니다.
- 수정 허용 범위: backend/jusik/research_small_entry_preregistration.py, backend/tests/test_research_small_entry_preregistration.py, docs/research/small-entry-preregistration-draft-v1.md. Astra는 등록부·audit·공개 history·handoff를 담당합니다.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. worktree 내부 .venv, .artifacts, tmp 경로 격리.
- 영구 산출물: /home/kwl/.local/share/jusik/portfolio-audit/small-entry-preregistration-draft-v1-a55b6ee8a036463da688fafe04567542
- 검증 방법: threshold/time/period/hash 경계, canonical roundtrip와 별도 identity, populated draft 불변성, pytest·Ruff·strict mypy·독립 review·main 재검사.
- 중단 조건: 세 파일 도구 완료. 임계값 탐색·정책 실행·PAPER 코드/config/DB·collector/order/GPU·runner/quota·remote 변경 금지. 미래 자료 부재는 도구 완료를 막지 않습니다.

- 결과 커밋 SHA: 0f8e1c674bc1535ee80caf500973b143123551e8, 92f3648481a8822a603eedcc82a1213c00d33452
- 병합 직전 main SHA: 03cdafd4b476c55430093d3dad2a6f453e286d80
- 통합 커밋 SHA: 4bd8a85e2d3c482fddaca47a85fe8d64c51d65ad
- 검토 결과: 독립 검토 통과. 추가 금액 계산 helper의 Decimal context 반올림 지적을 helper 제거로 해결하고 위조 상태·중첩 위험 한도의 출력 거부 회귀를 추가했습니다.
- 통합 검증 결과: 신규19개 및 기존 금액 분석6개 pytest 합계25개, Ruff check/format, 설정된 strict mypy 신규 소스·테스트2파일, diff 검사 통과. 기본·합성 완전 입력 반복 canonical 출력/roundtrip/낮은 Decimal context 바이트와 SHA 일치.
- 검사 제한: 전체 backend mypy의 torch 타입 정보 누락·기존 테스트 모듈 중복2오류를 변경 전 main에서도 재현했습니다. frontend build 비적용. 엔진·실험 정책 실행 테스트는 범위에서 제외했습니다.
- 결과: 기본4개 결정은 null, 모든 입력이 있어도 draft 및 활성화 금지. canonical draft SHA 71691f864ccc0e61e351b52298027e6df4e8c864ab9c15f16ae0887bbfe35dbb. PAPER10% 계약과 기존 코드/config/HANDOFF·역사 입력 SHA 보존.
- 웹: /research/history 한국어 보고서·검사 요약 게시 완료. API/웹 제목과4개 첨부 다운로드 SHA 및 기존 seed 이력 보존 확인.
- 정리: 근거62파일·환경·SHA·handoff를 영구 audit에 먼저 보존·검증한 뒤 작업 생성물과 병합 worktree를 git worktree remove로 제거했습니다. 브랜치는 보존했습니다. 최종 manifest.json에 정리 후 추가 기록까지 포함합니다.
- 통합 검증 실패 원인과 복구 결과: 통합 검사 실패 없음.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/small-entry-preregistration-draft-v1-a55b6ee8a036463da688fafe04567542/handoff.md. 기존 root HANDOFF.md 보존.
- 후속 후보: 초안의 선언 SHA와 실제 보관 출처를 검증하는 신규 오프라인 provenance bundle verifier1개. exact scope/input/tests/stop은 영구 followup.json 참조. 미래 자료·금융 승인 불필요.


## future-observation-replay-0bb3

- 상태: 완료
- 목표와 완료 조건: 합성 fixture 전용 순수 관측 분류기와 오프라인 CLI를 구현하고 독립 기대값·pytest·검토·main 통합·웹 보고 및 영구 증거 보존을 완료합니다.
- 담당 Luna: replay_luna (gpt-5.6-luna), 신규 세 파일 단일 구현 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-future-observation-replay-0bb3
- 작업 브랜치: feat/future-observation-replay-0bb3
- 기준 커밋 SHA: de52818e3ec249ef1bd9e42e80ad2304befa1eb1 (등록 전 main; 생성 기준은 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 기존 미래 관측 초안, readiness/receipt seam 읽기 전용 조사 완료. 순차 bounded plan과 독립 합성 기대값을 사용합니다.
- 수정 허용 범위: backend/jusik/research_future_observation_replay.py, backend/tests/test_research_future_observation_replay.py, docs/research/future-observation-protocol-replay-v1.md. Astra는 등록부·audit·공개 history·handoff 담당.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. worktree 내부 .venv, .artifacts, tmp와 cache 격리.
- 영구 산출물: /home/kwl/.local/share/jusik/portfolio-audit/future-observation-protocol-replay-v1-0bb3f02db53540c9b6da3e631c76aa9b
- 검증 방법: UTC 반열린 구간, 최초 receipt 불변, 중복·충돌·late, not_due/missing, clock/truncation, 미정 우선순위 보존, 고정 synthetic 불변성. pytest·Ruff·strict mypy·독립 review와 main 재검사.
- 중단 조건: 결정론적 합성 replay 도구까지. 미래 데이터 부재는 blocker가 아닙니다. PAPER 코드/config/contracts/DB·collector·order·GPU·runner/quota·remote 변경 금지.

- 구현 커밋: af61404, 23a425b, 8ad7113, 0bcf2cc, 420d04a, 2f5fecc. 독립 검토에서 미래 receipt 소급·시계 오류 건수·CLI alias 회귀를 발견해 동일 Luna가 수정했습니다.
- 감독 독립 검증: 10 receipt/8 identity fixture, 수신 전후 conflict/provenance/clock 3개 비교 통과. 최종 독립 검토와 main 통합 검사 후 완료 처리합니다.

- 최종 구현 커밋: 2f5fecc (수정 이력 포함). 독립 최종 검토 PASS, 중요 미해결 지적 없음.
- 병합 직전 main SHA: 6f320bd5e40bef99bb7da03e8996e590239744d6
- 통합 커밋 SHA: d83d47f2d289368f1719aff9ed516143cb35b091
- 통합 검증 결과: pytest 49개(신규20, readiness/receipt29), Ruff check/format, 신규 두 파일 strict mypy, diff 통과. 기존 deprecation 경고2개. frontend build 비적용, 전체 backend 타입 검사 미실행.
- 독립 결과: 10 receipt/8 identity 기대값, 두 CLI 출력 바이트, 미래 conflict/provenance/clock의 수신 전후3쌍 비교 통과. 모든 결과 synthetic, registered/accepted_nav/evaluation_inputs_complete=false.
- 웹: /research/history 한국어 보고서·checks 게시 완료. API·웹 제목과4개 첨부 다운로드 SHA, 기존 공개 seed 보존 확인.
- 보존: 기존 tracked 파일은 등록부 외 모두 동일하며 기존 미추적 HANDOFF.md 보존. 비ASCII 경로2개는 원래 기준 커밋 bytes와 추가 비교. 운영 DB·PAPER·collector·order·GPU·runner/quota·remote 변경 없음.
- 정리: 증거·SHA·환경·handoff82파일을 영구 audit에 보관·검증한 뒤 생성물을 제거하고 git worktree remove로 병합 worktree 정리 완료. 브랜치 보존.
- 통합 검증 실패 원인과 복구 결과: 코드 통합 검사 실패 없음. 감독 보존 검사에서 Git 경로 인용으로 비ASCII2파일이 새 파일로 오인되어 -z 경로 읽기와 기준 blob 비교로 검사 도구를 수정하고 통과했습니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/future-observation-protocol-replay-v1-0bb3f02db53540c9b6da3e631c76aa9b/handoff.md
- 후속 후보: 합성 revision-link 구조 감사1개. 프로토콜의 이전 revision·effective 시각 연결 규칙과 현재 replay의 충돌 보존 범위를 근거로 합니다. 범위·입력·테스트·종료 조건은 영구 followup.json에 기록했습니다.

## runner-daily-limit

- 상태: 완료
- 목표와 완료 조건: 기존 실행 이력을 보존하며 일일 설정 상한을 24회까지 지원하고 설치 설정을 24회로 조정해 대기 연구를 재개합니다.
- 담당 Luna: 별도 Codex CLI gpt-5.6-luna
- 워크트리 절대 경로: /home/kwl/projects/jusik-runner-daily-limit
- 작업 브랜치: fix/runner-daily-limit
- 기준 커밋 SHA: 8d9333f
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: UTC 실행 8회/설정8로 quota 대기 확인; 후속3개 queued, timer 정상
- 수정 허용 범위: development_runner.py, 해당 tests, docs/development-runner.md
- 포트·테스트 DB·출력 경로: 전용 venv/임시DB, 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260912T061307Z-runner-daily-limit
- 검증 명령과 결과: worker/main focused pytest 28개, Ruff check/format, strict mypy 통과. 독립 review P1/P2 없음
- 보존·종료: store/실행이력/90분제한/cooldown/PAPER/GPU 유지, main 검증 후 archive·worktree 정리·handoff·웹 게시
- 결과 커밋: ffdd7e3fb76a4120f5e05a988f0f2083089b7309
- 통합 커밋: ebc42b29c32734e86bbb71cdc0389171ea5166b1
- 정리: 로그·환경·해시 archive 후 worktree 제거, 브랜치 보존
- 설치: daily_launches 8에서24 변경, 나머지 설정과 과거 launch 행 전체 보존
- 재개·웹·handoff: HANDOFF.md 최신 절 및 audit activation.json 참조

## signal-anomaly-episodes-21ce

- 상태: 완료
- 목표와 완료 조건: 동결 신호의 분별 동시 이상/episodes utility, matching pytest, 한국어 보고서; 249 IDs, 68분, 최대5종목, 65 episodes 및 독립 분모/종목쌍 집계 일치
- 담당 Luna: gpt-5.6-luna 단일 구현 작업자; Astra 감독과 별도 독립 검토
- 워크트리 절대 경로: /home/kwl/projects/jusik-signal-anomaly-episodes-21ce (통합 검사 및 증거 보관 후 제거 완료)
- 작업 브랜치: feat/signal-anomaly-episodes-21ce (보존)
- 기준 커밋 SHA 및 병합 직전 main: 1876d8eb11ac7747dba3a08e90eb0a4486d81ac8
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: 지정 evidence/timestamp archive manifest 전체 검증; explore/plan 완료; offline immutable snapshot만 재선택
- 수정 허용 범위와 결과: backend/jusik/research_signal_anomaly_episodes.py, backend/tests/test_research_signal_anomaly_episodes.py, docs/research/paper-signal-coincident-anomaly-episodes-v1.md
- 포트·테스트 DB·출력 경로: 작업 전용 venv/pytest tmp; 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-coincident-anomaly-episodes-v1-21ce4592e34a4ee78332f2dbff95f994
- 검증 명령과 결과: main pytest 44개, Ruff check/format, strict mypy utility/tests, git diff 통과. 780분 grid·770개 관측 분·6,164행·249 IDs·68분·max5·65 episodes, 독립 observed/active 분모·종목 집합·종목쌍·에피소드 및 반복 출력 바이트 일치
- 결과 커밋 SHA: edc09685cbd6640cbddf8d96bc49500d374d9e4d
- 검토 결과와 남은 문제: 초기 분모/session/manifest/output 보호 누락 수정 후 독립 승인; 중요 잔여 문제 없음. 기존 dependency deprecation warning 2건, frontend 변경 없어 build 해당 없음
- 통합 커밋 SHA: b407810d3822db866dc44d4bd061224d68fe48b3
- 정리 여부: source·환경·로그·SHA·handoff 55파일을 durable archive에 검증·보관한 뒤 git worktree remove 완료. 기존 HANDOFF.md 보존
- 통합 검증 실패 원인과 복구 결과: 통합 실패 없음. worker mypy는 처음 root cwd에서 backend 설정 미적용으로 실패했으나 올바른 cwd에서 통과
- 웹 게시: /research/history sanitized 한국어 보고서와 검사 근거, API/web/download 4개 SHA 검증 및 기존 공개 항목 보존
- 보존: 원본 archive와 기존 handoff 213개 hash, 등록부 외 기존 tracked 196개 파일 불변. 운영 PAPER/DB/orders/GPU/runner/quota·remote 변경 없음
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-coincident-anomaly-episodes-v1-21ce4592e34a4ee78332f2dbff95f994/handoff.md

## small-entry-draft-provenance-4840

- 상태: 준비
- 목표와 완료 조건: 오프라인 bundle의 실제 SHA·canonical SHA·별도 identity·역사 재사용 계약 검증, 결정적인 공개 manifest/보고서, 독립 검토·main 검사·연구 이력 게시.
- 담당 Luna: gpt-5.6-luna 단일 구현 작업자
- 워크트리 절대 경로: /home/kwl/projects/jusik-small-entry-draft-provenance-4840
- 작업 브랜치: feat/small-entry-draft-provenance-4840
- 기준 커밋 SHA: 7c7bee5591affc5a5d2d9ead53a6f5e8e6a14c48; 작업 등록부 준비 커밋을 실제 작업 기준으로 사용한다.
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: 지정된 small-entry-preregistration-draft-v1 archive의 네 파일 읽기 전용; explore/plan 완료.
- 수정 허용 범위: backend/jusik/research_small_entry_draft_provenance.py, 대응 tests, docs/research/small-entry-draft-provenance-audit-v1.md
- 포트·테스트 DB·출력 경로: 서버·DB 없음. 작업 내부 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/small-entry-draft-provenance-audit-v1-484028675d0647a0a0b47f86c46a5ca5
- 검증 명령과 결과: baseline draft pytest 19개 및 mypy jusik 79개 통과. 신규 경계·회귀·Ruff·mypy와 archive replay를 추가 실행한다.
- 검토 결과와 남은 문제: 구현 후 독립 검토 예정.
- 보존 및 제외: 기존 HANDOFF.md 보존. PAPER/DB/orders/collector/GPU/runner/quota/remote 및 과거 blocked 작업 변경 없음.

## future-observation-revision-9773

- 상태: 완료
- 목표와 완료 조건: 합성 revision-link 구조 감사, 독립 기대값·검토·main 검사·공개 보고·영구 증거 보존.
- 담당 Luna: revision_luna (gpt-5.6-luna), 단일 구현 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-future-observation-revision-9773
- 작업 브랜치: feat/future-observation-revision-9773
- 기준 커밋 SHA: 824f2a357e9b800050138157814f9078525a15f6; 등록 커밋을 생성 기준으로 사용합니다.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: replay·프로토콜 읽기 전용 explore, bounded plan 완료.
- 수정 허용 범위: backend/jusik/research_future_observation_revision_audit.py, backend/tests/test_research_future_observation_revision_audit.py, docs/research/future-observation-revision-link-audit-v1.md
- 포트·테스트 DB·출력 경로: 서버/DB 없음. worktree .venv/tmp/cache 격리. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/future-observation-revision-link-audit-v1-97739cd36077413eab39ecf6961f673c
- 검증 방법: 신규+replay pytest, Ruff check/format, strict mypy, 독립 review, main 재검사.
- 중단 조건: 합성 구조 감사만 수행하며 selection/temporal policy는 미정. PAPER/실주문/DB/collector/GPU/runner/quota/remote 변경 금지.

- 결과 커밋 SHA: b72e91dcd1f29109746fb00afcc01e3a071b6b8d (초기 검토 수정 이력 보존)
- 병합 직전 main SHA: ea76c5646add58ec714698336c408a88d0d9f4e7
- 통합 커밋 SHA: d87174ac722bbd420f0747624afbc92c5810a240
- 검토 결과: 최종 독립 검토 승인. synthetic 강제·다중 부모 SCC·필수 회귀와 한도 검사 지적 해결.
- 통합 검증: 신규+replay pytest 38개, Ruff check/format, strict mypy 두 파일, diff 통과. 감독 독립 10 fixture·raw/availability/CLI bytes, 검토자 512 graph oracle 일치.
- 검사 제한: frontend 변경 없어 build 비적용. 전체 backend 검사 대신 요청된 집중 검사 수행.
- 웹: /research/history 한국어 보고서와 검사 요약, API/web 제목 및 4개 첨부 다운로드 SHA 검증. 기존 공개 항목 보존.
- 정리: 근거·환경·hash·handoff 65파일을 먼저 영구 보관·검증한 뒤 작업 생성물과 병합 worktree 제거. 브랜치 보존. 기존 HANDOFF와 다른 워크트리 보존.
- 통합 검증 실패 원인과 복구 결과: 통합 실패 없음. 작업 환경 초기 Python 경로 문제는 격리된 Python3.13 venv 재생성으로 해결.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/future-observation-revision-link-audit-v1-97739cd36077413eab39ecf6961f673c/handoff.md

## small-entry-draft-provenance-d946

- 상태: 완료
- 목표와 완료 조건: 고정 bundle provenance 검증기, 합성 경계와 보관 입력 검증, 독립 검토, main 통합 검사, 연구 이력 게시와 영구 handoff.
- 담당 Luna: provenance_luna (gpt-5.6-luna), 단일 구현 소유자.
- 워크트리 절대 경로: /home/kwl/projects/jusik-small-entry-draft-provenance-d946
- 작업 브랜치: feat/small-entry-draft-provenance-d946
- 기준 커밋 SHA: 2ee7b0a; 등록 커밋을 실제 생성 기준으로 사용합니다.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore/plan 완료. 지정 archive 네 파일 읽기 전용. 이전 미통합 커밋 d499309, ee4a0f8의 세 파일만 재사용하며 이전 워크트리는 보존합니다.
- 수정 허용 범위: backend/jusik/research_small_entry_draft_provenance.py, 대응 tests, docs/research/small-entry-draft-provenance-audit-v1.md
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 작업별 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/small-entry-draft-provenance-audit-v1-d946e107ca2a46e0a88ea65391331b60
- 검증 방법: 신규+draft+분포 pytest, Ruff check/format, strict mypy, 보관 네 파일 전후 SHA 및 반복 출력 일치, 독립 review, main 재검사, 웹/API 다운로드 SHA 확인.
- 제외: 미래 자료·임계값·정책·PAPER/운영 DB·collector/order/GPU·runner/quota·remote push 변경 및 과거 blocked 큐 재시도 없음.

- 결과 커밋 SHA: f512484d6cf2f06b65d0cf25e7b36de78e83c2e8 (선행 1d5c2dc)
- 검토 결과: 독립 review 통과, 중요 지적 없음. 별도 pytest 41개와 네 파일 변조/symlink probe 통과.
- 병합 직전 main SHA: 35af566e70927fe1f907611b77d888efd674dc88
- 통합 커밋 SHA: a2da7de8848c57a0408e7e9f1515a8078cb4baa0
- 통합 검증: 관련 pytest 47개, Ruff check/format, strict mypy 82개 소스, diff 통과. 원본 네 파일 SHA·반복/relocation 출력 일치. 기존 backend/frontend/deploy 118개 파일 보존. UI 미변경으로 build 생략.
- 게시: /research/history 보고서·공개 manifest·검사 3개 artifact, API/웹 제목 및 다운로드 6건 SHA 검증 완료. 기존 history seed 보존.
- 정리: 증거·환경·SHA·handoff 54개 파일을 영구 audit에 보관/대조한 뒤 이번 워크트리만 제거. 이전 4840 워크트리와 브랜치는 기존 상태·소유권 보존을 위해 유지.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/small-entry-draft-provenance-audit-v1-d946e107ca2a46e0a88ea65391331b60/handoff-final.md. 기존 root HANDOFF 내용 보존 후 이번 기록 추가.
- 통합 검증 실패: 없음. 남은 작업 없음.

## portfolio-symbol-removal-15a6

- 상태: 완료
- 목표와 완료 조건: 고정 32개 simulation의 모든 종목 기여분 차감 산술 민감도, 부호 반전 식별, 독립 검토, main 통합 검사, 한국어 연구 이력 게시와 영구 증거 보존.
- 담당 Luna: gpt-5.6-luna 단일 구현 소유자.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-symbol-removal-15a6
- 작업 브랜치: feat/portfolio-symbol-removal-15a6
- 기준 커밋 SHA: da76dd015cf583f73ee3acb4dd525748934dc74a. 등록 커밋을 실제 생성 기준으로 사용합니다.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 지정 unheld-entry-real32 및 verified-analysis/attribution.json 읽기 전용; explore 후 bounded plan.
- 수정 허용 범위: backend/jusik/research_portfolio_concentration.py, 대응 tests, docs/research/portfolio-symbol-removal-attribution-v1.md
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 작업별 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-symbol-removal-attribution-v1-15a65c0ea4694f0da1b0c8affd420f65
- 검증 방법: 합성 경계 및 기존 attribution pytest, Ruff check/format, strict mypy, 고정 입력 반복 출력·SHA 대사, 독립 review, main 재검사, 웹/API 다운로드 SHA.
- 제외: 재배분·재시뮬레이션·미래 자료·정책 활성화·PAPER/운영 DB·collector/order/GPU·runner·remote push 변경 없음. PAPER 10% 유지.
- 종료 조건: auditable 결과와 구현 workflow 완료. followup=null, 대기 중 portfolio-next-development-selection-v1이 두 분석을 통합합니다.

- 결과 커밋 SHA: 0b62dc1b9842e47fa196a9074e743f523d0511ab (선행 7029a56, ffd9449 수정 이력 보존).
- 병합 직전 main SHA: 66361d85edfc89a363c0eedaf7f08722e1e2c84e
- 통합 커밋 SHA: 6bf9910ccadf4abd4cc5b1c22ba50b46f73e10f4
- 검토 결과: 독립 review 승인. 초기 SHA 재읽기·회귀 테스트·formula 비교·문서 hash 지적을 해결했고 production 9개 및 synthetic fault 8개 probe 통과.
- 통합 검증: pytest 42개, Ruff check/format, strict mypy 83개 소스, diff check 통과. 동결 입력 256행과 독립 계산의 1,536개 금액·비율, 부호 반전 표시 일치. JSON/CSV/report 반복 byte 동일.
- 검사 제한 및 복구: 격리 venv 전체 mypy는 기존 optimizer의 torch 미설치로 실패했으나 신규 모듈·테스트 strict 통과, GPU 설치 없이 main 기존 환경 전체 검사 통과. 기존 deprecation 경고 2개. UI 미변경으로 frontend build 비적용. 통합 검사 실패 없음.
- 결과: fold_1 c1 000660·AMD·COHR·SOXL, c2 000660·COHR·SOXL에서만 strict flip 7건. fold_2~7 및 continuous 없음. 고정 초기자본 1억 원, 재배분 없는 사후 산술.
- 게시: /research/history 한국어 전체 256행 보고서·manifest·검사 3개 artifact. API/웹 및 6개 다운로드 SHA 검증, 기존 seed 항목 보존.
- 보존·정리: 원본 123개 hash 항목 불변. 증거·환경·소스·hash·handoff 67개 파일 영구 보존 검증 후 git worktree remove로 이번 병합 워크트리 제거. 브랜치, 기존 HANDOFF.md, 이전4840 워크트리 보존.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-symbol-removal-attribution-v1-15a65c0ea4694f0da1b0c8affd420f65/handoff-final.md
- 남은 작업: 없음. followup=null; 대기 중 portfolio-next-development-selection-v1이 두 분석을 통합합니다.

## portfolio-exposure-cost-734e

- 상태: 완료
- 목표와 완료 조건: 동결 32개 시뮬레이션의 노출·실제 비용 비교와 사전 고정 1/2/3배 산술 민감도, 독립 검토, main 통합 검사, 한국어 연구 게시 및 영구 증거 보존.
- 담당 Luna: gpt-5.6-luna 단일 구현 소유자.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-exposure-cost-734e
- 작업 브랜치: feat/portfolio-exposure-cost-734e
- 기준 커밋 SHA: 292f663527e85ec1f1b901fe6039ea5b24ddddac. 등록 커밋을 실제 생성 기준으로 사용합니다.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 지정 unheld-entry-real32 읽기 전용. explore 완료, plan 단계 후 구현. 계산 전에 audit/preregistered-diagnostics.json에 1/2/3배와 초기 1억 원 고정.
- 수정 허용 범위: backend/jusik/research_portfolio_exposure_cost.py, 대응 tests, docs/research/portfolio-exposure-cost-tradeoff-v1.md. 등록부는 감독만 관리합니다.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 독립 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-exposure-cost-tradeoff-v1-734e493df492407891611c190b42a54b
- 검증 방법: 합성 경계·회계 pytest, Ruff check/format, strict mypy, 동결 입력 전후 SHA, 반복 출력, 독립 review, main 검사, 웹/API 및 다운로드 SHA.
- 제외: 운영 엔진/PAPER/설정/DB/collector/order/GPU 변경, 재수집·정책 활성화·remote push 없음. PAPER 10% 유지. 노출 정규화 승자 선정·탐색·가상 MDD/실현 가능성 주장 없음.
- 종료 조건: 통합 검사와 영구 evidence/hash/handoff 보존 후 병합 worktree 정리. followup=null; 대기 중 portfolio-next-development-selection-v1에서 다음 작업 결정.

- 결과 커밋 SHA: 4620a84fb17dcf1b0eba82b05f012a9fde7d5b6e. 구현 커밋과 후속 회귀 보완 이력 보존.
- 병합 직전 main SHA: a543d79235ffb357b4130b6cf0884da18c079c6f. 최초 통합 후 타입 오류 수정 별도 병합.
- 통합 커밋 SHA: 5022efa9a5cb6f25a64890bf149847935b2a48ff
- 독립 검토: 최종 승인. UTC 정렬 미적용, 구현을 호출하지 않는 테스트와 누락 경계, 입력 manifest 재읽기 문제 해결. 필수 11개 테스트 독립 통과.
- 통합 검사: pytest 52개, Ruff check/format, strict mypy 84개 소스, diff 통과. 기존 deprecation 경고 2개, frontend 미변경으로 build 비적용.
- 통합 실패 및 복구: 첫 전체 mypy에서 frozen PortfolioSimulation에 대입하는 불필요한 fallback 실패. 해당 분기를 제거한 별도 커밋을 검토·병합하고 모든 통합 검사 재통과. 실패 로그 보존.
- 계산 근거: 실제 32행, UTC 마지막 일별 노출 4,696행, 실제 c2-c1 16행, 사전 고정 1/2/3배 산술 48행. 독립 원본 계산 5,080개 값 일치, 최종 7개 산출물 반복 byte 동일.
- 게시: /research/history 한국어 전체 행 보고서·manifest·검사 3개 artifact, 웹/API와 다운로드 6개 SHA 검증. 기존 history 항목 보존.
- 보존: frozen 입력과 기존 backend/frontend/deploy SHA 불변. 초기 작업자 amend 발견 후 원래 검토 커밋912160f를 archive/exposure-cost-original-734e와 patch에 보존하고 이후 수정은 별도 커밋으로 진행.
- 정리: 환경·결과·검사·hash·handoff 영구 보관 및 검증 후 git worktree remove로 이번 병합 워크트리만 제거. force 미사용. 작업 브랜치, 기존 HANDOFF와 이전4840 워크트리 보존.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-exposure-cost-tradeoff-v1-734e493df492407891611c190b42a54b/handoff-final.md
- 남은 작업: 없음. followup=null; 대기 중 portfolio-next-development-selection-v1에서 두 분석을 통합 검토합니다.

## portfolio-next-development-selection-bbbd

- 상태: 완료
- 목표와 완료 조건: 완료 증거를 검증한 뒤 corrected-entry 2%p/4%p 보유 밴드 격리 실험 하나를 실행 가능한 후속 과제로 명세하고 한국어 이력에 게시합니다.
- 담당 Luna: `/root/code_selection`
- 워크트리 절대 경로: `/home/kwl/projects/jusik-portfolio-next-selection-bbbd`
- 작업 브랜치: `docs/portfolio-next-selection-bbbd`
- 기준 커밋 SHA: `863d908b3ba34865b9a5deedf786575e62cdf092` (등록부를 포함한 실제 워크트리 기준)
- 통합 대상 브랜치: 로컬 `main`
- 입력과 선행 작업: explore와 순차 plan 완료. 두 선행 completion의 모든 evidence SHA 및 main 조상 관계를 감독이 검증했습니다.
- 수정 허용 범위: `docs/research/portfolio-next-development-selection-v1.md`만 Luna가 수정합니다. 등록부와 영구 증거 및 게시 기록은 감독이 관리합니다.
- 포트·테스트 DB·출력 경로: 서버와 DB 없음. 독립 워크트리; 영구 audit `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-next-development-selection-v1-bbbd21c0082348b09c073c45d73f3e17`.
- 검증 명령과 결과: 기준 관련 pytest 44 passed. 문서 수치·중복 작업·고정 입력 검토 후 관련 pytest/Ruff/strict mypy를 통합 재검증합니다.
- 종료 조건: 독립 review, main 병합/검사, 웹 게시, 영구 SHA/environment/handoff 저장 후 병합 워크트리를 정리합니다. 코드·PAPER·운영 설정·runner·GPU·기존 연구 자료는 수정하지 않습니다.
- 결과 커밋 SHA: `5beebcf92c131bb45051d640b1a59f7847f04cdb`
- 검토 결과와 남은 문제: 독립 `/root/review` 통과. 대조군 경로, 전체 model exact equality, 동일 corrected engine/hash 및 근거 참조를 수정하고 재검토했습니다. 남은 차단 사항 없음.
- 병합 직전 main SHA: `863d908b3ba34865b9a5deedf786575e62cdf092`
- 통합 커밋 SHA와 정리 여부: `ac238c68238f4304380442aee3c9a0e94731fc3e`. 영구 증거와 handoff 및 SHA를 먼저 보존한 후 워크트리와 병합 브랜치를 제거했습니다.
- 통합 검증: 관련 pytest 44 passed(기존 경고 2개), Ruff 8개 source/test 통과, strict mypy 4개 source 통과, git diff --check 통과. 문서만 변경하여 frontend build는 해당하지 않습니다.
- 게시 결과: `/research/history` 항목 `portfolio-next-development-selection-v1-bbbd21c0082348b09c073c45d73f3e17`. API/웹 다운로드 200 및 문서 SHA 일치, 기존 이력 62개·산출물 108개 보존.
- 통합 검증 실패 원인과 복구 결과: 검사 실패 없음. 게시 directory rename은 mount EBUSY였으나 새 artifact와 seed 파일의 원자적 교체로 완료했습니다. 실패 시 생성된 임시 복사본도 영구 보존본을 확인한 뒤 제거했습니다.
- handoff 저장 경로와 갱신 여부: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-next-development-selection-v1-bbbd21c0082348b09c073c45d73f3e17/handoff-final.md`. 기존 root HANDOFF.md는 보존했습니다.
- 후속 작업: `portfolio-held-band-interaction-v1` 하나를 completion.followup으로 제출합니다. 기존 corrected-entry 2%p와 새 4%p를 동일 frozen engine에서 32회 비교하는 별도 격리 실험이며 이번 선정 작업에서는 실행하지 않았습니다.

## portfolio-held-band-cce0

- 상태: 완료
- 목표와 완료 조건: corrected-entry 동일 엔진에서 2%p/4%p와 비용 1/2배를 7개 fold 및 continuous에 정확히 32회 실행하고, 16개 전체 exact control 및 Decimal 회계를 검증합니다.
- 담당 Luna: gpt-5.6-luna 단일 구현 소유자. explore 후 순차 plan, 독립 review.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-held-band-cce0
- 작업 브랜치: feat/portfolio-held-band-cce0
- 기준 커밋 SHA: 9bafb0ce7bfef4f826669045e3ffc428b96fdf8a (이 등록 커밋을 실제 생성 기준으로 사용합니다.)
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: 지정 source 3개, corrected preregistration/results 및 variant simulation 16개. 총 입력 21개와 core 4개 SHA 검증 통과.
- 수정 허용 범위: backend/jusik/research_portfolio_held_band_experiment.py, backend/tests/test_research_portfolio_held_band_experiment.py, docs/research/portfolio-held-band-interaction-v1.md. 등록부는 Astra만 수정합니다.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 워크트리 전용 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-interaction-v1-cce0cdf0e5ea43e4a088f2dfe5c2fa74.
- 검증 명령과 결과: synthetic pytest, 관련 회귀 pytest, Ruff check/format, strict mypy, 전체 exact control 16개, Decimal 회계 32개, 입력 전후 SHA, 독립 review, main 통합 검사.
- 제외: 제품 엔진/DB/PAPER 설정/runner/GPU 변경, 주문, remote push/refetch, 원본 b2 simulation 사용, retuning/winner selection.
- 종료 조건: main 통합·검사·연구 게시·영구 evidence/hash/handoff 저장 후 병합 워크트리 정리. broader engineering gaps를 결과 이후 읽기 전용 확인하여 즉시 실행 가능한 successor 최대 하나만 제안합니다.
- 실행기 확인: 현재 running attempt는 이 task/attempt 하나이며 CLI completion 경로를 읽기 전용 확인했습니다. 실행기 상태는 변경하지 않습니다.

- 결과 커밋 SHA: 구현 `a37cdda51e203226e0127daef5f54556b6ba03df`, 최종 문서 `246d348dbd88b44fec2970acc399180aeb6d7edc`.
- 병합 직전 main SHA: `6fd7346bc6a799a932db17438e377d17196a02ed`.
- 통합 커밋 SHA: 구현 `7486b2c9ac51edff0d36a68dbcb48293a47d32ab`, 검증 문서 `2aba6eb8c433204e384bc44b8f9d2eff2f8a4d8e`.
- 검토 결과: 독립 사전·결과·최종 코드/문서 review 통과. 초기 엔진 선택, JSON tuple key, eager hash fallback, Decimal precision 및 실패 산출물 보존 문제를 실행 전에 수정했습니다. 독립 verifier의 strict next-open/가격 exact 보강은 저장 결과에만 적용했으며 역사 재실행은 없습니다.
- 실제 결과: 정확히 32회 완료, corrected control 16개 전체 typed JSON exact equality. 2,347 trades 원시 개장가·FX·현금·최종 자산 독립 재계산, 최대 금액 잔차 4e-31 KRW. 양 비용 fold return delta 중앙값 0, fold 4 음수, fold 1/2/3/6 전체 결과 동일. continuous delta는 별도로 +1.052528/+0.817125%p이며 승자 선정은 하지 않습니다.
- 검증 결과: main pytest 71 passed(기존 deprecation 경고 2개), strict mypy 84개 소스, Ruff check/format, git diff --check 통과. 별도 입력 경계 26개와 모의 runner 실패/성공 5개 시나리오 통과. frontend 미변경으로 build 비적용. 통합 검사 실패 없음.
- 게시 결과: /research/history 항목 `portfolio-held-band-interaction-v1-cce0cdf0e5ea43e4a088f2dfe5c2fa74`; API/웹 다운로드 200과 문서 SHA 일치. 기존 seed 항목 63개와 artifact 109개 보존, DB 변경 없음.
- 보존·정리: 영구 audit에 실제/모의 산출물, 입력/소스/검사/hash/review/환경을 보존했습니다. 227개 영구 파일과 handoff 및 archive hash 검증 뒤 이번 병합 워크트리와 전용 브랜치를 제거했습니다. 기존 HANDOFF.md와 이전 4840 워크트리는 보존합니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-interaction-v1-cce0cdf0e5ea43e4a088f2dfe5c2fa74/handoff-final.md.
- 남은 실패: 실제 실행·통합 실패 없음. 후향/PIT 미인증, 조기 폐장과 broker receipt 부재는 연구 한계입니다.
- 후속 제안: `portfolio-session-calendar-stress-v1` 하나. 검증된 offline calendar를 쓰는 격리 adapter/복사 엔진과 synthetic 테스트 3개 신규 파일만 허용하며 제품/PAPER/DB/runner/GPU 변경과 역사 재실행을 제외합니다.


## empty-queue-planner

- 상태: 완료
- 목표와 완료 조건: 연구 큐가 비면 기존 결과를 근거로 읽기 전용 Astra 계획을 실행하고 검증된 후속 과제 하나를 원자적으로 등록합니다. 대기·중복·실패·한도·권한 및 다음 주기 실행을 검증합니다.
- 담당 Luna: gpt-5.6-luna, 단일 구현 소유자. 감독 조사와 순차 계획 완료 후 구현, 독립 검토를 수행합니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-empty-queue-planner
- 작업 브랜치: feat/empty-queue-planner
- 기준 커밋 SHA: 73fdc43de94c39825731002f6f91fea8a764a660 (등록 커밋을 실제 생성 기준으로 사용합니다.)
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: 기존 runner/store 및 history 흐름. 진행 중 held-band 작업 완료 후 pause와 서비스 inactive 확인.
- 수정 허용 범위: backend/jusik/development_runner{,_store,_planning}.py, 관련 runner/planning tests, docs/development-runner.md. 등록부·handoff·운영 설정은 감독만 관리합니다.
- 포트·테스트 DB·출력 경로: 독립 worktree venv와 임시 fixtures. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260912T114934Z-empty-queue-planner.
- 검증 명령과 결과: 관련 pytest, Ruff check/format, strict mypy, 실제 read-only sandbox와 Codex 계획 및 다음 주기 dispatch 검증 예정.
- 종료 조건: 독립 review, main 병합/통합 검사, 웹 기록, 운영 활성화, 증거/hash/handoff 보존 후 이번 worktree 정리.
- 보존 조건: 하루 한도24 및 기존 이력, PAPER/실거래/전략/운영 DB/GPU 설정은 유지합니다. 계획도 기존 quota와 lifecycle을 사용합니다.

- 통합 검증 실패 및 복구: main 병합 6f07ab177b9f6e4fc708f281acebe8e2dfe31f94에서 pytest55·Ruff lint·strict mypy는 통과했고 테스트 파일 한 줄 format 검사만 실패했습니다. Luna의 포맷 수정 및 통합 재검증 전 정리와 운영 재개를 보류합니다.

- 결과 커밋 SHA: 구현 ca4527e, 보완 e68a1b9, 회귀 검증5793462·6869012·631ff2f, 포맷 c1a1d26.
- 병합 직전 main SHA: 66a29ee. 기능 통합6f07ab177b9f6e4fc708f281acebe8e2dfe31f94, 포맷 복구 통합663a643ea90bc09bb08c1a065e3b7e7c5952dcd5.
- 최종 검증: main pytest55·Ruff lint·strict mypy 통과. 포맷 실패는 복구 병합 뒤 format/lint/diff 통과 및 AST 동일성으로 해소했습니다. 독립 소스 검토 통과. 테스트의 gate 허위 통과와 outside-root 해시 혼입은 별도 수정·검증했습니다.
- 실제 실행 증거: 읽기 전용 profile의 attempt 쓰기 허용 및 source/Git/다른 state/artifact/network 차단. 격리 synthetic fixture에서 실제 Astra 제안 등록, 다음 주기의 stub child 선택 확인. 실제 연구/수익 검증으로 혼동하지 않습니다.
- 운영 반영: planning_enabled=true, 하루24회 및 기존 모든 launch/task 기록 보존. queued portfolio-session-calendar-stress-v1부터 재개합니다. 실제 재개 상태는 영구 audit의 activation.json에 기록합니다.
- 통합 커밋 및 정리: 14개 필수 영구 파일의 SHA를 정리 전후 대조한 뒤 이번 워크트리와 전용 브랜치를 force 없이 제거했습니다. 이전4840 워크트리와 기존 HANDOFF 내용을 보존했습니다.
- 문서 통합 보완: 감독이 planning 권한 설명에서 읽기 전용 명령 허용 범위와 transaction 내부 재검증을 명확히 했습니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/20260912T114934Z-empty-queue-planner/handoff-final.md. root HANDOFF.md에서 연결합니다.


## portfolio-held-band-cost3-f9ae

- 상태: 완료
- 목표와 완료 조건: held-band 저장 32개 전체 JSON exact replay 후 비용 3배 16개를 실행하고, 고정체결 산술과 실제 순손익·MDD·회전율 및 현금·수량 차이를 검증합니다.
- 담당 Luna: gpt-5.6-luna 단일 구현 소유자; explore, 순차 plan, 독립 review 후 Astra 통합.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-held-band-cost3-f9ae
- 작업 브랜치: feat/portfolio-held-band-cost3-f9ae
- 기준 커밋 SHA: 15213cdd353de92193077ce2aef660c807a6d7d4 (이 등록 커밋을 실제 생성 기준으로 사용합니다.)
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: held-band experiment의 고정 results/preregistration/hash-manifest, frozen source와 corrected engine 및 simulation 32개.
- 수정 허용 범위: backend/jusik/research_portfolio_held_band_cost3_stress.py, backend/tests/test_research_portfolio_held_band_cost3_stress.py, docs/research/portfolio-held-band-cost3-stress-v1.md. 등록부는 Astra만 수정합니다.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 독립 worktree venv/tmp; 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-cost3-stress-v1-f9aecd54dffc4931a6100ac2de8c8cd3.
- 검증 명령과 결과: 관련 pytest·Ruff·strict mypy, 역사 실행 전 +1 KRW 변조 검출, 32 exact replays, 16 stress, Decimal 회계와 cutoff/next-open/UTC, 독립 review, main 통합 검사 예정.
- 종료 조건: 48회 이하·60분 한도; hash/replay/회계/누출 실패 시 즉시 중단·증거 보존·재시도 금지. 성공 시 로컬 통합·검사·handoff와 필요한 게시 후 durable 보존을 확인하고 이번 worktree만 정리합니다.
- 보존 조건: 자본 1억원, 최대 손실 허용20%, leverage 배분 cap20%, frozen drawdown_limit=.10/gross_cap=.60/symbol_cap=.20. PAPER10%와 실거래 유예. 제품/DB/config/remote/주문/GPU 불변.
- 실행기 확인: running attempt는 portfolio-held-band-cost3-stress-v1 / f9aecd54dffc4931a6100ac2de8c8cd3 하나입니다. 실행기 상태를 변경하지 않습니다.

- 결과 커밋 SHA: 구현 `21bbb9adbe7a9fc0dd6322689bbf502eaa36d057`, metadata 보완 `5c53b04ea77956e63e309b273fdd87d0184a1729`, 포맷 `e4782741b6427fe70bcafc5ee5128989a086a2c1`, 보고서 `0ea1fbe86cf349ba464698e2eb9a8382164a2783`.
- 병합 직전 main SHA: `06a8924468811c7adb478aa80e13ad58b4c739b6`. 통합 커밋 SHA: `1698741c1eaab4bda9e9b41301dce3a11ad42177`.
- 실제 결과: 32개 전체 JSON exact replay 뒤 16개 비용3 스트레스, 총48회·30.6658초·재시도0. 초기 +1 KRW 변조32개 거부. 독립48개 회계 최대 오차4e-31 KRW. fold 수익률/MDD/회전율 차이 중앙값 모두0, fold4 수익률 차이는 음수이며 actual3x가 fixed 산술보다 낮은 경우10/16입니다. Continuous는 별도로 보고했습니다.
- 검토 결과: 초기 runtime 변조/FX/helper hash/완전성/중앙값/metadata 지적을 역사 실행 전에 보완하고 독립 코드·결과 review를 통과했습니다. source AST가 동일한 포맷 보완도 확인했습니다. 독립 verifier와 보고서 파서 개발 중 스키마 오류는 증거에 보존했고 실제 입력·replay·회계·누출 실패는 없습니다.
- 통합 검증: pytest75개, strict mypy86개 소스, Ruff lint/format, diff 검사 통과. 기존 tracked215개 보존. 워크트리 전체 mypy는 선택 의존성 torch 부재로 제한됐으나 관련 모듈 및 main 전체 mypy는 통과했습니다. torch 설치나 GPU 변경은 없습니다. frontend 미변경으로 build 비적용.
- 게시: 연구 history 항목 `portfolio-held-band-cost3-stress-v1-f9aecd54dffc4931a6100ac2de8c8cd3`, API/웹 다운로드200 및 SHA 일치. 기존 이력65개와 artifact111개 보존, DB 변경 없음.
- 보존·정리: 입력·소스·실제48개 결과·검사·review·publication·handoff 포함 영구575개 파일을 정리 전후 SHA 대조했습니다. 이번 워크트리·전용 브랜치를 force 없이 제거했고 기존 HANDOFF.md와 이전 두 워크트리를 보존했습니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-cost3-stress-v1-f9aecd54dffc4931a6100ac2de8c8cd3/handoff-final.md.
- 남은 작업: 요청 범위 없음. 후향/PIT 미인증, 조기 폐장·partial/cancel/reject 미지원은 유지합니다. 추가 배수/밴드 탐색, 승자 선정, 정책 승격, 손실 보장은 없습니다.


## portfolio-held-band-cost-path-0f90

- 상태: 완료
- 목표와 완료 조건: 저장48개 hash 및 회계 검증 후32개 비용 비교와16개 밴드 분해 차이, 음수 결과와 결정적 출력 증거를 보존합니다. 역사 실행·외부 수집·튜닝은0회, 분석은2회 이하 및15분 한도입니다.
- 담당 Luna: gpt-5.6-luna 단일 구현 소유자. 감독 explore 후 순차 plan, 별도 review를 수행합니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-held-band-cost-path-0f90
- 작업 브랜치: feat/portfolio-held-band-cost-path-0f90
- 기준 커밋 SHA: cf0db95 (등록부를 포함한 실제 생성 기준)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: portfolio-held-band-cost3-stress-v1-f9aecd54dffc4931a6100ac2de8c8cd3/experiment의 results, preregistration, manifest와 simulations48개. 상위3개 hash 검증 일치.
- 수정 허용 범위: 신규 research_portfolio_cost_path_attribution 모듈, 대응 테스트, 한국어 연구 문서. 기존 attribution 회계를 재사용합니다.
- 포트·테스트 DB·출력 경로: 포트/DB 미사용. worktree 독립 venv. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-cost-path-attribution-v1-0f907dc6cd5b40cf9604af0bccbb2acd.
- 검증 명령과 결과: 신규 pytest/Ruff/strict mypy 및 회계 residual≤1e-6, 48완전성,32비교, 결정적2회 출력 대조 예정.
- 종료 조건: 검토·main 통합 검사·handoff 및 필요한 웹 게시 후 영구 evidence/hash 확인, worktree 정리.
- 보존 조건: 자본1억원, 사용자 손실20%, leverage cap20%, frozen drawdown.10 및 PAPER10% 불변. 실주문/remote push/PAPER engine·DB/GPU 변경 금지.
- 실행기 확인: 현재 task/attempt 하나만 running이며 CLI output은 해당 attempt/completion.json입니다. runner를 중지하지 않습니다. 기존 HANDOFF.md 및 두 worktree를 보존합니다.

- 실행 결과: 원자료 분석2회, 추가 역사 실행·외부 수집·튜닝0회. 원자료 실행의 보수적 시간 상한534.205초. 32개 비용 비교·16개 밴드 차이를 저장하고 후속 검증과 표 생성은 저장 출력만 사용했습니다.
- 독립 결과 검산: 32개 비교 모두 순손익 감소. 종목 합계와 NAV 차이 최대7.156250e-31 KRW. continuous 비용2에서 .04의 비용 증가가 작아도 경로 악화로 순손익 감소가 더 큰 음수 사례를 보존합니다.
- 검토 보완: manifest 상수, 누락된 분해항, 실제 residual 검산, 합성48 loader, CLI 출력 일치, 테스트 상수 복원 지적을 수정했습니다. 최종 리뷰와 main 통합 검사는 아래에 기록합니다.
- 초기 커밋 보존: 작업자가 초기 커밋95ab4d를 대체하여 원본을 archive/portfolio-cost-path-initial-0f90 및 durable initial-development.bundle에 보존했습니다. 이후 수정은 추가 커밋으로 수행했습니다.

- 결과 커밋 SHA: 최종 `10ff83952e45a788b08432e3daabb4217362876a`.
- 병합 직전 main SHA: `ec0ff7fa4c0a1632e2465cb7a860540740e55921`. 통합 커밋 SHA: `f33e06c54ee5126fc3be3f807822dbdefbddbc64`.
- 검토 결과: 독립 PASS. 추가 합성 fixture7개, 실제 저장 출력32/16 검산, pinned hash 전역 상태 복원 검증 통과.
- 통합 검증: main pytest25개, Ruff lint/format, strict mypy2개 파일, diff 검사 및 기존 코드·48개 입력 hash 보존 통과. frontend 미변경으로 build 비적용.
- 게시: 연구 history 항목 `portfolio-held-band-cost-path-attribution-v1-0f907dc6cd5b40cf9604af0bccbb2acd`, API/웹 다운로드200 및 SHA 일치. 기존 이력66개/artifact112개 보존, DB 미접근. mounted history root의 directory rename은 EBUSY로 실패하여 검증된 seed를 루트 내부 atomic file replace로 게시했습니다.
- 보존·정리: 필수158개 durable 파일을 정리 전후 SHA 대조했습니다. 이번 worktree·전용 작업 브랜치를 force 없이 제거했습니다. 기존56b9·4840 worktree와 기존 HANDOFF.md 내용을 보존했습니다. 초기 커밋 보존용 archive branch와 bundle은 유지합니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-cost-path-attribution-v1-0f907dc6cd5b40cf9604af0bccbb2acd/handoff-final.md.
- 남은 작업: 승인 범위 없음. 부분체결·취소·거절은 unsupported이며 실거래 유예와 기존 제약을 유지합니다.

## portfolio-rebalance-cadence-e017

- 상태: 차단
- 목표와 완료 조건: corrected-entry band 0.02를 고정하여 4/8주 × 비용1/2/3 × 7개 독립 fold 및 continuous의 48회만 실행합니다. 4주 control24 전체 JSON exact replay를 먼저 통과해야 합니다.
- 담당 Luna: gpt-5.6-luna 단일 구현 소유자. explore, plan, 독립 review는 읽기 전용으로 수행합니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-rebalance-cadence-e017
- 작업 브랜치: feat/portfolio-rebalance-cadence-e017
- 기준 커밋 SHA: 5529a54dcd9b7d016586b6bd021d91f7164726ff 이후 이 등록부를 포함한 준비 커밋입니다.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: cost3 f9aecd54 experiment 및 원천 manifest. 54개 artifact와 source/core/helper/runner를 포함한 68개 hash 일치를 input-preflight.json에 기록했습니다.
- 수정 허용 범위: 신규 research_portfolio_rebalance_cadence_cost_stress 모듈, 대응 테스트, 한국어 연구 보고서. 등록부는 Astra만 수정합니다.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 독립 worktree venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-rebalance-cadence-cost-stress-v1-e0176881b1d34518805032c279324417.
- 검증 명령과 결과: 관련 pytest, Ruff lint/format, strict mypy. control 전체 JSON, hash, temporal cutoff, cadence/holiday/UTC, 위험 청산 및 recovery/cooldown, Decimal residual≤0.000001 KRW를 검사합니다.
- 제한: 최대48회/60분, 재시도·외부 수집 없음. 입력/hash/control/회계 실패 시 중단합니다. 1억원/손실한도20%/leverage20%/frozen drawdown10%를 유지합니다. PAPER/제품엔진/DB/config/주문/remote/GPU 변경 금지.
- 보고 기준: 동일 anchor, reentry_ready부터 reentry까지 시간 및 recovery_reset/기간 말 censoring을 보존합니다. frozen frequency_skip의 four-week cadence 문구는 legacy label임을 명시합니다. 승자 선택·합성·retuning·정책 승격 없음.
- 실행기 확인: 현재 task/attempt가 running인 자동 dispatch입니다. runner를 중지하지 않습니다. 기존 HANDOFF.md와 이전 두 worktree는 보존합니다.
- 종료 조건: 독립 검토, Astra main 병합과 통합 검사, 필요한 게시 및 handoff, 영구 evidence/hash 보존 후 이번 worktree만 정리합니다.

- 실제 실행 결과: CLI 한 번이 preregistration 출력에서 KeyError(input_paths)로 중단되었습니다. cost3 입력의 source_paths를 legacy 키로 읽은 구현 오류이며 원천 입력 누락이 아닙니다. ledger0개, simulation0/48, 재시도0회입니다.
- 최종 검증: Astra의 관련 pytest59개 통과(경고2), Ruff lint/format 통과. runner와 새 테스트를 함께 검사한 strict mypy는 오류4개로 실패했습니다. final-checks.json과 로그를 영구 audit에 보존했습니다.
- 검토 결과: 독립 실패 검토에서 초기 readiness PASS를 철회했습니다. tests_passed=false, review_passed=false이며 실제 비교 지표는 없습니다.
- 통합·정리: 구현 미병합, 통합 검사·웹 연구 보고서 게시 미실시. 차단 worktree와 branch를 보존합니다. main의 변경은 작업 등록부뿐이며 기존 HANDOFF.md와 이전 worktree를 보존합니다.
- 재개 조건: source_paths 출력 계약과 실제 metadata를 사용하는 회귀 fixture, strict mypy 오류를 수정·검증한 뒤 새 명시적 시도로 수행해야 합니다. 이번 attempt에서 재실행하지 않습니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-rebalance-cadence-cost-stress-v1-e0176881b1d34518805032c279324417/handoff-final.md.


## gpu-collector-mode

- 상태: 완료
- 목표와 완료 조건: 사용자가 승인한 GPU 역할 전환. 수집·기존 결과를 유지하면서 GPU를 요청 기반 포트폴리오 스트레스 실험에 사용합니다.
- 담당 Luna: gpt-5.6-luna, 작업별 단일 구현 소유자. 독립 조사·순차 계획 완료.
- 워크트리 절대 경로: /home/kwl/projects/jusik-gpu-collector-mode
- 작업 브랜치: feat/gpu-collector-mode
- 기준 커밋 SHA: 7544e986101d1bcdad166576254cb3836bae8266; 이 등록 커밋을 실제 생성 기준으로 사용합니다.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 기존 universe daemon 및 보존된 paired continuous NAV 경로. 자동 개발 pause/service inactive 확인.
- 수정 허용 범위: research_universe.py, research_optimizer_store.py, development_runner.py, related tests, docs/research-gpu-role.md, deploy/systemd/jusik-research-optimizer.service. 등록부·handoff·설치 서비스·공개 산출물은 감독 소유.
- 포트·테스트 DB·출력 경로: worktree별 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260912T212923Z-gpu-role-transition.
- 검증: focused pytest/Ruff check·format/strict mypy, 독립 review, main 통합 검사. GPU 실제512/4096 시나리오·CPU parity 및 collection-only 활성화는 감독 수행.
- 보존: PAPER/live 엔진·DB·동결 계약10% 유지. 기존 GPU 서비스의 CPU 수집 모드 전환은 사용자 명시 승인 범위이며 감독이 원본 unit 보관 후 적용합니다.
- 종료 조건: main 병합·검증, 실제 역할 전환·웹 게시·SHA/handoff 보관, 병합 worktree 정리, 자동 개발 재개.


- 실제 공통 생성 기준: `6ee4be69d3e5d03f40969fee40cae5ca5c308faa`.
- 결과·검증: local main 최종 구현 `844cf6089820815427db03d3baef40d95fa80c9a`; 영향 통합 pytest86개, 후속 stress17개, Ruff check·format 및 변경 파일 strict mypy 통과. 기존 transitive type 오류는 별도 기록. 독립 최종 검토 P1/P2 없음.
- 실제 적용: CPU collection-only 수집·보고서 갱신 확인. CUDA512/4096 parity 최대1.53e-12%p; auto512 CPU/4096 CUDA 확인. 웹 이력·다운로드4경로 검증.
- 복구 기록: 첫 stress 통합에서 torch 설치 환경 타입 오류2개를 발견해635b5ec로 수정 후 재검증했습니다. 초기 CLI 초안은 CUDA·신규 테스트 미완성으로 채택하지 않았습니다.
- 보존·정리: 원본 설정, source patch·환경·SHA manifest·실험·검토·통합 결과를 `/home/kwl/.local/share/jusik/portfolio-audit/20260912T212923Z-gpu-role-transition`에 보관하고 병합 worktree와 branch를 정리했습니다. 기존 미병합3개는 보존합니다.
- handoff: `/home/kwl/.local/share/jusik/portfolio-audit/20260912T212923Z-gpu-role-transition/HANDOFF.md`. 자동 실행 재개 확인은 같은 경로 runner-activation.json을 확인합니다.

## gpu-portfolio-stress

- 상태: 완료
- 목표와 완료 조건: 사용자가 승인한 GPU 역할 전환. 수집·기존 결과를 유지하면서 GPU를 요청 기반 포트폴리오 스트레스 실험에 사용합니다.
- 담당 Luna: 초기 CLI Luna가 CUDA·신규 테스트 미완성 상태로 종료하여 결과를 채택하지 않았습니다. 종료 확인 후 native Luna `collector_transition`에 단일 구현 소유권을 이전했습니다. 동시 구현 담당자는 없습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-gpu-portfolio-stress
- 작업 브랜치: feat/gpu-portfolio-stress
- 기준 커밋 SHA: 7544e986101d1bcdad166576254cb3836bae8266; 이 등록 커밋을 실제 생성 기준으로 사용합니다.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 기존 universe daemon 및 보존된 paired continuous NAV 경로. 자동 개발 pause/service inactive 확인.
- 수정 허용 범위: new research_portfolio_gpu_stress.py, related test, docs/research-portfolio-gpu-stress.md. 등록부·handoff·설치 서비스·공개 산출물은 감독 소유.
- 포트·테스트 DB·출력 경로: worktree별 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260912T212923Z-gpu-role-transition.
- 검증: focused pytest/Ruff check·format/strict mypy, 독립 review, main 통합 검사. GPU 실제512/4096 시나리오·CPU parity 및 collection-only 활성화는 감독 수행.
- 보존: PAPER/live 엔진·DB·동결 계약10% 유지. 기존 GPU 서비스의 CPU 수집 모드 전환은 사용자 명시 승인 범위이며 감독이 원본 unit 보관 후 적용합니다.
- 종료 조건: main 병합·검증, 실제 역할 전환·웹 게시·SHA/handoff 보관, 병합 worktree 정리, 자동 개발 재개.

- 실제 공통 생성 기준: `6ee4be69d3e5d03f40969fee40cae5ca5c308faa`.
- 결과·검증: local main 최종 구현 `844cf6089820815427db03d3baef40d95fa80c9a`; 영향 통합 pytest86개, 후속 stress17개, Ruff check·format 및 변경 파일 strict mypy 통과. 기존 transitive type 오류는 별도 기록. 독립 최종 검토 P1/P2 없음.
- 실제 적용: CPU collection-only 수집·보고서 갱신 확인. CUDA512/4096 parity 최대1.53e-12%p; auto512 CPU/4096 CUDA 확인. 웹 이력·다운로드4경로 검증.
- 복구 기록: 첫 stress 통합에서 torch 설치 환경 타입 오류2개를 발견해635b5ec로 수정 후 재검증했습니다. 초기 CLI 초안은 CUDA·신규 테스트 미완성으로 채택하지 않았습니다.
- 보존·정리: 원본 설정, source patch·환경·SHA manifest·실험·검토·통합 결과를 `/home/kwl/.local/share/jusik/portfolio-audit/20260912T212923Z-gpu-role-transition`에 보관하고 병합 worktree와 branch를 정리했습니다. 기존 미병합3개는 보존합니다.
- handoff: `/home/kwl/.local/share/jusik/portfolio-audit/20260912T212923Z-gpu-role-transition/HANDOFF.md`. 자동 실행 재개 확인은 같은 경로 runner-activation.json을 확인합니다.

## portfolio-held-band-underwater-38fd

- 상태: 완료
- 목표와 완료 조건: 고정 48개 경로 및 paired 24개 underwater 분석, 검토·main 통합 검사·영구 증거와 handoff 보존.
- 담당 Luna: 단일 gpt-5.6-luna 구현 작업자.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-held-band-underwater-38fd
- 작업 브랜치: feat/portfolio-held-band-underwater-38fd
- 기준 커밋 SHA: 44bb62b0948545b459d9cd609d1fe5ef1de520d3 이후 이 등록 커밋.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: cost3 stress f9aecd54 experiment, 기존 cost path attribution loader.
- 수정 허용 범위: 새 underwater 분석 모듈·대응 테스트·연구 문서. 등록부는 Astra 소유.
- 포트·테스트 DB·출력 경로: 서버와 DB 없음. worktree 내부 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-underwater-duration-v1-38fd7b5ffb304507a1e222205e9d2cac.
- 검증 명령과 결과: pytest/Ruff/strict mypy 및 독립 검토 예정. 실제 분석 48개·paired24개 1회, 단일 CPU 600초 상한, historical simulation 0회.
- 검토 결과와 남은 문제: 진행 전. 기존 HANDOFF와 미병합3개 보존.
- handoff 저장 경로: 위 영구 audit/HANDOFF.md.

- 실제 생성 기준 SHA: `7c96a2a6f9780a4c058e6d5c22a708a314e455ee`.
- 담당 및 결과 커밋: Luna code, `9a471209c21ea49dc4fd180333c29bf3cfe60f74`. 독립 explore/review 최종 승인, material finding 없음.
- 병합 직전 main SHA: `7c96a2a6f9780a4c058e6d5c22a708a314e455ee`.
- 통합 커밋: `2f491ea8f8df1d255638e63ddfcb4b31201095e0`. main pytest47개, Ruff check/format, strict mypy, diff 통과. frontend 변경 없음.
- 실제 분석: 단일 CPU0.3656초, historical simulation0회, 48경로·24paired 한 번. 승인7d04a1e 결과를 보존하고 최종 paired terminal flag는 기존48행에서 복사했다. 추가 경로 분석 없음.
- 결과: fold4 비용1/2/3 모두 MDD 감소와 기간24시간/10.5시간/10.5시간 증가. continuous는3cost 모두 MDD·최장기간 감소, 종료는6경로 모두 미회복. 정책 승격 없음.
- 보존·정리: 영구 audit에359개 파일과 SHA/handoff를 먼저 검증한 후 이번 worktree를 정상 제거했다. 작업 브랜치 및 기존 미병합3개 보존.
- 게시: 기존 연구 이력70개·artifact116개 보존, 보고서 API/웹 다운로드200·SHA 일치. DB 변경 없음. 정확한 통합 SHA는 audit/publication.json에 보존.
- handoff: 위 audit/HANDOFF.md. 기존 루트 handoff 내용 보존. 통합 검증 실패 없음.


## portfolio-expanded-universe-1975

- 상태: 완료
- 목표와 완료 조건: 확정 mandate 추적·planner 읽기 회귀검사, IVV/SGOV+현금 준비도 및 사전등록, independent review·main 통합 검사·웹 게시·증거 보존 후 정리.
- 담당 Luna: 단일 gpt-5.6-luna code 작업자.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-expanded-universe-1975
- 작업 브랜치: feat/portfolio-expanded-universe-1975
- 기준 커밋 SHA: f87607a337c04c3d8498bed1a465b87d4a5fc78f 이후 이 등록 커밋.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 사용자 decision SHA30d2108bc082b7d2d9d079fa09548c15f416167174850303c0d852ada269f73c; explore/plan 완료, Astra bounded plan 승인. 현재 runner claim 안에서 실행 중.
- 수정 허용 범위: tracked mandate와 한국어 readiness/prereg 문서, development_runner.py의 최소 planning prompt 변경, 관련 테스트. 등록부·audit·publication·handoff는 Astra 소유.
- 포트·테스트 DB·출력 경로: worktree 전용 venv/tmp; 서버 없음, 운영/PAPER DB 접근·변경 없음. audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-expanded-universe-mandate-v1-1975c426b9e1436c979e5c4091bfa595.
- 검증 명령과 결과: focused pytest/Ruff/strict mypy 및 독립 review 예정. historical simulation0회, GPU0회, 주문0회.
- 검토 결과와 남은 문제: 진행 중. 기존 HANDOFF와 미병합3개 보존.
- handoff 저장 경로: 위 audit/HANDOFF.md.

- 실제 생성 기준: `8f1a4ec2b96c1a482889d7fb7d88106f084b365f`.
- 담당 및 결과: 단일 Luna code, 최종 `fc2f2034428f834cdff8c25e7c22725fe35fecab`; 독립 review 최종 승인, material finding 없음. 손상 mandate와 실제 proposal enqueue 차단 회귀를 보강한 뒤 통합했습니다.
- 병합 직전 main SHA: `8f1a4ec2b96c1a482889d7fb7d88106f084b365f`.
- 통합 커밋: `d112be8de6f6eb507689936223d6435335dc54ce`. main pytest60개, Ruff check/format, 변경 Python3파일 strict mypy(--follow-imports=silent), diff 통과. frontend 변경 없음.
- 산출물: exact mandate JSON/한국어 요약과 IVV·SGOV+현금 준비도·기존16종목 baseline 대비 A/B 사전등록. 투자기간 미정, 3년은 history만 유지합니다. 가격/action/FX/total-return adapter/실시간 데이터 gate는 미통과이며 simulation0회입니다.
- 게시: 한국어 보고서 API/웹 다운로드200·SHA bea534ed60019d57ba1d680b47161ee6ba2db5e6fc7d92ef8b71fe6d14a1836f 일치. 기존 이력71개·artifact117개와 DB 보존. mounted history root rename EBUSY를 파일 단위 원자적 게시로 복구했습니다.
- 보존·정리: audit에 원문·날짜·환경·패치·검사·검토·handoff와276개 파일의 SHA를 먼저 보존한 후 이번 worktree와 전용 브랜치를 정상 제거했습니다. 기존 미병합3개와 root HANDOFF는 보존했습니다. force/push/PAPER/GPU/실주문/생산 데이터 변경 없음.
- handoff: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-expanded-universe-mandate-v1-1975c426b9e1436c979e5c4091bfa595/HANDOFF.md`.
- 통합 검증 실패 없음. 초기 가상환경 준비 오류는 격리 Python3.13.15 환경으로 해결했고, 게시 복구 근거는 audit에 보존했습니다.

## runner-unlimited

- 상태: 완료
- 목표: 사용자 요청으로 일일 launch 제한을 명시적 null로 해제하고 기존 유한 설정·timeout·cooldown·lock·실패 격리를 보존합니다.
- 담당 Luna: native collector_transition, 단일 소유자.
- 워크트리: /home/kwl/projects/jusik-runner-unlimited
- 브랜치: feat/runner-unlimited
- 기준: d1d16dfff1e20ade26453fc949b285d53e961ae2; 이 등록 커밋에서 생성합니다. 통합 local main.
- 범위: backend/jusik/development_runner.py, 관련 tests, docs/development-runner.md. 설치 설정·웹 보고·인계·등록부는 감독 소유.
- 격리·근거: 자체 venv/tmp; /home/kwl/.local/share/jusik/portfolio-audit/20260913T004630Z-runner-unlimited.
- 검증·완료: quota초과에서도 unlimited dispatch, 유한quota/중복/cooldown/timeout보존, pytest/Ruff/strictmypy·독립검토·main통합·25건 초과 회귀 테스트와 실제 다음 dispatch 확인·웹·인계·worktree정리.

- 결과: worker380fb56·docs847d006, 구현통합 `617274dd2eb10402e5f9386c70bf37fffe4fdf14`. runner45tests/Ruffcheck·format/strictmypy 통과. 독립검토 P1/P2 없음. 설치daily_launches=null, 다른설정·launchhistory보존.
- 보존·정리: `/home/kwl/.local/share/jusik/portfolio-audit/20260913T004630Z-runner-unlimited`에 archive/checks/설치·연구근거·웹보고서·HANDOFF 저장. 이번worktree/branch정리, 기존미병합3개보존. 실제자동개발기동은 activation.json 확인.

## portfolio-gpu-allocation-screen-42b4

- 상태: 진행 (배분 연구는 입력 gate 차단)
- 목표와 완료 조건: 고정 입력의 누락 근거를 한국어 보고서로 작성하고 검토·main 통합·웹 게시·handoff로 보존한다. 성능 결과를 만들지 않는다.
- 담당 Luna: code 단일 문서 구현자, explore/plan 완료.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-gpu-allocation-screen-42b4
- 작업 브랜치: docs/portfolio-gpu-allocation-screen-42b4
- 기준 커밋 SHA: 9945be5d3c8c60c618857b34adb931f0b7e38e1e 이후 이 등록 커밋
- 통합 대상 브랜치: local main
- 입력과 선행 작업: expanded mandate 완료; readiness false. audit/input-manifest.json에 보고서·소스 SHA 고정. 현재 runner attempt 내부 작업.
- 수정 허용 범위: docs/research-portfolio-gpu-allocation-screen.md만. 등록부·audit·게시·handoff는 Astra 소유.
- 포트·테스트 DB·출력 경로: 서버/DB/venv 불필요. audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-gpu-allocation-screen-v1-42b4b5646fe3467394bd0b37d46eac99
- 검증 명령과 결과: 문서 diff·입력 SHA·독립 review·게시 검증 예정. 금융 acceptance tests는 입력 부재로 blocked.
- 결과 커밋 SHA·통합 검증·정리: 대기
- handoff 저장 경로: 위 audit/HANDOFF.md

## portfolio-low-cash

- 상태: 완료
- 목표와 완료 조건: 3년 핵심 종목 자료에서 현금 비중과 거래 빈도를 함께 줄이는 32개 설정을 사전 등록하고 실제 비교, 위험 검증, 웹 보고를 완료한다.
- 담당 Luna: CLI gpt-5.6-luna 단일 구현자. 내장 작업자 스레드 한도로 전용 CLI 세션을 사용했으며 조사·계획·독립 검토를 수행했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-low-cash
- 작업 브랜치: feat/portfolio-low-cash
- 기준 커밋 SHA: deab5b2 (등록과 최신 mandate 포함)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 현재 research-mandate, core 10종목 고정 입력. 신규 ETF 수집은 선행 조건에서 제외한다.
- 수정 허용 범위: 신규 low_cash_experiment 모듈, 대응 테스트, 연구 문서. 기존 engine/PAPER 설정 변경 없음.
- 포트·테스트 DB·출력 경로: 워크트리 자체 가상환경과 임시 테스트 경로. 실제 연구는 별도 audit/experiment.
- 검증 명령과 결과: 관련 통합 pytest 51개, Ruff check/format, 범위를 지정한 strict mypy 통과. 독립 검토의 중요한 지적을 같은 Luna가 수정했습니다. 실제 142회 비교 및 원본 140쌍 독립 산술 검증을 완료했습니다.
- 결과 커밋 SHA·통합 검증·정리: 구현 b7bbb48, 수정 6f22d31·be9227f. 병합 직전 main 5da867e, 통합 60e443c2eba6da6e616b6f0ce4ecfa95b0afcf97. 증거와 환경을 audit에 보존하고 해당 워크트리·브랜치를 정리했습니다. 기존 미병합 워크트리 4개는 보존합니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/20260913T011304Z-low-cash-low-turnover/HANDOFF.md
- 결과: 비용 1배의 연속 3년 비교에서 후보 A 수익률 118.94%, 현금 중앙 비중 41.66%, 거래일 33일, 최대 낙폭 14.96%입니다. 기준은 각각 43.18%, 79.80%, 71일, 6.53%입니다. 거래 빈도는 줄었지만 거래금액 회전율과 비용은 증가했습니다. 두 후보 모두 이번 평가의 전역 낙폭·실제 레버리지 기준을 통과했으며 PAPER 반영은 하지 않았습니다.
- 웹 산출물: `/research/history/download/aceef65a6cf64ac8afddfcc0226827ce3146100651706f2e3cab010008dc70fd`. 기존 게시 이력을 보존하고 API·웹·두 다운로드의 SHA를 확인했습니다.
- 운영 상태: 자동 실행 재개 증거는 audit의 `activation.json`으로 확인합니다. 남은 현금 원인과 위험 추정 개선 작업을 큐에 추가하고 선택적 신규 ETF 수집은 해당 핵심 작업 뒤에 배치했습니다. 과거 중단된 allocation 시도와 미병합 문서는 변경하지 않았습니다.

## portfolio-blocked-research-repair-122f

- 상태: 준비
- 목표와 완료 조건: source_paths/input_paths 불일치와 최종 현금 변조 누락을 오프라인 어댑터·검증기로 복구하고 독립 검토, local main 통합 검사, 한국어 웹 보고 및 handoff를 완료한다.
- 담당 Luna: code 단일 구현자. explore와 plan은 읽기 전용으로 수행한다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-blocked-research-repair-122f
- 작업 브랜치: fix/blocked-research-repair-122f
- 기준 커밋 SHA: 2c4e830 이후 이 등록 커밋. 통합 대상 local main.
- 입력: audit/portfolio-blocked-research-repair-v1-122f67291266410d8706be0ade14e940/input-manifest.json에 기존 감사 자료·실제 입력·보존 모듈 742개 파일을 변경 전에 고정했다.
- 수정 허용 범위: 신규 오프라인 repair adapter/validator, 관련 테스트, 한국어 사용 문서. 보존 연구 모듈은 정확한 SHA 확인 후 새로운 출력 경로의 복사본에만 수정한다.
- 제한: 한 차단 원인씩 순차 복구, 기존 산출물 검증만 수행하며 새 전략 simulation 0회. 기존 워크트리·과거 이력·PAPER·broker·GPU·서비스는 변경하지 않는다.
- 포트·테스트 DB·출력 경로: 자체 venv/tmp, 서버·DB 없음. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-blocked-research-repair-v1-122f67291266410d8706be0ade14e940.
- 검증: 원래 KeyError와 현금 +1 KRW 허점 재현, 실제 자료 정상 통과 및 변조 거부, pytest/Ruff/strict mypy, 독립 review와 main 재검사.
- 종료 조건: 두 기술 gate의 재개 가능 범위와 남은 기존 테스트 의존성을 명시한다. 과거 blocked 시도를 재시도하거나 완료로 바꾸지 않는다.
- handoff 저장 경로: 위 audit/HANDOFF.md. 증거·SHA·handoff 보존 후에만 이번 워크트리를 정리한다.

- 상태: 완료 (요청한 기술결함 2건 수정; calendar 전체 연구는 추가 입력 의존성으로 보류)
- 실제 기준 커밋: `8a4e9aec075cd0e6b6f5804a0b611697127e2de5`. 단일 구현 워커에 `gpt-5.6-luna`를 지정했습니다.
- 결과 커밋: 코드 `871f85c961111c902904570f32420e1a4c1855a3`, 재개 조건 문서 `513122a18197738636489498487e38991815e1bb`. 독립 review 승인, 차단 지적 없음.
- 병합 직전 main: `8a4e9aec075cd0e6b6f5804a0b611697127e2de5`. 통합 커밋: `7bc7c5cb0d7eb17fda61d2fb8d95a90caa96190b`.
- 통합 검증: pytest63개, Ruff check/format, 신규 어댑터·테스트 strict mypy 통과. 생성한 복구 소스2개 strict mypy도 통과. 원본742파일 해시 보존 확인. frontend 변경 없어 build 대상 아님. dependency deprecation warning2건.
- 재현: cadence 원래 KeyError와 수정 metadata 확인. calendar 원래 정상·+1KRW 변조 잔차0, 수정 정상 잔차0 및 변조 거부. 새 simulation0회, 저장 simulation1개를 정상/변조·원본/수정 검증에 사용. 초기 AST·fixture preflight 실패는 ledger 실행 전이며 감사 자료에 보존.
- 재개 경계: cadence 경로 차단은 해소됐으나 기존 테스트 mypy4건은 별도 조건. calendar는 현금 검증 수정에도 기존 normalizer의 bars/adjustment_factors 불일치로 전체 재개 보류. 원본 generator와 normalizer의 결과가 저장 fixture와 완전히 같음을 확인해 현금 결함만 재현했으며 역직렬화 계약을 완화하지 않음.
- 웹: 기존 이력75개·artifact121개 보존. 보고서 SHA `2ce89353738be9f0a8983f7daf70f6feb4cb451276421acf151bfa7f404edebc`; API·웹·두 다운로드200 및 SHA 일치. DB 쓰기 없음.
- 증거·handoff: 위 영구 audit에 원본 복사본, 검증 로그, 생성 소스·diff, 입력 해시, 리뷰, 한국어 보고서·게시 확인, HANDOFF.md를 보존한다. 보존 후 이번 병합 워크트리와 브랜치만 정리한다. 기존 미병합4개와 root HANDOFF.md는 유지한다.
- 변경하지 않은 범위: 과거 blocked 이력·큐 재시도, frozen 엔진·PAPER10%·DB·브로커 실행·서비스·GPU·원격 push.
- 정리 완료: 영구 audit의51개 파일 SHA와 handoff를 검증한 후 이번 worktree·전용 branch를 정상 제거했다. 강제 삭제 없음. 기존4개 worktree와 root HANDOFF.md는 유지했다. 실제 정리 상태는 audit/cleanup.json에 기록한다.


## portfolio-residual-cash-abec

- 상태: 준비
- 목표와 완료 조건: 잔여 현금의 겹치는 원인을 진단하고 단일 제한 가설을 사전등록하여 최대 24회 정확 비교 또는 재현 가능한 부정 결과, 독립 검토, local main 검사, 한국어 웹 보고와 인계를 완료한다.
- 담당 Luna: code 단일 구현자. explore와 plan은 읽기 전용으로 완료했다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-residual-cash-abec
- 작업 브랜치: feat/portfolio-residual-cash-abec
- 기준 커밋 SHA: 등록 커밋 직후 SHA를 실제 생성 기준으로 기록한다.
- 통합 대상 브랜치: local main
- 입력: 검증된 low-cash audit의 source, request, 원본 엔진과 개발 구간 raw artifacts. results SHA 71c1e5efac632d6f934d5b411d5f217131d0eb635aae121e90aee0373963e445.
- 수정 허용 범위: 신규 residual_cash 모듈, 대응 테스트와 한국어 연구 문서만. 기존 engine/PAPER/DB/서비스/GPU/원격 변경 금지.
- 격리: 워크트리 자체 .venv; 출력은 /home/kwl/.local/share/jusik/portfolio-audit/portfolio-residual-cash-risk-proxy-v1-abecaf881ae842378d77d5a6838040ed. 포트/DB 없음.
- 검증: 입력·코드 SHA, 과거 가용 가격·FX, 미래 변조, 1KRW 회계 변조, 실제 종목·레버리지 비중, 원본/observer parity, 비용 1/2배, dev/final 분리와 finalist 사전 동결. pytest/Ruff/strict mypy 및 통합 후 재검사.
- 결과·검토·통합 SHA: 진행 후 기록한다.
- 보존: 위 audit에 증거·SHA·HANDOFF.md 보존 후 이번 병합 워크트리만 정상 제거한다. 기존 미병합 4개와 root HANDOFF.md는 유지한다.

- 상태: 통합 대기 (독립 검토 승인)
- 실제 기준 커밋: c9a00a4cb066865e95309de5610532dffb5ec94c. 단일 Luna 구현 워크트리에서 신규 모듈·테스트·문서 3개 파일만 변경했다.
- 결과 커밋: ce0fdbff9914df09d4b7697fcf25f07822f2b7c0. 독립 결과 검토는 audit/review/final-review.json에 저장했다.
- 유효 비교: 개발 8회와 초기 무효 8회, 총 16회. 최종 후보 없음, final/continuous 0회. H1은 현금 감소·순수익 증가·동일 거래일이나 dev1 실제 종목 비중 28.98%/28.40%로 탈락했다.
- 실행 보존: Decimal 끝자리 차이로 중단한 기준 원장 3개를 재검증해 재사용했다. target_weight와 band_skip.value에만 1e-38 허용, 실제 6개 차이 모두 1e-41. 기준 거래·현금·평가액·성과 지표는 보관본과 정확히 일치한다.
- 검증: 작업자 pytest11개·Ruff·strict mypy, 감사 fixture29개와 raw8개·112pins·원자료 회계·전체 관측 위험 독립 검토 통과. local main 검사는 병합 후 기록한다.

- 병합 직전 main: 3e88c352ab55d4ce5be1278ac1520b6b6b284515. 첫 통합: 67a8a81499a6c1f44cd4c501edf54fd4f463d445.
- 첫 통합 검사: pytest92개와 Ruff 통과. strict mypy에서 새 테스트의 _market_time helper 타입 주석 누락 1건이 발생해 정리를 보류하고 동일 Luna에 수정 요청했다. 실패 로그는 audit/integration/mypy-initial-failure.log로 보존한다.

- 통합 검증 복구: 동일 Luna의 타입 주석 수정 8ce05b5를 독립 검토 후 병합했다. 최종 코드 통합 99a7e8506cd6f379014ce2037f2753fdc4dfca23. 영향 테스트11개 재검사·명시적 strict mypy·Ruff·diff 검사 통과. 기존 통합 pytest92개 결과와 함께 보존한다.
- 웹 게시: 기존 이력76개·artifact122개 보존. 보고서 SHA9be03de33391eb2bb1546f26784c46c875785c4b115e0d313fe014090d78f529. API·웹·두 다운로드200과 본문 SHA 일치. DB 변경 없음.
- 보호 검증: 기존 코드·설정303파일과 입력audit333파일 모두 SHA 일치. 실험코드92모듈과 테스트·문서·환경·실패 및 원장 기록을 영구audit로 복사했다.
- 상태: 통합 검증·게시 완료, 영구handoff 및 SHA 확인 후 이번 worktree 정리 대기.

- 상태: 완료. 영구 증거420개와 정리 전 handoff SHA를 검증한 후 이번 worktree·브랜치를 강제 옵션 없이 제거했다. 정리 후 같은420파일이 모두 생존하고 해시가 일치함을 다시 확인했다. 기존 미병합4개와 root HANDOFF.md는 유지했다.
- 최종 handoff: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-residual-cash-risk-proxy-v1-abecaf881ae842378d77d5a6838040ed/HANDOFF.md. 정리 증거는 같은 경로의 cleanup.json, 완료 근거는 archive-sha256.json과 completion.json이다.


## portfolio-expanded-collection-2ea6

- 상태: 완료 (수집·검토·통합 완료, 데이터 gate 8개 미통과로 실제 비교는 차단)
- 목표와 완료 조건: 기존 A/B 사전등록을 유지하고 공식 자료 수집·검증을 한 차례 수행하여 gate별 결손을 보고합니다. 독립 검토, 필요한 main 통합, 영구 evidence/handoff 보존과 정리를 완료합니다.
- 담당 Luna: 단일 gpt-5.6-luna code 작업자.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-expanded-collection-2ea6
- 작업 브랜치: docs/portfolio-expanded-collection-2ea6
- 기준 커밋 SHA: 02d802e76a9f265e3a38b27de1ddedcb47b4be4c 이후 이 등록 커밋.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: completion ac14fb4d2df2c1f9614136c14a3f2704ff3e634fdc9021e20327e814a70f07a2 및 모든 evidence/source 해시 검증 완료. explore 완료, bounded plan 후 배정.
- 수정 허용 범위: 수집 연구 스크립트와 관련 검사, 한국어 준비도 보고서만 허용합니다. 기존 전략/registry/mandate/PAPER 수정은 금지합니다.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 전용 venv/tmp 및 /home/kwl/.local/share/jusik/portfolio-audit/portfolio-expanded-universe-collection-gates-v1-2ea67734308a40eda685c1b0839576c6.
- 검증: 고정 입력 해시, 가격·배당·분할·FX·세금·캘린더·venue·coverage gate, 관련 pytest/Ruff/strict typing, 독립 검토.
- 제한: 수집 한 차례, simulation/sweep/GPU/주문/remote push 없음. 원천 또는 entitlement 결손 시 비교를 차단합니다. 기존 HANDOFF와 다른 worktree를 보존합니다.
- 결과 커밋/통합/정리/handoff: 진행 후 기록합니다.

- 담당 결과: Luna `cfc751dc5e3f9484ae9c5b019e78d4d4c435cc78`, Astra 독립 review 승인 후 통합했습니다.
- 병합 직전 main: `2c059be53d92a0b51d177a5606a4602e24d75185`; 통합: `c7dcd0d888243287cec6bd1c904923ff86aa8b37`.
- 검증 결과: main pytest42개·offline 실패 회귀5개·Ruff·strict mypy3개 스크립트·diff 통과. 기존 dependency 경고2개.
- 수집 결과: 공식 HTTP10회, IVV 배당12건·SGOV36건 검증. 가격 추출0건, FX 빈 응답, calendar302. baseline 기업행동/IPO·split completeness·세금·venue 미확인으로 모든 데이터 gate 차단, 비교/simulation0회.
- 검토 수정: 배열 길이·실제 오류 기반 pass 판정, raw hash 실패 종료, 가격 결손 범위·mandate 구분을 수정했습니다. 최초 수집기 source hash 누락은 null로 공개했습니다.
- 게시: 연구 이력 파일 게시, API/웹200·SHA 일치. 기존 항목77개·artifact123개 보존. DB·서비스 변경 없음.
- 보존·정리: audit에 handoff 포함303개 파일의 SHA를 검증한 뒤 이번 worktree와 전용 브랜치를 정상 제거했습니다. 기존 worktree와 root HANDOFF 보존.
- handoff: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-expanded-universe-collection-gates-v1-2ea67734308a40eda685c1b0839576c6/HANDOFF.md`.
- 통합 검증 실패 없음. completion은 자료 결손으로 blocked, comparison followup은 null입니다.

## portfolio-gross-cap-2643

- 상태: 완료
- 목표와 완료 조건: gross .60/.80 고정 민감도, 대조군16 exact replay 후 신규16. CPU32회/19.058726초, 재시도0, GPU0으로 완료했습니다.
- 담당 Luna: code 작업자1명, 조사·계획·독립 검토는 별도 읽기 전용 작업자.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-gross-cap-2643 (증거·SHA·handoff 보존 후 제거)
- 작업 브랜치: feat/portfolio-gross-cap-2643 (병합 확인 후 제거)
- 기준 커밋 SHA: c77a186 (작업 등록 포함)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: cost3 f9aecd54 experiment, 최신 mandate; 원천·engine/helper/manifest/mandate69개 SHA 일치. 기존16종목 실제 coverage 및 eligibility 고정.
- 수정 허용 범위: 신규 gross-cap 연구 runner, 해당 테스트, docs/research/portfolio-gross-cap-cash-sensitivity-v1.md. 기존 backend source93개 불변.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 독립 worktree venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-gross-cap-cash-sensitivity-v1-2643020d4e374d5699187071f552d34d.
- 실행기 확인: task/attempt portfolio-gross-cap-cash-sensitivity-v1 / 2643020d4e374d5699187071f552d34d. dispatcher 상태 변경 없음. 기존 HANDOFF.md와 다른4개 worktree 보존.
- 검증 명령과 결과: worker 최종60pytest/Ruffcheck·format/strictmypy2파일 통과(전체 타입 무시 제거). main 통합86pytest/Ruffcheck·format/strictmypy2파일 통과. 독립 raw32·대조군 JSON16·manifest72 SHA 통과. raw 금액 최대잔차3.21875e-31 KRW.
- 결과 커밋 SHA: e2eb919d57adbf8b6c6a08333145c5b46c01ad43
- 검토 결과와 남은 문제: 최종 독립 review 통과. Historical PIT·배당·receipt·early-close 한계 유지, 추가 연구와 정책 승격 없음.
- 결과: continuous 평균 현금은 비용1x/3x에서 +0.044545/+0.010027 pp, 순수익 -0.314952/-0.100381 pp. MDD·비용은 소폭 감소, 거래수 동일. 현금 대기 감소를 확인하지 못한 결과로 종료했습니다. Fold와 continuous 분리. NVDA symbol cap 초과223 valuation 관측, gross/leveraged 초과0.
- 병합 직전 main SHA: c77a186
- 통합 커밋 SHA와 정리 여부: 6f9778508154488e5b46682ecde88f7f2ecc5787, main 검증과 archive-before-cleanup.json·handoff 보존 후 worktree/branch 제거.
- 통합 검증 실패 원인과 복구 결과: 통합 검사는 모두 통과. 초기 worker 잘못된 명령 경로 로그는 실패로 보존하고 올바른 경로에서 최종 검사했습니다. 게시 seed의 Pydantic timestamp 정규화는 원본 값으로 복구 후 기존 항목 보존을 검증했습니다.
- 게시: API/웹/다운로드200과 보고서SHA 일치. 기존 이력78개·artifact124개 원본 보존, DB 변경 없음.
- handoff 저장 경로와 갱신 여부: audit/handoff-before-cleanup.md 및 handoff-final.md, 영구 보존 완료.

## portfolio-volatility-5171

- 상태: 완료
- 목표와 완료 조건: volatility .10/.15, 고정 gross .60 CPU exact32회/900초; control16 JSON 일치 후 variant16, 독립 검토 및 local main 통합 검증.
- 담당 Luna: code 작업자 한 명.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-volatility-5171
- 작업 브랜치: feat/portfolio-volatility-5171
- 기준 커밋 SHA: ae87254ea79c6944da2a422be2b5020eae3aa48e (등록 커밋에서 worktree 생성)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: gross-cap 2643020d experiment 및 최신 mandate. 86개 SHA 검증 통과.
- 수정 허용 범위: 새 volatility 연구 runner/test/보고서만.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. worktree 전용 venv/tmp; audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-volatility-target-cash-sensitivity-v1-51714e900b9b4cd3b94a4cf0f1aae2f4.
- 검증 명령과 결과: main pytest103개(기존 dependency 경고2개), Ruff check/format, strict mypy2파일, diff 통과. worker 전체112 및 최종 대상103개 통과.
- 결과 커밋: c6244b284d0278c5f548964a7fa708cf03cf48c2. 독립 실행 전 및 결과 review 통과.
- 병합 직전 main: 9498876485b01bd12d5a296e76c6a255cb7323e4. 통합 커밋: f38918d3db96b7a749be03ee5ac50d73dc85b9b0. 통합 실패 없음.
- 결과: control16 전체 JSON 일치 후 variant16, CPU exact32회/19.086222초/재시도0/GPU0. Continuous 현금7.641445/7.744083pp 감소, 순수익11.423940/9.100226pp 증가, MDD3.925490/4.147701pp·비용841623/2483668 KRW 증가. 거래수5/4회 감소, turnover 증가. 추가 탐색·승격 없음.
- 독립 검증: raw32 회계 최대잔차3.21875e-31 KRW, manifest72 SHA·observer MDD·paired delta 통과. 최대 MDD10.414050%, symbol 초과463 valuation, 최대MSFT3.131096pp; gross/leverage 초과0. Historical PIT/짧은 ETF 이력/배당·receipt·early-close 한계 유지.
- 검토·환경 보완: helper 중복 제거, gross metadata 및 pre/post SHA 기준·deadline 실패기록 보호 복원, 실제 mutation/휴장 영향 거래 회귀 추가. 초기 Python3.12/기준 venv 사용 로그는 보존했고 전용3.13에서 최종 검사. Worker의 초기 branch commit 재작성은 검토 기록에 남겼으며 이후 append-only 수정. Root main 이력 재작성 없음.
- 게시: API/웹/다운로드200, 보고서 SHA 일치. 기존 이력79개/artifact125개 보존. DB·서비스·remote 변경 없음.
- 보존·정리: 소스/로그/결과/handoff134파일 SHA 검증 후 이번 worktree·브랜치 정상 제거. 기존 backend93개/root HANDOFF/다른4개 worktree 보존.
- handoff: audit/handoff-before-cleanup.md 및 handoff-final.md. archive-before-cleanup.json 및 cleanup.json으로 보존·정리 확인.
- 실행기: 현재 task/attempt dispatch 내 작업이며 dispatcher 상태 변경 없음. 기존 HANDOFF 및 다른 worktree 보존.

## portfolio-volatility15-cadence-4c25

- 상태: 차단 — 이전 시도 중단. 후속 5270 시도에서 완료했으며 기존 worktree는 보존합니다.
- 목표와 완료 조건: target .15 고정 4/8주 CPU exact32회/900초 비교, control16 전체 JSON replay 후 variant16, 독립 회계 및 검토, local main 통합 검사와 handoff.
- 담당 Luna: code 작업자 한 명.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-volatility15-cadence-4c25
- 작업 브랜치: feat/portfolio-volatility15-cadence-4c25
- 기준 커밋 SHA: f630332562a97b9dd916b03f9b4f65fcb401ed77 (등록 커밋에서 worktree 생성)
- 통합 대상 브랜치: local main
- 입력: volatility target 51714e90 experiment; evidence5/manifest72/source3 SHA 일치.
- 수정 허용 범위: 새 연구 runner/test/report. PAPER/제품/DB/설정/주문/remote/GPU 변경 금지.
- 격리: 전용 worktree venv/tmp, 서버/DB 없음. durable audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-volatility15-cadence-cost-tradeoff-v1-4c25334c49c2491b8e74d9e16d63dda2.
- 실행기: 해당 task/attempt dispatch 내 작업. dispatcher 상태 변경 없음. 기존 HANDOFF와 다른4개 worktree 보존.
- 검증과 결과: 실행 전.

## portfolio-volatility15-cadence-5270

- 상태: 완료
- 목표와 완료 조건: .15 고정 4/8주 CPU exact 32회/900초 비교, 대조군 16개 전체 JSON 일치 후 변형군 16개, 독립 회계·검토 및 local main 통합 검사 완료.
- 담당 Luna: code 한 명. Astra가 단 한 번의 historical 실행과 통합을 담당했습니다.
- 워크트리와 브랜치: /home/kwl/projects/jusik-portfolio-volatility15-cadence-5270, feat/portfolio-volatility15-cadence-5270. 통합 검증·영구 보존 후 정상 제거했습니다.
- 기준 커밋 SHA와 통합 대상: cdaa6f72f8ef6396246c3c616948dfd3d26eaf09, local main.
- 입력과 선행 작업: 선행 volatility-target variant_c1/c3 16개. 입력 SHA 80개 일치. 이전 시도 4c25의 중단 worktree 및 기존 다른 4개 worktree와 root HANDOFF를 보존했습니다.
- 수정 범위: 새 연구 runner/test/report 3개. PAPER/제품/DB/설정/주문/remote/GPU 변경 없음. 서버/DB 미사용, 전용 venv/tmp 사용.
- 결과: CPU exact32회/18.251010초/재시도0/GPU0. Control16 byte 및 전체 JSON 일치 후 variant16. Continuous 비용1/3배에서 현금+0.607432/+0.608667pp, 순수익-5.551477/-1.999894pp, MDD+5.315978/+5.088576pp, 거래수-134/-140, 총비용-1102154/-3081364 KRW. Fold14개와 continuous2개 분리, 재튜닝·승격 없음.
- 독립 검증: raw32 최대 회계잔차1.734375E-31 KRW. manifest72 SHA, runtime95 SHA, observer 현금/MDD/cap 재계산 통과. Symbol 초과351개는4주에만 관측,8주0; gross/leveraged0.
- 검증 명령과 결과: Astra 실행 전 및 통합 후 pytest99개, Ruff check/format, strict mypy 통과. 프런트엔드 코드 변경 없음. 최초 Astra 검사도구의 tmp 상위 폴더 누락은 수정 후 통과했고 실패 로그 보존.
- 검토: 독립 코드·수치·보고서 검토 통과. 초기 helper SHA 오타·preregistration·실패 중단/경계 테스트 누락은 실행 전에 같은 Luna가 수정했습니다. Historical 실패·재시도 없음.
- 작업자 최종 커밋: b165bbb2292c32f8c66fcae9c310cf1dfb634111. 병합 직전 main: cdaa6f72f8ef6396246c3c616948dfd3d26eaf09. 통합 커밋: 114232eadcc4cac4e66cf14c267f518acdcf4c2a.
- 게시: 기존 file history와 progress catalog에 보고서 및16개 비교를 추가했습니다. 기존 항목과 대표 비교 보존, API/웹/다운로드200 및 보고서 SHA 일치. DB·서비스 변경 없음.
- 영구 보존: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-volatility15-cadence-cost-tradeoff-v1-527025c895ad4d54a9559469434162a8. 삭제 전147개 증거/SHA/handoff 검증, 삭제 후 전부 재검증 및 runtime95개 대체 영구 경로 검증.
- handoff: audit/handoff-before-cleanup.md와 audit/handoff-final.md. 실행기 dispatch 안에서 완료하며 dispatcher 상태는 변경하지 않았습니다.

## progress-api

- 상태: 완료
- 목표와 완료 조건: 자동 개발 상태·종료 조건·같은 조건의 성과 비교·남은 작업을 한눈에 확인하는 읽기 전용 웹 화면을 구현하고 실제 웹에서 검증합니다.
- 담당 Luna: 작업별 CLI Luna 한 명. 조사와 계획을 완료했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-progress-api
- 작업 브랜치: feat/progress-api
- 기준 커밋 SHA: e878263 이후 이 등록 커밋
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 공통 API 계약 /tmp/jusik-progress-contract.md. 공개 비교 catalog는 감독이 실제 근거를 검증해 준비합니다.
- 수정 허용 범위: backend/jusik/research_progress.py, research_app.py 연결, 대응 테스트, docs/research-progress.md. 실행기·거래·원장 변경 없음.
- 포트·테스트 DB·출력 경로: 작업별 가상환경·의존성·임시 데이터·빌드. 실제 배포와 공개 catalog는 감독 소유.
- 검증 명령과 결과: main 관련 pytest 27개, Ruff check/format 및 strict mypy, frontend lint/typecheck/build 통과. 독립 검토 P1/P2 없음. 실제 데스크톱·모바일 표시, 10초 갱신, 보고서 3개 다운로드·SHA 일치 확인. 기존 환율/mandate 테스트 실패 2건은 별도 큐로 등록했습니다.
- 결과 커밋: a395ee3, a3b144b. 통합 커밋: f04d671. 검증·환경·diff·화면 자료를 audit에 보존한 후 이번 워크트리와 브랜치를 정상 제거했습니다. 기존 미완료 워크트리 5개는 보존합니다.
- 게시: /research/progress 및 /api/research/progress 실제 HTTP 200. 공개 catalog 3개 연구·8개 비교와 개발 이력 게시 완료. PAPER·실제 거래·remote 변경 없음.
- 통합 검증 실패: 최초 브라우저 실행은 libasound 부재로 실패하여 별도 임시 라이브러리를 사용했습니다. 표시값 절삭을 반영한 검증 후 통과했습니다.
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260913T053914Z-progress-dashboard/HANDOFF.md

## progress-ui

- 상태: 완료
- 목표와 완료 조건: 자동 개발 상태·종료 조건·같은 조건의 성과 비교·남은 작업을 한눈에 확인하는 읽기 전용 웹 화면을 구현하고 실제 웹에서 검증합니다.
- 담당 Luna: 작업별 CLI Luna 한 명. 조사와 계획을 완료했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-progress-ui
- 작업 브랜치: feat/progress-ui
- 기준 커밋 SHA: e878263 이후 이 등록 커밋
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 공통 API 계약 /tmp/jusik-progress-contract.md. 공개 비교 catalog는 감독이 실제 근거를 검증해 준비합니다.
- 수정 허용 범위: frontend/lib/research-progress.ts, app/research/progress/, CSS, research/history 진입 링크. 실행기·거래·원장 변경 없음.
- 포트·테스트 DB·출력 경로: 작업별 가상환경·의존성·임시 데이터·빌드. 실제 배포와 공개 catalog는 감독 소유.
- 검증 명령과 결과: main 관련 pytest 27개, Ruff check/format 및 strict mypy, frontend lint/typecheck/build 통과. 독립 검토 P1/P2 없음. 실제 데스크톱·모바일 표시, 10초 갱신, 보고서 3개 다운로드·SHA 일치 확인. 기존 환율/mandate 테스트 실패 2건은 별도 큐로 등록했습니다.
- 결과 커밋: 431ac8b, ef7e9b4, fb3989c. 통합 커밋: 7e8e498. 검증·환경·diff·화면 자료를 audit에 보존한 후 이번 워크트리와 브랜치를 정상 제거했습니다. 기존 미완료 워크트리 5개는 보존합니다.
- 게시: /research/progress 및 /api/research/progress 실제 HTTP 200. 공개 catalog 3개 연구·8개 비교와 개발 이력 게시 완료. PAPER·실제 거래·remote 변경 없음.
- 통합 검증 실패: 최초 브라우저 실행은 libasound 부재로 실패하여 별도 임시 라이브러리를 사용했습니다. 표시값 절삭을 반영한 검증 후 통과했습니다.
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260913T053914Z-progress-dashboard/HANDOFF.md


## baseline-fx-mandate-test-repair-56e8

- 상태: 완료
- 목표와 완료 조건: 기존 mandate 기대값과 FX 날짜 fixture 실패 2개를 테스트 범위에서 수정합니다. 독립 검토, local main pytest·Ruff·mypy, 한국어 개발 이력과 handoff, 근거 보존 후 정리까지 수행합니다.
- 담당 Luna: 전용 Luna 구현 작업자 1명(/root/luna_fix). 읽기 전용 explore와 plan을 순서대로 완료했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-baseline-fx-mandate-56e8
- 작업 브랜치: fix/baseline-fx-mandate-56e8
- 기준 커밋 SHA: a42ab7db0a04110ae9a68dc049c03fe1252098f3
- 통합 대상 브랜치: local main
- 입력과 선행 작업: task baseline-fx-mandate-test-repair-v1, attempt 56e8f44c391947c7bc03f7a891c67f0a. 현재 main에서 지정 테스트 2개 실패를 재현했습니다. 이번 attempt만 running이며 실행기 상태는 변경하지 않습니다.
- 수정 허용 범위: backend/tests/test_development_runner_planning.py, backend/tests/test_fx_signals.py. 운영 코드와 research-mandate.json 변경은 필요하지 않습니다.
- 포트·테스트 DB·출력 경로: 서버와 운영 DB 미사용. 워크트리 자체 .venv와 pytest 임시 데이터 사용. 영구 audit: /home/kwl/.local/share/jusik/portfolio-audit/baseline-fx-mandate-test-repair-v1-56e8f44c391947c7bc03f7a891c67f0a.
- 검증 명령과 결과: 수정 전 지정 pytest 2개 실패. 수정 후 FX·runner·planning·FX provenance pytest, Ruff check/format, strict mypy를 실행합니다. ML·전략 실험·GPU·PAPER·실거래·서비스·원격 변경 없음.
- 검토 결과와 남은 문제: FX 5일 초과 자료 차단은 정상입니다. 테스트 UTC 시계 고정과 Decimal 양·음수·0 반올림, UTC 자정의 5일/6일 경계, mandate 현재 의미와 추가 필드 보존을 검증합니다.

- 결과 커밋 SHA: 634a238157b643fe0a38fa25a308e45533bc3009 및 검토 수정 4ad94d56fbbfd188a7101bd944d94c55b4f8bb42.
- 검토 결과: 독립 pytest 32개, 변경 테스트 strict mypy 및 Ruff 통과. 테스트 datetime override 반환형 오류 1건은 Self 반환으로 수정했습니다.
- 통합 검증: main 관련 pytest 95개, 백엔드 전체 Ruff check/format(160개), strict mypy jusik(96개) 및 변경 테스트(2개) 모두 통과했습니다.
- 환경 제한: 최초 시스템 Python 3.12 ensurepip 실패 후 전용 Python 3.13 환경을 생성했습니다. 기본 lock의 선택 torch 누락으로 전용 환경 전체 mypy만 실패했으나 관련 pytest 95개와 변경 테스트 mypy는 통과했고 기존 main 환경 전체 mypy도 통과했습니다. ML 설치나 전략 실험은 하지 않았습니다.
- 병합 직전 main SHA: a42ab7db0a04110ae9a68dc049c03fe1252098f3.
- 통합 커밋 SHA와 정리 여부: 84225358236dc30573a684ad30bb3dbf609322f9. 삭제 전에 영구 audit의 근거 42개·SHA·handoff를 검증하고 이번 워크트리와 병합 브랜치를 정상 제거했습니다. 삭제 후 42개 해시를 재검증했습니다. 기존 워크트리 5개는 보존했습니다.
- 게시: 한국어 개발 이력을 기존 file history에 추가했습니다. API·웹·보고서 다운로드 HTTP 200과 보고서 SHA를 검증했습니다. 기존 항목과 성과 catalog를 유지했으며 새 성과 수치는 없습니다.
- 통합 검증 실패 원인과 복구 결과: 통합 검증 실패 없음. 구현 단계 타입 오류 및 선택 의존성 제한은 위에 기록했습니다.
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/baseline-fx-mandate-test-repair-v1-56e8f44c391947c7bc03f7a891c67f0a/HANDOFF.md. 삭제 전 handoff-before-cleanup.md도 별도로 보존합니다.


## portfolio-symbol-cap-episodes-0e01

- 상태: 준비
- 목표와 완료 조건: 저장된 32개 셀의 symbol cap 초과 관측 351회를 종목별 episode로 재구성하고 같은 셀의 비용 반영 성과와 연결합니다. 입력 SHA 검증, 분석 1회와 결정성 재검산 1회, 독립 검토, local main 통합 검사와 영구 handoff를 완료합니다.
- 담당 Luna: 전용 Luna 구현 작업자 1명. explore 완료 후 plan을 진행합니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-symbol-cap-episodes-0e01
- 작업 브랜치: feat/portfolio-symbol-cap-episodes-0e01
- 기준 커밋 SHA: 93bddaf9db7214331a8e363b95bbf9c6f8b8e4df 이후 이 등록 커밋
- 통합 대상 브랜치: local main
- 입력과 선행 작업: task portfolio-symbol-cap-breach-episodes-v1, attempt 0e018f57a6b14e3587dc5dfca65985d8. 선행 mandate/report/results/manifest 4개 및 manifest 72개 파일 SHA 일치. 자동 실행기의 현재 시도이며 서비스나 큐를 변경하지 않습니다.
- 수정 허용 범위: 새 분석 모듈, 해당 fixture tests, 한국어 연구 보고서와 전용 audit. 감독만 이 등록부를 갱신합니다.
- 포트·테스트 DB·출력 경로: 포트와 DB 미사용. 워크트리 자체 Python 3.13 venv. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-symbol-cap-breach-episodes-v1-0e018f57a6b14e3587dc5dfca65985d8.
- 검증 명령과 결과: 관련 pytest, Ruff check/format, strict mypy. 32셀 CPU 분석 1회와 결정성 재검산 1회 합계 900초 이내. Historical simulation·수집·GPU·후보 탐색 0회.
- 검토 결과와 남은 문제: 원본 배열 순서를 보존하며 동일 UTC 시각과 동일 값의 정상 반복도 유지합니다. 거래와 관측의 동일시각 선후 및 관측 사이 회복은 추정하지 않습니다. 기존 PAPER10%, 사용자 MDD20%·레버리지20%, 1억원·인출 없음과 짧은 이력/PIT 한계를 보존합니다.

## investor-web

- 상태: 완료
- 목표와 완료 조건: 일반 투자자가 목표·현재 단계·성과 의미·한계·다음 판단을 이해하는 통일된 웹 여정을 구현합니다. 실제 브라우저와 독립 과제 검토 후 local main 통합·배포·handoff까지 완료합니다.
- 담당 Luna: frontend 구현 담당자 한 명. Astra는 설계 기준·통합·검증·배포 담당입니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-investor-web
- 작업 브랜치: feat/investor-web
- 기준 커밋 SHA: f981fa9
- 통합 대상 브랜치: local main
- 입력과 선행 작업: docs/investor-web-design.md, 기존 research progress API 및 연구 화면. explore와 plan 검토를 완료했습니다.
- 수정 허용 범위: frontend의 연구 홈·공통 탐색·성과/관찰/이력 설명·기존 연구 도구 이동·계좌 화면의 연구 안내. 전략·백엔드·주문·인증·공개 성과 수치 변경 없음.
- 포트·테스트 DB·출력 경로: 전용 node_modules 및 build, 임시 fixture 8311/프런트 3311. 운영 서버 변경은 Astra만 수행합니다.
- 검증 명령과 결과: main lint/typecheck/build, Decimal 비교 회귀 9건, 실제 8개 화면 HTTP 200·현재 메뉴 1개·desktop/mobile 가로 넘침 없음·키보드 본문 이동 통과. 실제 Next/브라우저에서 자료·운영 상태 6개 검증, 폼 8개·입력 필드 20개·서버 액션 보존 대조 통과. 독립 화면 과제 7개 확인; 실제 일반인 참가 시험은 수행하지 않았습니다.
- 결과 커밋: e7420ff, 24faf18, 976e58d, dfd09f6. 통합 커밋: 52cfb86 및 1f4f4be. 독립 검토 P1/P2 해소 후 통합, 실제 웹 배포 완료.
- 검토 및 복구: 초기 모바일 넘침, 후보 단독 수치, 공통 탐색 누락, 잘못된 상태 단정, 현재 메뉴 중복, 상세 링크 누락을 같은 Luna가 수정했습니다. 최초 실패와 최종 통과 근거를 audit에 보존했습니다.
- 정리: diff·환경·검증 스크립트·화면·인계 자료를 audit에 보존한 후 이번 워크트리와 브랜치를 정상 제거했습니다. 기존 6개 미완료 워크트리는 보존했습니다.
- 게시: /research를 시작점으로 웹 반영 및 개발 이력 게시 완료. 공개 성과 catalog SHA 불변, 계좌 조회·인증·거래 로직 변경 없음. 원격 push 없음.
- 운영: 사용자 요청으로 runner paused, service/timer inactive. 완료 후에도 자동 재개 금지. 기존 중단 작업과 6개 워크트리 보존.
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260913T072036Z-investor-web-remake/HANDOFF.md


## research-ui-redesign

- 상태: 완료
- 목표와 완료 조건: research-ui-redesign.md의 사용자 요구를 바탕으로 전체 목표·운용 조건, 연구 질문·변경점·결론·결정, 별도 PAPER 관찰을 이해할 수 있게 화면을 재설계합니다. 기존 기능과 URL을 보존하고 독립 검토, 브라우저 검증, local main 통합 검사와 handoff까지 완료합니다.
- 담당 Luna: /root/luna_ui (gpt-5.6-luna), 구현 소유자 한 명. explore와 plan 완료.
- 워크트리 절대 경로: /home/kwl/projects/jusik-research-ui-redesign
- 작업 브랜치: feat/research-ui-redesign
- 기준 커밋 SHA: afc2eb4
- 통합 대상 브랜치: local main
- 입력과 선행 작업: docs/research-ui-redesign.md(사용자 미추적 원본 보존), 최신 mandate, 기존 화면/API/공개 연구 원문. 자동 실행기는 paused, service/timer inactive이며 중지를 유지합니다.
- 수정 허용 범위: frontend 연구 화면·표시용 데이터·CSS·관련 검사. 전략·주문·PAPER 정책·공개 성과 수치 변경 없음.
- 포트·테스트 DB·출력 경로: 전용 node_modules/build, frontend 3321 및 fixture 8321, 운영 DB 미사용. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260913-research-ui-redesign.
- 검증 명령과 결과: worker와 main의 lint/typecheck/build 통과. main 실제 Next 브라우저 44개 상태·화면 폭 검사, 비율 변환 12건·원본 식별 20건 통과. 배포된 8개 화면 HTTP 200, desktop/mobile 가로 넘침 없음, 공통 탐색·현재 메뉴·키보드 이동·JavaScript 오류 없음 확인. 기존 연구 도구 파일 9개와 공개 성과 catalog SHA 보존.
- 결과 커밋 SHA: 6aeff89, e891675. 초기 중간 커밋 cc3efff는 작업자가 정리했으며 최종 두 커밋을 통합했습니다. 감독 요청 후 후속 수정은 별도 커밋으로 보존했습니다.
- 검토 결과와 남은 문제: 독립 review의 관찰 검증 기간 누락, 낙폭 측정 기준 혼합, 고정 연구 수, 전체 기간 계산 오류와 브라우저 가로 넘침을 수정했습니다. 최종 독립 review 중요 지적 없음. 실제 일반인 참가 사용자 시험은 수행하지 않았습니다.
- 병합 직전 main SHA: 2ee48a8be641f92eacb68b664a547ae447de1402.
- 통합 커밋 SHA와 정리 여부: fbf97e01429e07e2d2ab5b77911864cd6c3f74ba. 웹 반영 및 통합 검증 후 audit 파일 123개 SHA를 확인하고 이번 워크트리와 병합 브랜치를 정상 제거했습니다. 기존 미완료 워크트리 6개 보존. 자동 실행기 paused, service/timer inactive 유지.
- 통합 검증 실패 원인과 복구 결과: main 통합 검사 실패 없음. 초기 개발본의 모바일·비교 상세 넘침과 정보 표시 오류는 독립 리뷰 후 수정했습니다. 브라우저 실행에 필요한 기존 공유 라이브러리를 LD_LIBRARY_PATH로 지정했으며 새 시스템 패키지는 설치하지 않았습니다.
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260913-research-ui-redesign/HANDOFF.md. 루트 HANDOFF.md에 최신 안내를 추가하며 기존 내용과 미추적 요구사항 원본을 보존합니다.


## open-ended-decision-study

- 상태: 완료
- 목표와 완료 조건: 종료 시점 없는 계속 운용과 실제 비교 후 사용자 선택이라는 최신 의사를 기록하고, 고정된 4주 대 8주 연구 32개 결과를 재분석해 선택 근거를 제공합니다. PAPER 준비와 미완료 7건을 읽기 전용 점검하고 연구 한 건 후 중지합니다.
- 담당 Luna: /root/luna_decision (gpt-5.6-luna), 구현 소유자 1명. explore·plan·구현·독립 review 완료.
- 워크트리 절대 경로: /home/kwl/projects/jusik-open-ended-decision-study
- 작업 브랜치: feat/open-ended-decision-study
- 기준 커밋 SHA: ed2ae9afff0e60dd59bef8d33d715e087997fb39 이후 이 등록 커밋
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 사용자 1-D 및 2-C 선택. 고정 volatility15-cadence 5270 결과와 manifest. 실제 경계 capture monitor running, 두 경계 scheduled 및 코드 hash 일치. runner paused와 service/timer inactive.
- 수정 허용 범위: 최신 mandate JSON·한국어 안내·해당 테스트, 웹의 현재 조건 표시, 단일 재분석 보고서 및 전용 audit. 전략·PAPER·운영 DB·runner 큐 변경 없음. 감독만 등록부와 공개 catalog를 관리합니다.
- 포트·테스트 DB·출력 경로: 전용 Python 3.13 venv와 node_modules/build. 필요시 웹 3331. 운영 DB 읽기 전용, 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260913-open-ended-decision-study.
- 검증 명령과 결과: 관련 pytest·Ruff·strict mypy, frontend lint·typecheck·build, Decimal 재분석과 독립 검증, 원본 SHA·기존 catalog 보존.
- 종료 조건: 32개 저장 셀과 16개 쌍만 분석·재검산하며 historical simulation·새 후보·GPU 실행 0회. local main 통합 검사, 한국어 보고서·같은 조건 catalog 게시, handoff·이번 worktree 정리 후 중지합니다.
- 남은 문제: 일부 원자료의 짧은 이력·PIT·배당·세금 한계를 유지합니다. 실거래나 기존 PAPER 정책에 후보를 채택하지 않습니다.
- 결과 커밋 SHA: a44d402b8c7570c8e48601b86f3f6bbb4c7c42b9, 360cec03be18eb7d3d2ad68bbbf667e18587d094.
- 병합 직전 main SHA: 532450a. 통합 커밋 SHA: 7ed18c1af7919925d06176adad9e330eb66d8ebf.
- 검증 결과: worker와 main pytest 52개, 관련 Ruff·strict mypy 및 frontend lint·typecheck·build 통과. 원본 SHA 72개·raw 32셀·paired 16쌍·catalog 32개 수치 행 독립 검산 통과. 실제 브라우저 2개 화면×2개 너비, 다운로드 2개 SHA·API·PAPER raw collector 실행과 예약 확인.
- 검토와 복구: 공개 중단 후 재실행 불가와 오래된 보고서 sourceReference를 수정했습니다. 임시 공개 디렉터리에서 실패 주입·복구·완료 후 동일 재실행을 확인했고 독립 재검토 추가 P1/P2 없음. 초기 브라우저 검사 selector의 study 접두사를 실제 DOM에 맞춰 고친 뒤 4개 화면 검사가 통과했습니다.
- 게시: cadence-decision-20260913 신규 study·16개 비교와 한국어 보고서 공개. 기존 study 4개 및 featured 비교 보존. runner 전체 snapshot·기존 7건 상태 불변, paused와 service/timer inactive 유지. 웹은 실행 중입니다.
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260913-open-ended-decision-study/HANDOFF.md. 기존 6개 미완료 워크트리 및 이번 작업 중 별도 등록된 jusik-agent-tooling 워크트리는 이번 정리 대상에서 제외합니다.
- 정리: 검증·구현 diff·환경 정보·보고서 등 audit 41개 파일의 SHA를 확인한 뒤 이번 워크트리와 병합 브랜치를 정상 제거했습니다. 다른 작업의 등록 내용과 워크트리는 보존했습니다.
