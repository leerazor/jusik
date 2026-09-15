# R1-01 historical US membership

- 최신 상태: 완료; 아래 첫 시도 차단 이력은 보존
- 작업 slug: `r1-us-membership`
- task/attempt: `roadmap-r1-01-v1` / `24eb774959c9485eae4e8cdb32609dc4`
- 기준: `a55da5a190a8764764be6748e346e09fdfc8dac6`; 구현 통합 없음.

## 확인과 차단 원인

현재 collector는 이후 annual listing을 읽지만 초기 표본을 전체 기간에 복제합니다. R1-01 계획의 membership 갱신은 아직 구현되지 않았습니다. 기존 roadmap의 R0 완료와 R1-01 미완료 상태를 확인했습니다.

필수 supervisor 스킬은 실제 spawn 인자에 명시적인 `agent_type`을 요구합니다. 현재 호스트의 `collaboration.spawn_agent`에는 해당 인자가 없습니다. 실제 지원 인자로 구성한 사전검사는 `missing explicit agent_type`로 실패했습니다. 가상의 인자를 넣어 검사를 통과시키거나 helper를 변경하지 않았으며, Luna 작업자와 독립 review를 시작하지 않았습니다.

## 검증과 한계

- frozen manifest의 artifact 4개 SHA-256 일치.
- 기존 main에서 오프라인 `jusik.market_research_replay` 실행: 원본 cache 84개 검증, `comparison.all=true`.
- 이 결과는 기존 legacy replay 검증이며 R1-01 구현 검증이 아닙니다.
- prefix invariance, contemporaneous eligibility, focused pytest/Ruff/type checks, 독립 review와 통합 main 검사는 구현 전 차단으로 미실행했습니다.

## 문서·운영 경계

개발 기록과 기존 작업 등록부에 차단만 기록했습니다. 사용자/API/설정 계약, roadmap checkbox, 연구 조건, 제품 코드는 변경하지 않았습니다. 네트워크 수집, PAPER/live 활성화, 주문, 운영 원장, 서비스 변경, 원격 push는 없습니다. 새 worktree는 만들지 않았고 기존 worktree와 untracked `HANDOFF.md`를 보존했습니다.

## 증거와 재개

- 영구 audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-r1-01-24eb7749`.
- `input-verification.json`: 입력과 현재 코드 해시.
- `routing-preflight.json`, `spawn-args.json`: 실패한 라우팅 사전검사와 지원 인자.
- `preflight-replay/catalogue.json`: 기준 main의 exact replay 검증.
- `HANDOFF.md`: 미충족 완료 조건과 재개 지점.

재개하려면 명시적 역할 인자를 지원하는 호스트 또는 현재 호스트를 지원하는 승인된 라우팅 절차가 필요합니다. 이후 같은 작업을 명시적으로 retry하고 frozen 계획부터 Luna 단일 worktree 구현·독립 review·local main 통합 검증을 수행해야 합니다. R1-01과 R1 전체는 미완료입니다.


## 2026-09-16 재시도

- task/attempt: `roadmap-r1-01-v1` / `0406c82ad69743049331fa3e1ff08495`.
- 상태: 완료; 독립 재검토 및 main 통합 검증 통과.
- 조사 기준 main: `5831862f9f5f1766d775db18e84cfa8362c5465b`; 작업 기준: `a8a2ac8`.
- 구현: `32815e75f6bbda311d43861954b54c99289925a5`; review 보완: `897abd46a653c70e93807fc3ea7ef2c55300e5bb`.
- 워크트리: `/home/kwl/projects/jusik-r1-us-membership-0406`; 담당 Luna `r1_code`, 독립 Terra `r1_review`.
- 영구 audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-01-0406c82a`.

### 변경과 계약

