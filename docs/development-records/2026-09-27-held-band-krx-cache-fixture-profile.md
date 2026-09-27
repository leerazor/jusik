# Held-band KRX prepared fixture profile

- 상태: 완료 (offline fixture profile only)
- 기록 시각: 2026-09-27T07:06:34Z
- 작업 slug: `portfolio-held-band-krx-cache-fixture-profile`
- 기준/통합: `91def6a33a36cbcc4d665ccf5bdcfb0da5902b89` / local `main` fast-forward 대상; 통합 SHA는 작업 등록부에 기록
- 범위: 보존된 KRX `kr-pilot.json`과 `run.json`을 read-only로 프로파일링하고 결정 준비 문서에 범위와 한계를 기록했습니다. mandate·v1/v2 preregistration·원본 입력·제품 코드/테스트·credential·runner config는 변경하지 않았습니다.

## 변경과 결정

- 현재 source 폴더에는 prepared JSON과 run summary만 있으며 raw manifest와 completed marker가 없습니다. 두 원본 SHA는 이전 KRX smoke 기록과 일치하지만 저장된 `run.input_hash`와 prepared byte SHA가 다르고, 결과 provenance에는 prepared hash가 없어 run-to-file snapshot binding은 증명되지 않습니다. 이 차이만으로 입력 변조를 주장하지 않습니다.
- Prepared rows는 universe 14,446행, bars 14,446행, 194세션(2025-08-13~2026-06-02), 94 symbols입니다. 현재 repository calendar가 run 요청 기간에서 기대하는 246세션 중 174세션만 포함해 72세션(2026-06-03~2026-09-11)이 비어 있습니다. observed range 내부에는 현재 calendar 기준 gap이 없습니다. 시작 전 20개 warmup session이 포함되어 있습니다.
- 정규화 파일 내부의 membership/bar 키 중복 및 일방 키, numeric 누락, invalid OHLC, 음수 volume은 0입니다. 다만 raw 응답이 없어 무거래 membership 누락 여부를 판정할 수 없습니다. 두 symbol의 이름 또는 거래소 값 변경, `events=0`, `fx=0`, `observed_at` 부재를 기록했습니다. 모든 `available_at`은 현재 repository calendar close와 같으나 이는 collector modeled-availability 관례이며 제공자 관측/공표 시각 증거가 아닙니다.
- 보존 run은 `insufficient`, `incomplete`, `readiness.ready=false`, `final_promotable=false`, metrics/trades/equity 0입니다. 결과는 fixture/debug·pipeline 회귀 점검에만 쓰며 PIT, 완전한 역사 membership, 성과, OOS, 후보·실거래 승인 근거에서 제외합니다.
- Provisional assumption: 무료 offline 프로파일·현재 repository calendar 대조·기존 exposed fixture만 사용합니다. 시장/source/data grade·표본 기준·수익 hurdle·정식 기간·예산을 정식 등록값으로 동결하지 않습니다. `FINAL_VALIDATION`/OOS만 승인된 freeze 및 적격하고 미노출된 미래 자료에 의존합니다.

## 문서·계약 영향

- 사용자 문서: [결정 준비 문서](../research/portfolio-held-band-decision-preparation-v1.md)에 KRX prepared fixture의 실제 범위, 결손, timestamp 의미와 fixture 전용 제한을 추가했습니다.
- 운영 문서: 작업 등록부와 held-band handoff는 main 통합 후 supervisor가 갱신합니다.
- API·설정·데이터 계약: 변경 없음. 새 API 호출, 자료 수집, DB·broker·PAPER/live·주문을 하지 않았습니다.

## 검증

- Python 3.13.15 `py_compile`, private audit script Ruff check와 format check — 통과.
- 결정적 프로파일 두 번 실행 후 `cmp` — byte-identical. 출력 SHA-256 `6d7b531d1135d4c5bb87b92998bd39882cceeb3e46bc649e593d8914f53b76e8`; 보조 audit script SHA-256 `ff05b069dbe4137ad5af802917803b45e5aeb5aeb3b285b79b17a7f6d567cde3`.
- 입력 SHA-256: `kr-pilot.json` `d4448db8d418e45482589a1b39b6d4885992c31a58e2997357d8501b07a46352`, `run.json` `652fa3985d7990143e77800210114d8533ece96a8e3b45e800c2a55f6ab9e64d`; 현재 calendar SHA-256 `ba26619a27e066ca32b1aaaf3b7da2b99f0c6658f731a000c5095c057081c1d8`.
- 독립 read-only review — PASS. 246/174/72는 현재 calendar 기준 prepared-file coverage이고, canonical hash와 file-byte hash 차이는 변조 증거가 아니며, `available_at`을 실제 공표 시각으로 읽지 않는 경계가 profile과 문서에 일치합니다. review 수정 사항은 없습니다.
- 결정 준비 문서·개발 기록의 내부 상대 링크, `git diff --check` — 통과. mandate SHA와 v2 20개 unresolved null 및 `registered/approved/execution_allowed=false`를 확인했습니다.
- Python product tests는 제품 코드 변경이 없고 audit 입력이 prepared JSON이므로 실행하지 않았습니다. mandate SHA와 v2 null/비실행 필드는 main 통합 후 재확인합니다.

## 안전·운영 상태

- 원본 audit files는 읽기만 했으며 변경하지 않았습니다. 네트워크·API·DB·credential·구매·주문·PAPER/live 접근은 없습니다. 결과는 입력과 분리된 private audit 경로에 저장했습니다.
- roadmap runner queue는 `paused=true`를 유지합니다. 확인 당시 service가 `activating`이어서 tracked 문서 수정을 앞두고 stop해 `inactive`를 확인했으며 timer는 `active`로 두었습니다.
- 사용자 작성 루트 `HANDOFF.md`는 미수정·미추적 상태로 보존합니다. remote push는 하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260927-held-band-krx-cache-fixture-profile/`; deterministic outputs `profile-a.json`, `profile-b.json`은 byte-identical입니다. 이전 입력 directory는 raw manifest/completed marker 없이 `kr-pilot.json`, `run.json` 두 파일만 보존합니다.
- 남은 차단: 정식 `FINAL_VALIDATION`/OOS는 사용자 승인 preregistration freeze와 이후 확보한 적격·미노출 미래 자료를 기다립니다. 신규 KRX API 수집은 적용 가능한 이용 자격, API별 승인 및 credential 확인에 종속됩니다. 현재 credential 상태는 조사하지 않았고, 유료자료는 실제 지출 승인 전 구매하지 않습니다.
- 다음 시작: source/schema-agnostic pipeline에서 observed-time과 membership/event coverage를 fail-closed로 표현하는 독립 offline test/fixture gap을 조사합니다. 이 기술 작업은 v2 등록 필드나 투자 승인 기준을 변경하지 않습니다.
