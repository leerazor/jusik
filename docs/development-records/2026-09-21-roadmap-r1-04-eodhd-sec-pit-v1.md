# R1-04 EODHD·SEC 증거 경계

## 이전 attempt: 세션 마감으로 구현 전 중단

- 상태: 차단. Task `roadmap-r1-04-eodhd-sec-pit-v1`, attempt `cd71193683a14c5596f60728189bc0fa`.
- 기록 시각: 2026-09-21T04:04:43.971062+00:00
- 기준 커밋: `a5eaecfd5c341b126f6ec5baf47ed8d068cc83da`. 구현 및 통합 커밋은 없습니다.
- 범위: 미국 기업행사 evidence adapter 또는 focused fixture 한 slice.

## 변경과 결정

시스템 UTC 시각과 현재 tracked `docs/continuous-development-session.md`를 대조했습니다. 승인 마감인 2026-09-21 10:29:59 KST가 이미 지났으므로 신규 작업자 배정과 구현을 시작하지 않았습니다. 이번 차단은 코드 결함이나 외부 자료 부족을 새로 확인한 결과가 아니며 자동 복구 label을 지정하지 않습니다.

## 검증과 한계

Git 상태, worktree 목록, 정책 마감 및 R1-04 미체크 상태만 확인했습니다. 테스트·Ruff·타입 검사·독립 review·main 통합 검사는 미실행입니다. 구현 worktree는 생성하지 않았고 정리 대상도 없습니다. 기술 slice는 미완료이며 금융 및 provider coverage 평가는 `not-evaluated`입니다.

## 문서·계약 및 안전 경계

작업 등록부와 이 중단 기록만 갱신합니다. API·설정·데이터 계약 변경은 없습니다. 네트워크 수집·fixture 생성·전략·legacy replay·원장·PAPER/live·주문·서비스·설정·remote push·Windows 종료는 실행하지 않았습니다. 기존 미추적 사용자 `HANDOFF.md`와 다른 worktree를 보존합니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260921-r1-04-eodhd-sec-cd711936/stop-evidence.json`.
- handoff: `/home/kwl/.local/share/jusik/portfolio-audit/20260921-r1-04-eodhd-sec-cd711936/HANDOFF.md`.
- 재개 조건: 새로운 실행 기한 승인 후 현재 상태와 소유 worktree를 다시 확인합니다. Luna 구현, 독립 review, local-main 통합 검사와 durable evidence 보존을 거칩니다.
- 이후 확인할 자료: dividend declaration/record/payment dates, split ratio, retrieval UTC, response SHA-256, 가능한 SEC filing identity/accepted timestamp. 전체 R1-04에는 initial state, fixed price, entitled quantity, effective/payment UTC boundaries, complete symbol/period coverage가 추가로 필요합니다. 이번 시도에서 provider 결측 필드를 실측했다고 주장하지 않습니다.


# 2026-09-21 재개: EODHD·SEC 읽기 전용 증거 경계

- Task: `roadmap-r1-04-eodhd-sec-pit-v1`; attempt: `914a85ba9e31429b82d8b397403da5c8`.
- 새 승인 마감: 2026-09-21 18:30:46 KST. 이전 시도의 시간 만료는 당시 기록으로 보존합니다.
- 상태: 기술 슬라이스 완료. 외부 자료가 필요한 전체 R1-04 및 경제 평가는 계속 `blocked` / `not-evaluated`입니다.
- 기준: `12c2525`; 구현 worktree: `/home/kwl/projects/jusik-r1-04-eodhd-sec-pit`; branch: `feat/r1-04-eodhd-sec-pit`.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260921-r1-04-eodhd-sec-914a85ba/`.

## 확정 범위와 수집 결과

