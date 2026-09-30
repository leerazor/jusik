# ECOS 환율 원천·시점 계약 근거

- 상태: 문서 작업 완료, main 통합 대기
- 기록 시각: 2026-09-30T04:40:26Z
- 작업 slug: `ecos-fx-source-contract-20260930`
- 기준/통합: `4a4d2480ab61c274325a8f7bf619b4af211b2d31` / 없음 (감독자 확정 예정)
- 범위: ECOS 공식 항목과 한국은행 산정 기준의 확인 범위, PIT 재개 조건만 문서화. 코드·원시 자료·성과 계약 변경 없음.

## 변경과 결정

- `docs/ecos-fx-comparison.md`: ECOS `731Y001/D/0000001`의 공식 항목명·단위와 매매기준율의 거래량 가중평균 산정 기준을 출처 링크와 함께 보강했다. 첫 10행 항목 응답에 최초 공표시각·vintage가 없다는 관측을 전체 서비스 부재로 확대하지 않았다.
- 관측일과 기초 거래일의 대응, 시간대·최초 사용 가능 시각, 과거 수정 이력은 미확인이다. FRED의 뉴욕 정오 매입환율과 다른 기준이므로 자동 결손 보충·NAV·성과 적용 및 임의 1일 지연은 승인하지 않는다.
- 재개에는 날짜 의미, 최초 사용 가능 시점, revision/vintage 자료, 기존 FX 적용 계약의 날짜·기준·비용 정합성 검증이 필요하다.

## 문서·계약 영향

- 사용자 문서: `docs/ecos-fx-comparison.md`에 공식 metadata, 산정 기준, PIT 재개 조건을 추가했다.
- 운영 문서: 변경 없음. 지속 실행 상태는 아래 인계에 보존한다.
- API·설정·데이터 계약: 실행 동작 변경 없음. 성과 적격성은 계속 `false`다.

## 검증

- `sha256sum`과 저장된 `verification.json`: backend 소스·테스트 2개, 실제 조회 산출물 6개, baseline 1개의 해시 일치 9건. backend tree는 기존 검사 대상 커밋 이후 차이 없음. 공식 자료 2개의 해시는 별도 manifest와 일치하며 manifest SHA-256은 `e47a5ea28a90b05c4963702b515693693f8617da9ea776902bf29bfcd8767188`.
- 공식 ECOS 항목 응답의 지정 코드·주기·항목명·단위, 저장된 한국은행 FAQ의 산정 설명과 문서 문구를 대조했다. 문서 상대 링크와 `git diff --check`를 확인했다.
- 기존 코드 `e9cf0a4`의 집중 pytest 182개, Ruff check/format, strict mypy 통과는 `integration-verification.json`의 기록을 재사용했다. 이번 작업에 코드·입력 변경이 없으므로 재실행하지 않았다. Python 빌드 대상도 변경 없음.

## 안전·운영 상태

- PAPER·실주문·서비스·DB·cache·원시 자료·배포·원격 push 변경 없음. 자동 실행기는 paused, service/timer inactive이고 실행 task가 없다는 감독자 확인 상태를 보존했다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260930-ecos-fx-source-contract/`; manifest: 같은 경로의 `manifest.json`; hash: 위 SHA-256. 기존 검사: `/home/kwl/.local/share/jusik/portfolio-audit/20260930-ecos-fx-comparison/integration-verification.json` 및 `live-verification.json`.
- 남은 작업·차단 조건: 독립 검토·main 통합. PIT·수익성 증명은 여전히 미완료이며 공표·수정 이력과 FX 적용 계약 근거가 필요하다.
- 다음 시작: 인계와 현재 mandate·작업 등록부에서 실제 READY 연구 후보를 확인하고 좁은 독립 작업을 선정한다. 동일 ECOS 근거를 반복 조회하지 않는다.
