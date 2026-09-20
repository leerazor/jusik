# SEC assisted draft, KIS cost source audit, and KRX zero-status boundary

- 상태: SEC action/exclude 검증 완료·외부 KRX status evidence 대기
- 기록 시각: 2026-09-20T12:00:00Z
- 작업 slug: `sec-assisted-draft-kis-cost-krx-status-20260920`
- 기준/통합: `d66249e` / `ec1c4c2`
- 범위: SEC 수동 검토 패킷을 완결하고, 한국투자증권 공식 비용·세금 표와 KRX 상태 자료 경계를 기록했습니다. SEC 사실은 정본 원문과 Nasdaq 보조 근거를 결속했지만 원장 자동 적용·비용 가정 교체·zero bar 보간은 하지 않았습니다.

## 변경과 결정

- SEC `pure-action-review-assistance.json`은 priority 8건의 accession/symbol/kind/source URL/raw SHA/후보 문맥을 보존합니다. 명백한 false positive 4건은 `exclude`와 사유를 기록했고, BMRC/RWT/ATXG/IMUX 4건은 SEC 원문과 Nasdaq 근거를 확인해 ex-date·비율·적용일·검증 hash를 채웠습니다. form validator는 `ready=true`를 반환하지만 ledger 자동 적용은 금지됩니다.
- 한투 뱅키스 국내 온라인 표는 2025-10-27 기준 KRX 0.0140527%, NXT 0.0130527%이고, 미국 온라인은 0.25% 및 매도 SEC fee 0.00206%입니다. 국내 KRX 매도 세금 표시는 증권거래세 0.08% + 농어촌특별세 0.15% = 0.23%입니다. 사용자가 BanKIS online 범위(A)를 선택했지만, 과거 frozen backtest와 modeled rate는 보존하고 새 PAPER 비용 계약에만 적용할 수 있습니다.
- KRX zero OHLCV 29건은 KRX 관리종목 지정 내역 화면이 제공하는 일자·종목·지정사유·시세 컬럼과 정규장 09:00~15:30 설명을 근거로 별도 status 원문이 필요한 상태로 남겼습니다. 상태 원문 없이 거래정지/무거래를 확정하거나 bar를 보간하지 않습니다.

## 문서·계약 영향

- 사용자 문서: 없음. 비용은 연구 계약에 아직 적용하지 않았고 SEC/상태 자료는 operator 검토용입니다.
- 운영 문서: `docs/worktree-tasks.md`에 상태·audit 경로를 추가했습니다.
- API·설정·데이터 계약: 변경 없음. runner/service와 거래 경계도 변경하지 않았습니다.

## 검증

- SEC assisted draft validator — `source_verified_items=8`, `source_missing_accessions=[]`, `missing_fields={}`, `ready=true`, `excluded_accessions=4`, `automatic_ledger_application=false`
- KIS/KRX 공식 페이지 확인: [한국투자증권 수수료 안내](https://m.truefriend.com/main/customer/guide/_static/TF04ae010000.jsp), [매매관련 세금](https://www.truefriend.com/main/customer/guide/_static/TF04ae050000.shtm), [해외주식 시장별 안내](https://m.truefriend.com/main/bond/research/_static/TF03ca050000.jsp), [KRX 관리종목 지정 내역](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT215.jsp)
- 실행하지 않은 검사: 실주문·PAPER 승격·KRX 상태 API의 무제한 수집. KRX 일별시세 키는 HTTP 200으로 확인했지만 상태 자료는 별도 서비스 권한·API ID 결속이 필요합니다.

## 안전·운영 상태

- 실제 주문, broker write, PAPER/live 승격, remote push, Windows 종료 없음.
- runner paused, service inactive, timer disabled 상태를 유지합니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-us-market-collection-recheck/sec-evidence/`; assisted form SHA `b3aad84e6106016a836453adc3b8639bdf32a81a1d11c16885fa828fc5fc73fa`; assistance SHA `016a4c2dea94f2ce7c65ea4ee21a2df3187ea0c52ed070b69a3765640ebdaea5`
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-kis-cost-source-audit/sources.json`; SHA `9ee18ab9d8e7fabef1a96accdc9ec0b566a2da5d64ed9101cf4519e5069e826d`; selected scope `BanKIS online` (user A)
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-krx-zero-status-source-audit/report.json`; SHA `4b031089fd4985d549d7a49b3a6d4ab3c330eb3c522eb59454aef027cd28466d`
- 남은 조건: SEC 검토 form은 완결됐지만 이것은 action ledger 승인이나 NAV/PAPER 승인을 뜻하지 않습니다. KIS는 뱅키스 온라인 범위가 확정됐고 기존 frozen backtest에는 적용하지 않습니다. KRX는 29개 종목의 날짜별 공식 status 원문이 있어야 readiness를 올릴 수 있습니다.
- 다음 시작: SEC form을 operator 입력으로 갱신하거나, KRX status 원문을 제한된 날짜·종목으로 수집해 zero 행과 결속합니다.
