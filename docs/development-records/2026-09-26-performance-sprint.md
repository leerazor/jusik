# 3시간 연구 성능 개선 집중 작업

## 범위와 운영

사용자는 토큰 리셋 전 3시간 동안 유용한 성능 개선에 집중하도록 요청했다. 시작은
2026-09-26T07:56:14Z, 종료 목표는 10:56:14Z(19:56 KST)다. 시작 당시 실제 계정
잔여량·리셋 시각은 미확인이었다. 08:14:28Z의 읽기 전용 `account/rateLimits/read`는
37% 사용·63% 잔여와 11:11:11Z(20:11:11 KST) 리셋을 반환했다. 정확한 잔여 토큰 수는
제공하지 않았으며 요청한 작업 종료 목표는 연장하지 않는다. 추가 결제·권한·credential 변경·투자 기준
완화·실주문·원격 push·Windows 종료는 하지 않는다.

시작 당시 runner는 별도 `research-web-reports` UI 작업으로 pause였고 실행 중인
runner child는 없었다. 그 pause 소유권과 frontend·운영 데이터는 보존한다. 본 작업은
별도 backend worktree와 전용 환경에서 수행하며 main 통합은 활동·HEAD를 다시
확인한 경계에서 직렬로 한다. 다른 사용자의 미추적 `HANDOFF.md`와 UI 기록은 보존한다.

UI 감독자는 `9357d63`에서 배포·정리를 완료하고 본 수동 작업이 끝날 때까지 runner
pause를 유지하도록 명시적으로 인계했다. 이후 본 감독자가 pause를 확인했다. 실제
`jusik-development-runner.service`는 inactive, timer는 active이며 네 종류의 실행
attempt는 모두 0이었다. 수동 작업을 마친 후 기존 설정으로 복원할 책임은 본 작업에 있다.

전용 audit:
`/home/kwl/.local/share/jusik/portfolio-audit/20260926-performance-sprint-XzoOxB/`.

## 첫 병목과 확정한 계획

Luna read-only 조사에서 `research_engine.run_backtest`가 전체·학습·검증의 기본/후보
전략을 최대 여섯 번 실행하면서 같은 순수 SMA 신호를 반복 계산함을 확인했다.
10종목×550봉의 합성 입력 cProfile은 총 0.194초, 신호 19,460회·SMA 29,190회였다.
이는 단일 초기 관측이며 제품 speedup 결과는 아니다. 별도 시장 fixture의 1,136봉은
0.031초였고, 이 경로에는 아직 변경 근거를 확정하지 않았다.

별도 Sol 계획에 따라 `research_engine.py` 내부의 한 `run_backtest`에 한정된
`(version, symbol, sorted_bar_index)` bool cache를 검토한다. 기본 신호만 기존
`target_invested`로 계산하고 순서·Decimal precision 40·ROUND_HALF_EVEN·포트폴리오
상태·날짜 인덱스 의미를 유지한다. rolling recurrence, 전역 캐시, 전략 수식 변경,
다른 엔진의 hash pin 변경은 제외한다. 사용자 정의 SMA와 callback 경로는 그대로다.

단일 Sol 구현 파일은 `backend/jusik/research_engine.py`와
`backend/tests/test_research_engine.py`다. 외부 audit의 재현 benchmark와 결과도
같은 구현자가 준비한다. `perf/research-signal-cache` 전용 worktree를 사용한다.

## 검증·완료 기준

- 현재 합법 요청 상한인 10종목, 550/1,100봉 합성 입력을 고정한다.
- 기준/후보 각각 warmup 3회·측정 11회의 median을 교대로 확인한다. 대표 1,100봉에서
  10% 이상 개선을 목표로 하되 벽시계 속도를 CI assertion으로 쓰지 않는다.
- 전체 출력은 `implementation_hash`, `parameters_hash`만 제외해 정확히 비교하고,
  여섯 내부 `StrategyResult`의 거래·자산 경로도 비교한다. 변경된 코드 hash는 별도 확인한다.
- 미래 prefix 불변, 이벤트·수수료·미체결·누락·중복 날짜·역순·Decimal 경계,
  연속 실행의 캐시 격리, 비기본 SMA·callback 동작을 검증한다.
- engine/optimizer/risk/universe 집중 pytest, Ruff, strict mypy, 별도 Sol review,
  main 통합 검증을 통과해야 완료다. 기존 역사 산출물 pin 실패를 숨기지 않는다.

## 독립 연구 준비 점검

root의 정적 계약 점검에서는 legacy prospective 등록의 6개 metric과 현재 mandate의
CAGR/MDD/Sharpe/Calmar·고정 required return·분리 validation/WF/단회 OOS 계약이
같지 않음을 확인했다. 기존 literal `evaluation_inputs_complete=False`는 유지된다.
평가 창은 `[2026-09-14, 2026-11-09)`이며 runtime 등록·관측·PAPER DB·미래 성과는
열지 않았다. 상세는 audit의 `PROSPECTIVE_CONTRACT_AUDIT.md`에 있다. 새 계약의
실제 구현·등록·투자 검증을 이 점검만으로 승인하지 않는다.

