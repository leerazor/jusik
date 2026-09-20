# SEC assisted draft, KIS cost source audit, and KRX zero-status boundary

- 상태: 완료·외부 operator/status evidence 대기
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `sec-assisted-draft-kis-cost-krx-status-20260920`
- 기준/통합: `d66249e` / 다음 통합 커밋
- 범위: SEC 수동 검토를 위한 보조 패킷과 유효한 미완성 form 초안을 생성하고, 한국투자증권 공식 비용·세금 표와 KRX 상태 자료 경계를 기록했습니다. 사실 자동 추출, 원장 적용, 비용 가정 교체, zero bar 보간은 하지 않았습니다.

## 변경과 결정

- SEC `pure-action-review-assistance.json`은 priority 8건의 accession/symbol/kind/source URL/raw SHA/후보 문맥을 보존하고 모든 행을 `review_required`로 표시합니다. `pure-action-review-form.assisted-draft.json`은 기존 8행 form의 구조를 유지하되 모든 facts와 `operator_verified`를 미완성으로 둡니다.
- 한투 뱅키스 국내 온라인 표는 2025-10-27 기준 KRX 0.0140527%, NXT 0.0130527%이고, 미국 온라인은 0.25% 및 매도 SEC fee 0.00206%입니다. 국내 KRX 매도 세금 표시는 증권거래세 0.08% + 농어촌특별세 0.15% = 0.23%입니다. 계좌·주문채널·거래일·상품에 대한 연구 계약 결속이 없으므로 기존 modeled rate를 공식값으로 대체하지 않았습니다.
- KRX zero OHLCV 29건은 KRX 관리종목 지정 내역 화면이 제공하는 일자·종목·지정사유·시세 컬럼과 정규장 09:00~15:30 설명을 근거로 별도 status 원문이 필요한 상태로 남겼습니다. 상태 원문 없이 거래정지/무거래를 확정하거나 bar를 보간하지 않습니다.

## 문서·계약 영향

- 사용자 문서: 없음. 비용은 연구 계약에 아직 적용하지 않았고 SEC/상태 자료는 operator 검토용입니다.
- 운영 문서: `docs/worktree-tasks.md`에 상태·audit 경로를 추가했습니다.
- API·설정·데이터 계약: 변경 없음. runner/service와 거래 경계도 변경하지 않았습니다.

## 검증

- SEC assisted draft validator — `source_verified_items=8`, `source_missing_accessions=[]`, `ready=false` (필수 사실/operator verification 미입력으로 의도된 결과)
- KIS/KRX 공식 페이지 확인: [한국투자증권 수수료 안내](https://m.truefriend.com/main/customer/guide/_static/TF04ae010000.jsp), [매매관련 세금](https://www.truefriend.com/main/customer/guide/_static/TF04ae050000.shtm), [해외주식 시장별 안내](https://m.truefriend.com/main/bond/research/_static/TF03ca050000.jsp), [KRX 관리종목 지정 내역](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT215.jsp)
- 실행하지 않은 검사: 실주문·PAPER 승격·KRX 상태 API의 무제한 수집. 계좌/기간과 상태 원문이 확정되지 않았기 때문입니다.

## 안전·운영 상태

- 실제 주문, broker write, PAPER/live 승격, remote push, Windows 종료 없음.
- runner paused, service inactive, timer disabled 상태를 유지합니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-us-market-collection-recheck/sec-evidence/`; form SHA `6e43d3f62deccc34211217fc35ee0ba3bf2daa03b1b9292c2fc1355fa9dae383`; assistance SHA `f22bd21af8edf2199cbb97954ae767131264077988acc7d3caf1eef44c3355ca`
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-kis-cost-source-audit/sources.json`; SHA `0678ec1d01da46976d629976c48386a8f73340ca0edf604cfb63c75ba208c01c`
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-krx-zero-status-source-audit/report.json`; SHA `4b031089fd4985d549d7a49b3a6d4ab3c330eb3c522eb59454aef027cd28466d`
- 남은 조건: SEC operator가 8건을 action/exclude로 확인하고 필수 facts·revision/content hash·PIT link를 입력해야 합니다. KIS는 계좌/채널/거래일을 확정해야 비용 계약에 반영할 수 있습니다. KRX는 29개 종목의 날짜별 공식 status 원문이 있어야 readiness를 올릴 수 있습니다.
- 다음 시작: SEC form을 operator 입력으로 갱신하거나, KRX status 원문을 제한된 날짜·종목으로 수집해 zero 행과 결속합니다.
