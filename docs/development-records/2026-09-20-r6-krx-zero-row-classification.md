# R6 KRX zero-row classification

- 기록 시각: 2026-09-20T03:12:00Z
- 입력: 기존 KRX raw cache의 `2026-06-29` response 946행을 read-only로 읽었습니다.

## 관찰

- zero/missing OHLCV 행: `29`
- 29행 모두 `MKT_NM=KOSPI`
- 공통 signature: `TDD_CLSPRC`, `MKTCAP`, `LIST_SHRS`는 양수지만
  `TDD_OPNPRC/TDD_HGPRC/TDD_LWPRC/ACC_TRDVOL/ACC_TRDVAL/CMPPREVDD_PRC`는 `0`
- 따라서 현재 raw는 인증/HTTP 실패가 아니라 provider가 membership과 종가·기본정보는 반환하면서
  당일 거래 bar를 비워 둔 응답입니다.

## 판정

- 이 signature만으로 거래정지, 무거래, 상장 상태를 확정하지 않습니다. 별도 KRX trading-status/거래정지
  원문과 전후 날짜 coverage가 필요합니다.
- zero 행을 보간하거나 정상 bar로 승격하지 않았습니다. R6 readiness는 `insufficient`, R6-04 한국
  benchmark/경제 평가는 계속 보류합니다.
