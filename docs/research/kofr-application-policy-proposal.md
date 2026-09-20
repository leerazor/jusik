# KOFR risk-free application policy proposal

이 문서는 현재 KOFR source evidence를 canonical NAV에 연결하기 전에 필요한
application 정책을 고정하기 위한 설계 문서다. 정책을 선택하거나 Sharpe/readiness를
승격하지 않으며, 현재 기본 동작은 fail-closed다.

## 현재 확인된 사실

- KSD source response는 `2025-09-11~2026-09-11`의 245행을 반환합니다.
- canonical US NAV는 같은 기간 252개 날짜를 사용합니다.
- 두 날짜 집합은 한국·미국 휴장일 차이로 일치하지 않습니다.
- 행별 `PUBN_DTTM`은 `YYYY.MM.DD HH:MM:SS` local-looking text지만 absolute
  timezone/instant 의미를 독립적으로 증명하지 않았습니다.

## 적용 선택지

### A. strict exact-date (현재 기본)

각 NAV 날짜에 같은 날짜의 KOFR 행과 publication evidence가 있어야 합니다. 없는
날짜는 삭제·0 대체·carry-forward하지 않고 `missing_risk_free_evidence`로 차단합니다.

### B. prior-observation carry-forward (후속 승인 필요)

각 NAV 날짜에 대해 해당 날짜의 NAV 결정 시각보다 먼저 공개된 가장 최근 KOFR를
사용하고, 한국·미국 휴장일에는 직전 관측값을 유지합니다. 이 정책을 채택하려면
다음 항목을 별도 manifest에 고정해야 합니다.

- provider가 비산출일에 직전 관측값을 사용하는 공식 적용 규칙
- `PUBN_DTTM`의 Asia/Seoul timezone 및 UTC 변환 근거
- NAV 결정 시각과 publication instant의 strict ordering
- 최초 NAV 이전 관측값 부족, 긴 공백, provider 수정 공시 처리
- 적용된 source date와 NAV date의 1:1 매핑 및 hash

KRX 선물 설명의 carry-forward 문구만으로 B를 승인하지 않습니다. 상품 산식과
포트폴리오 Sharpe의 risk-free interval 적용은 별도 계약입니다.

## 결정과 다음 gate

- 현재 선택: A의 fail-closed 동작을 유지합니다.
- B를 구현하지 않으며, source/NAV 적용 manifest를 정본으로 만들지 않습니다.
- B의 증거가 모두 확보되면 작은 별도 구현으로 validator·mapping audit·metrics
  replay를 추가하고, 그렇지 않으면 현재 blocked 상태를 유지합니다.

이 경계는 경제 지표를 임의로 만들지 않으면서 다음 외부 증거 요구를 명확히 합니다.
