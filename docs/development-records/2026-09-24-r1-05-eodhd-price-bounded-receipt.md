# 2026-09-24 R1-05 EODHD price bounded receipt

## 목적

`.env`에 이미 등록된 `EODHD_API_KEY`를 사용해 R1-05의 LIME/MDA 누락 기간을 인증된 historical price 원천으로 한 번 bounded 확인했다. API key 값은 저장·출력하지 않았다.

## 요청과 결과

- endpoint: EODHD `/api/eod/{symbol}.US`
- period: `2025-01-01`~`2026-09-24`
- LIME: 59 rows, first `2026-07-01`, last `2026-09-23`, raw SHA `846ec9df9e5954d72986a2f05186b1915e8f4bb85252f88d793146fc34e2e728`
- MDA: 135 rows, first `2026-03-12`, last `2026-09-23`, raw SHA `11af3c72fd437b11765bc1f6a26be4f30aaac31b941ec4ff6eefb9ba5fb36039`
- 응답 필드: `date`, OHLC, `adjusted_close`, `volume`; provider publication/first-observed timestamp는 응답에 없었다.
- receipt: `/home/kwl/.local/share/jusik/portfolio-audit/20260924-r1-05-receipt/eodhd-bounded/`

EODHD의 시작일은 기존 Yahoo 장기 fallback과 동일하며, 2025-09-11~2026-02-27 등 남은 366개 누락 세션을 제공하지 않았다. 따라서 provider 교차 확인은 되었지만 complete coverage·historical observed_at·누락 원인은 증명되지 않았다. R1-05/PIT/economic acceptance는 승격하지 않는다.

## 후속 조건

더 긴 원본 이력 또는 provider의 historical observed_at/cause와 complete coverage manifest가 있어야 누락을 해결할 수 있다. 현재 응답으로 누락 세션을 보간하거나 심볼을 자동 제외하지 않는다.