미국 collector는 `approx-us-r1-membership-v1`에서 초기 seeded 표본과 이후 membership을 구분합니다. 성공한 연간 관측에서 여전히 eligible인 incumbent를 유지하고 빈자리만 당시 후보로 채웁니다. 세션당 최대100개와 실행 전체 누적 admission400개를 구분하며, 요청 예산은 관측 횟수와 누적 admission 상한을 반영합니다. 소비자는 전체 기간 symbol 합집합을 다시 추출하지 않습니다.

이용 가능한 시각부터 변경을 반영하고, 실패 관측부터 다음 성공 관측까지 eligibility를 확인 불가로 남깁니다. 과거 membership과 보유 평가용 가격은 보존하며 warmup 가격으로 과거 eligibility를 만들지 않습니다. 새 membership 시각은 UTC로 정규화합니다. 새 pool 계약은 정책·seed·상한·admission/gap 규칙을 hash하고 실제 구성원은 입력 hash로 구분합니다.

`docs/market-research.md`에 새 미국 근사 계약을 기록했습니다. 기존 `approx-v2` 파싱·pool·replay, KR 경로, 전략·mandate·PAPER/live 경계는 보존했습니다. API schema·운영 설정·원장·서비스 변경, 네트워크 자료 수집, 실제 주문과 원격 push는 없습니다.

### 검증과 한계

- 현재 baseline artifact4개 hash 일치, 수정 전 main legacy replay `comparison.all=true`.
- 초기 review는 UTC 처리와 검증 누락을 지적했습니다. 동일 Luna가 보완했습니다.
- 보완 commit에서 지정 pytest4개 파일111개, Ruff, strict source mypy 통과. `code-verification/pytest-final.log`, `ruff-final.log`, `mypy-final.log`이 최종 구현 근거입니다.
- 초기 `pytest-focused.log`의 dirty dependency 실패는 미커밋 소스 검사이며 보존했습니다. 커밋 후 최종 검사와 혼동하지 않습니다.
- frozen replay `replay-final-v2-result.json`: `comparison.all=true`, `dependencies_dirty=false`.
- event-free collector/source/strategy의 membership·candidate prefix 동일성, 실패/복구, UTC, admission 이전 매수 방지,100/400 경계와 예산을 검증했습니다.
- 프런트엔드 변경이 없어 빌드 미실행. 기존 테스트 fixture의 전체 strict typing 부채는 범위 밖이며 변경한 제품 모듈2개의 configured mypy를 실행했습니다.
- 연간 관측 carry-forward는 근사 membership이며 strict PIT 일별 실제 명부가 아닙니다. 전체 종목 event 제외는 R1-02, 분류는 R1-03, 배당·split 회계는 R1-04로 남습니다. 수익 개선이나 R1 전체 완료, PAPER 승격을 주장하지 않습니다.

### 최종 통합과 보존

- 독립 Terra 재검토 PASS, 중요한 미해결 지적 없음. 모델 라우팅4역할 prepare/pre/post 검증 PASS; opaque message는 receipt 전달 근거이며 원문 무결성이나 role sandbox 적용으로 주장하지 않습니다.
- 병합 직전 main: `7915813cd597812769dc15c954f5c562bc1e06fe`; 통합: `52ef32e7c0990acc900a14a73ef38a166f820ff1`.
- main 통합 검사: pytest111·Ruff·strict mypy2 source·frozen replay `comparison.all=true` 모두 통과. `integration-verification.json`과 `integrated-*.log`에 실제 명령과 결과 hash를 보관했습니다.
- R1-01 체크박스만 갱신했습니다. R1 전체는 미완료이며 다른 체크박스와 연구 조건은 변경하지 않았습니다.
- handoff: audit의 `HANDOFF.md`. 사용자 기존 루트 HANDOFF.md와 다른 워크트리6개는 보존합니다.
- 정리: 증거·환경·patch·handoff 및 SHA-256 보관·검증 후 이번 병합 워크트리와 브랜치를 제거했습니다. 기존6개 워크트리는 보존했습니다.
