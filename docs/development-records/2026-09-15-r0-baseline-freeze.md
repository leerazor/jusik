# R0 미국 기준선 증거 고정

- 상태: 검증
- 기록 시각: 2026-09-15T02:39:21Z
- 작업 slug: `r0-baseline-freeze`
- 기준/통합: `008ca02867224832fd36f4d437547b12173bcd47` / 없음
- 범위: 기존 미국 approximate pilot의 입력·실행·cache 증거를 외부 manifest 하나로 묶었습니다. 현재 replay 기준 SHA와 원본 생성 코드 후보를 분리했고, 코드·전략·프로바이더·DB·운영 설정은 변경하지 않았습니다.

## 변경과 결정

- 외부 기준선 manifest는 `/home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-baseline-freeze/baseline-manifest.json`에 보존합니다. manifest SHA-256은 `03ff5a140138277d2161a0896c7c8aefd64abe0545de7cc33ed9270882481205`입니다.
- 입력은 `us-pilot-1y-stable.json` (`ApproximateDataset`, SHA-256 `e58e69fc19fd89589e5cd5d55a43259f1ad28c9b9f0a87c75dd7617f28906aea`), `us-web-pilot-run.json` (`MarketResearchRun`, SHA-256 `cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275`), `us-pilot-1y-stable-cache/manifest.json` (`collector-cache-v2`, SHA-256 `a806c1ac0058901bbbca007aa91c8f8a3c56bc397c37452025babe82d6260d14`)입니다.
- run `87c94561b6f84bdcb87550fd9844f287`의 요청·기간·근사 등급·원천(`alpha_vantage`/`yahoo`/`fred`)·정책, data contract, pool contract와 input hash를 manifest에 그대로 기록했습니다. 데이터는 2025-09-12~2026-09-11 수집 기간과 2025-08-14~2026-09-11 가용 기간을 구분합니다.
- 원본 생성 코드 후보는 cache capture 직전 마지막 커밋 `aeeed810c7424535dc39fe38311b524c69d4d776`로 기록했지만, 실행 당시 워킹트리 메타데이터가 없어 `unverified`입니다. 현재 replay 기준은 별도로 `39541c5d8a07136f8f227e8f8477a7aeb57d8c89`로 고정했습니다.
- 기존 `-16.9330248724%`는 historical approximate observation으로만 기록했습니다. 경제적 성공 판정과 replay 동등성 주장은 하지 않으며, replay는 R0-03에서 수행합니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 사용자에게 보이는 동작은 바뀌지 않았습니다.
- 운영 문서: 해당 없음. 외부 audit manifest에만 기준선 증거를 보존했습니다.
- API·설정·데이터 계약: 해당 없음. 현재 모델 `ApproximateDataset` (`backend/jusik/market_history_approximate.py:87`) 및 `MarketResearchRun` (`backend/jusik/market_history_models.py:447`)을 읽기 전용으로 검증했습니다.

## 검증

- `python3.13 -m venv backend/.venv` — 통과; 워크트리 전용 가상환경을 생성했습니다.
- `backend/.venv/bin/python -m pip install --disable-pip-version-check -r backend/requirements.lock` — 통과; lock 설치를 완료했습니다.
- `PYTHONPATH=backend backend/.venv/bin/python`으로 두 JSON을 현재 모델에 `model_validate_json` — 통과; `ApproximateDataset`은 US·universe 10,840·bars 10,476·FX 271행, `MarketResearchRun`은 completed/pilot/approximate를 확인했습니다.
- 동일한 검증에서 `collector-cache-v2` manifest의 84개 entry를 `raw/<key>.bin`에 대조 — 통과; 누락 0, content SHA-256 불일치 0, byte count 불일치 0.
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_market_history_approximate.py backend/tests/test_market_research.py` — 통과; 45개 테스트 통과, 의존성 deprecation warning 2개.
- `python3.13 -m json.tool .../baseline-manifest.json` — 통과.
- 실행하지 않은 검사: 전체 lint/type check/build. 이 작업은 허용된 문서만 변경했고 replay는 R0-03 소유 범위입니다.

## 안전·운영 상태

- 원본 audit JSON·cache는 읽기 전용으로 사용했고 외부 manifest만 새로 작성했습니다. 실주문, brokerage API, 운영 DB, 서비스, runner, 원격 push는 변경하지 않았습니다.
- 비밀정보·자격증명·인증 응답·계좌 식별자는 기록하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-baseline-freeze`; manifest: `baseline-manifest.json`; SHA-256: `03ff5a140138277d2161a0896c7c8aefd64abe0545de7cc33ed9270882481205`.
- 남은 작업·차단 조건: supervisor의 독립 review와 local `main` 통합 검증 전까지 R0-01을 완료로 표시하지 않습니다. R0-03에서 현재 replay 기준으로 metrics·trades·equity 동등성을 검증해야 합니다.
- 다음 시작: supervisor가 이 커밋을 검토한 뒤 외부 manifest를 보존하고 R0-01 통합 검증을 수행합니다.