## 첫 개선의 구현·검증 결과

구현 `7fbbace431514bd35c61eeaddaba0bd2eb550e89`를 별도 Sol이 검토하고
`a4fd555c43fbeecc506b7c33498602ac56fae0f6`로 local `main`에 통합했다. 병합 직전
main은 `9357d6346c742e82bafec6d24dc75f09e541b0a0`이며 UI 변경과 사용자 파일을
보존했다. 최초 통합 시도는 예상 HEAD와 실제 HEAD의 차이를 감지해 변경 없이 중단했고,
UI 문서 완료 commit만 추가됐음을 확인한 다음 저장소 runner lock 안에서 통합했다.

| 합성 입력 | 기준 median | 개선 median | 실행 시간 감소 |
| --- | ---: | ---: | ---: |
| 10종목 × 550봉 | 134.094 ms | 101.284 ms | 24.47% |
| 10종목 × 1,100봉 | 284.967 ms | 216.673 ms | 23.97% |

기준·후보는 별도 프로세스에서 각 warmup 3회·측정 11회를 교대로 실행했다. 신호/SMA
호출은 550봉에서 19,460/29,190 → 9,720/14,580, 1,100봉에서 41,460/62,190 →
20,720/31,080이었다. 공유 WSL 환경의 합성 입력 측정이며 실시장 처리량·수익률 개선이 아니다.

전체 공개 결과는 실제로 변경된 `implementation_hash`와 `parameters_hash`만 제외하여
같았다. 내부 전체·학습·검증 결과, 종료 상태의 pending·현금·보유·비용·이벤트도 같았다.
중복·누락·역순, 40자리 초과 Decimal, 비용·0거래량·미체결, 분할 없는 짧은 입력,
연속 호출의 가변 입력 등 9개 경계 사례를 고정 기준 소스와 비교했다. 별도 reviewer가
원시 JSON·Git 소스 hash·median을 대조하고 경계 비교를 독립 재현하여 PASS했다.

- 구현 및 main: engine/optimizer/risk/universe pytest 91개 PASS.
- main: 변경 두 파일 Ruff check·format, strict mypy, `git diff --check` PASS.
- 독립 검토: engine pytest 25개와 기준/후보 9개 경계 재현 PASS; 조치할 결함 없음.
- 최초 작업 환경의 PyTorch 미설치 실패는 기존 optimizer lock을 전용 venv에 설치해
  해결했다. 의존성 선언·버전·운영 환경은 변경하지 않았다.
- 추가 전체 suite: `python -m pytest -q` 2,106개 PASS·2개 FAIL·경고 2개, 257.59초.
  실패는 기존 `test_copy_is_exactly_the_guarded_variant`의 고정 variant SHA 불일치와
  `test_frozen_archive_replay`의 과거 calendar source hash 불일치로 같다. 새 실패는
  없었고 역사 pin을 수정하지 않았다. 전체 suite green으로 표시하지 않는다.

재현 자료는 audit의 `signal-cache-benchmark/RESULTS.md`, `timing.json`, `parity.json`,
`edge-parity-final.json`, 동결된 기준 소스에 있다. 기준 엔진 SHA-256은
`14606b7069e91b427d15629b3963f764aa05bb31a1baaf38a37ed8821c553a37`, 후보는
`76917cc42bd2ea9aeafaa6d39cd1ed63ebc9133d18e3e1c69ceddc522b473d32`, 재현 script는
`cb04a67412a2d574d5765c03eaea794430345cfd1dec482e524be5b52aa7995d`다.
전체 검사 JUnit XML은 audit의 `main-full-suite.xml`이다. reviewer의 독립 재현 JSON은
`signal-cache-benchmark/independent-review-reproduction/`으로 보존했고, 전용 환경의
59개 package 버전·Python·lock hash는 같은 폴더의 `environment.json`에 기록했다.
코드·증거와 main 소유 파일 동일성을 확인한 후 첫 전용 worktree·venv·cache를 정상
`git worktree remove`로 정리했다. `perf/research-signal-cache` branch와 commit은 보존한다.

## 후속 작업과 현재 판정

첫 속도 개선은 `ENGINEERING_COMPLETE/NOT_EVALUATED`다. 3시간 창은 계속 진행 중이다.
다음 과제는 구현 완료 reviewer의 구조화된 일시 호출 장애를 영속 기한 재시도로
분리하는 것이다. 범위 reviewer의 별도 상태 전환은 독립 후속으로 두고, 먼저 한 경로를
완결한다. 자료·투자 검증·주문 기준은 변경하지 않는다. 정적 prospective 계약 점검만으로
새로운 OOS 실험이나 투자 후보 승격을 승인하지 않는다.
