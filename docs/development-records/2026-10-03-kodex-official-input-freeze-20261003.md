# KODEX 공식 배당 계산 입력 동결

- 상태: 동결 완료. 기존 CLI 입력 검증·재실행 동일성 및 독립 검토 PASS.
- 기록 시각: 2026-10-03T12:49:07.027706+00:00
- 작업 slug: `kodex-official-input-freeze-20261003`
- 기준/통합: `64391c8` / 이 기록의 로컬 main 커밋.
- 범위: 이미 검토 DB에 반영된 KODEX11건을 기존 공식 배당 입력 계약으로 동결. 코드·운영 DB·원장 변경 없음.

## 결과와 검증

등록목록 revision1과 검토DB의 SQLite online backup을 사용했다. 487230 7건,487240 3건,0173Y0 1건의 최신 event/revision/review와 공식 상품 코드/ISIN을 결속했다. 기존 CLI가 공급자 원문·검토 원문·해시·금액/날짜 계약을 재검증했고 같은 입력의 재실행 및 영구 경로 이동 후에도 같은 산출물 해시를 반환했다. API의 현금분배금 DIVID_A·기준일·지급일도 별도 대조했다. TAX_DIVID_A를 현금으로 대체하지 않았다.

상품 신원 원문은 새 조회 없이 기존 cache를 재사용했다. identity evidence의 captured_at은 이번 로컬 재검증 시각이며 원래 다운로드 시각이라고 주장하지 않음을 locator에 명시했다. operator_verified는 수동 신원 연결이며 역사적 PIT 증거가 아니다.

- artifact SHA `b160157c804f949dbc07bca380c8cd2a6d1c41a79995ff5d941e6ade5f541198`.
- `retrospective=true`, `historical_pit_verified=false`, `automatic_ledger_application=false`, `nav_ready=false` 유지.
- audit `/home/kwl/.local/share/jusik/portfolio-audit/20261003-kodex-official-input-freeze/`; manifest SHA `e8346e66ab6ba8b87966bc42c3ba0396ff4b8d8d694f9234c46d4913922d6b82`.
- 최초 CLI는 출력 디렉터리 미생성으로 실패했고 디렉터리를 만든 뒤 검증/재실행 통과. 원천이나 검증 조건은 바꾸지 않았다.

## 영향과 다음 행동

새 기능/API/정책이 없어 사용자 기능 문서 변경과 코드 검사는 반복하지 않았다. 전체 수익성·세후NAV·거래일·비용 적격은 아직 미검증이다. 원문11건 독립 검토는 앞선 작업에서 통과했으나 이 동결 산출물도 별도 Sol/high read-only 실행에서 해시·exact DB pins·상품 식별·현금금액/지급일 대조 PASS를 받았다. 그 후 기존 MSFT12건 입력과 함께 회계 연결 자료로 재사용한다. 주문·서비스·승격·remote push 없음.

- workflow 판단: 도움 됨 — 코드 재개 장애 동안 독립 준비 자료를 기존 검증기로 연결했다.
- 근거: 원천 재조회0,11건/3상품 exact pins와 artifact 동일성 통과; 절감 시간·비용 미측정.
- 다음 조정: 유지 — source cache와 기존 CLI 재사용, 투자 인수와 동결 완료 구분.

- 최종 독립 확인: 2026-10-03T12:59:48.876220+00:00; 검토문은 audit의 `independent-review.txt`로 보존한다. 최초 verification/manifest의 pending은 동결 당시 상태이며 후속 `review-completion.json`이 완료 상태를 명시한다.