새로운 독립 evidence parser만 추가합니다. 배당 ex/declaration/record/payment date, 조정·비조정 금액, 분할 비율, 원문 응답 SHA-256과 조회 UTC를 분리합니다. SEC는 기존 submissions parser와 filing 모델을 재사용하여 명시적으로 선택한 accession·CIK·hash를 결속합니다. 기존 strategy, legacy replay, action ledger, PAPER/live, brokerage API에는 연결하지 않습니다.

[EODHD 공식 계약](https://eodhd.com/financial-apis/api-splits-dividends)에 따라 JSON `div`와 `splits` endpoint를 사용했습니다. AAPL/BMRC/RWT/ATXG/IMUX의 2025-01-01~2026-09-11 구간에 GET 10회를 실행했고 재시도는 하지 않았습니다. 배당 20건과 분할 2건을 확보했으며 새 원문 응답 10개를 immutable 파일로 저장했습니다. 배당 20건의 declaration/record/payment 날짜는 모두 있었지만 publication timestamp는 응답에 없습니다. 이 구간은 source field audit이며 새로운 backtest 또는 성과 실험이 아닙니다.

기존 SEC cache의 ATXG/BMRC/IMUX/RWT 4건은 review form·filing body·submissions의 accession, CIK 및 SHA-256을 대조했습니다. 접수 UTC는 각각 `2026-03-27T20:15:27Z`, `2025-10-27T12:53:25Z`, `2026-04-23T12:30:43Z`, `2025-09-11T20:15:40Z`입니다. 기존 관측시각도 보존하며 이번 조회시각으로 바꾸지 않습니다. AAPL SEC reference는 이번 범위에서 평가하지 않았습니다.

IMUX의 EODHD split 거래일은 2026-04-27이고 기존 SEC 검토의 법적 효력일은 2026-04-22입니다. 날짜 의미를 합치거나 자정 UTC를 만들어내지 않습니다. SEC 접수시각이 있어도 배당·분할 사실의 PIT 검증이나 전체 coverage를 자동 승인하지 않습니다.

## 자료 차단 조건

`source-gap-audit.json`에 다음 누락을 기록했습니다: EODHD event publication timestamp, complete symbol/period coverage receipt, initial portfolio state, fixed valuation price, entitled quantity, effective UTC boundary, payment UTC boundary. 빈 응답도 “행사 없음” 또는 complete coverage의 증거가 아닙니다. 전체 R1-04 checkbox는 변경하지 않습니다.

## 운영·라우팅 및 예산

현재 runner DB의 running attempt는 이 시도 하나였습니다. 실제 DB의 paused 값은 `0`이므로 세션 문구의 paused 설명을 현재 상태로 재주장하지 않았습니다. systemctl user bus는 접근할 수 없었고, runner-owned child 규칙에 따라 pause·서비스·설정을 변경하지 않았습니다.

첫 read-only explore는 host가 message를 opaque envelope로 기록하여 plaintext post-audit에 실패했습니다. 실패 기록을 유지한 뒤 실제 envelope 구조를 확인하고 문서화된 encrypted-message adapter로 새 read-only explore를 실행했습니다. 새 explore와 plan의 receipt/parent-child/model 검사가 통과했습니다. raw message 무결성을 검증했다고 주장하지 않습니다.

Python 3.13.15의 독립 worktree venv를 requirements.lock으로 준비했습니다. dependency cache가 일시적으로 audit 하위에서 107 MiB를 차지한 사실은 `environment-budget-note.json`에 보존했습니다. cache는 owned worktree로 이동했고, 이후 disposable environment 512 MiB와 durable evidence 20 MB의 별도 prospective budget을 적용합니다. 과거 초과를 소급 승인하지 않습니다. 사용자 fixture·네트워크·CPU 한도는 변경하지 않았습니다.

## 완료 검증

Luna 구현 커밋은 `229dfb7e3061314c32eb05e1bf6d86af75073eaf`입니다. 감독이 별도 `verify_captured_sources.py`로 실제 원문 10개, 배당 20건, 분할 2건, SEC 연결 4건을 검증했고 기존 source 39개 hash가 유지됨을 확인했습니다. 결과는 `supervisor-source-validation.json`에 저장했습니다. 최초 독립 review에서 SEC 관측시각·원시 중복 accession 결함 2건이 확인됐고, 같은 Luna가 `10c4cd589a8800db6a30d64d290d7edace82f01a`에서 수정했습니다. 필수 submissions 관측시각을 분리하고 접수시각을 두 관측시각 모두와 비교하며, 기존 parser가 행을 건너뛰기 전에 원시 accession 수를 검증합니다. 독립 재검토는 PASS입니다.

고정 synthetic raw fixture는 구현 보고 기준 10개입니다. 사용자 상한은 신규 fixed local test fixture 20개이며 네트워크 원문은 별도 source receipt입니다. 추가로 부과했던 synthetic 10 제한은 필수 회귀 검증을 빠뜨리지 않도록 실행 전에 prospective 20으로 정정했습니다. 원본 응답을 테스트 fixture로 복사하지 않았고, 현재 보고된 실제 fixture 수는 이전의 보수적 제한에도 맞습니다.


## 최종 검증·통합·정리

- local main 통합 커밋: `5f250dd3b234d9276d48bc164773bf499252c071`; 병합 직전 `c9390da895f840f0957c5548ef552c1003dc7ddd`.
- main에서 `python -m pytest -q tests/test_research_eodhd_evidence.py tests/test_research_sec_evidence.py tests/test_research_action_review.py tests/test_research_corporate_actions.py tests/test_research_action_collection.py` — 59 passed, 기존 third-party deprecation warning 2건.
- 새 모듈·테스트 Ruff check 및 format check, 새 모듈 configured strict mypy, `git diff --check` — 통과.
- 수정본 및 main에서 실제 원문 10개/배당 20건/분할 2건/SEC 4건과 기존 source 39개 hash 보존 — 통과. `main-source-validation.json`에 전체 정규화 증거를 기록했습니다.
- 기존 테스트 입력 bytes만 계측한 결과 distinct synthetic input 12개였습니다. reviewer의 독립 재현 1개까지 포함해 최대 13/20이며 새 성과 실험이나 추가 네트워크 호출은 없습니다. `fixture-budget-verified.json`을 참조하십시오.
- frontend 변경이 없어 frontend build는 해당 없습니다. full financial acceptance는 실행하지 않았으며 명시적으로 차단합니다.
- code와 review의 parent/child·model·receipt post-audit를 모두 통과했습니다. opaque host mode의 message 무결성은 미검증임을 그대로 기록했습니다.
- `pre-cleanup-manifest.json`에 71개 보존 파일의 hash를 확인한 뒤, 미커밋·미병합 작업이 없는 worktree와 branch를 `--force` 없이 제거했습니다. dependency environment/cache도 해당 worktree와 함께 제거했습니다. 기존 사용자 HANDOFF hash와 다른 worktree를 보존했습니다.
- 최종 handoff: `/home/kwl/.local/share/jusik/portfolio-audit/20260921-r1-04-eodhd-sec-914a85ba/HANDOFF.md`. 최종 hash 목록: 같은 디렉터리 `audit-manifest.json`.

## 문서·계약 및 최종 자료 상태

새 offline adapter의 계약을 `docs/eodhd-action-evidence.md`에 기록했습니다. API·서비스·설정·운영 데이터·기존 결과 계약은 변경하지 않았습니다. 로드맵 파일 자체가 기준 `cb5a700`과 동일함을 확인했고 R1-04는 미체크입니다. 구현과 통합 검사는 완료했지만, 사용자 stop condition에 따라 provider publication time과 complete coverage 및 회계 입력 누락을 최종 `blocked` / `not-evaluated`로 보고합니다. recovery label이나 후속 자동 작업은 지정하지 않습니다. 다음 행동은 누락 원천 증거를 확보하는 것이며, synthetic fixture나 현재 조회시각으로 대체할 수 없습니다.
