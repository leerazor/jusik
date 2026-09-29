# 자료 차단 해소 인계

- 날짜: 2026-09-29. 기준 local main `eadcaa06d5169b3992eea84e526d9bd2c19a9b29`; 이번 기록 commit은 뒤에 추가됩니다.
- 최우선 목표: 시간·현재 요금제 제약 아래 빠른 유효 수익성 결과. 같은 가격 요청·no-work 조사를 반복하지 않습니다.
- 새 근거: [개발 기록](../development-records/2026-09-29-listing-identity-evidence.md). 공식 공시 5개를 원문·SHA와 함께 확보했습니다. 원인 확인과 최종 연구 자료 승인을 구분합니다.
- 관찰: LIME 221개, MDA 145개 누락은 전부 각각 현대 미국 종목의 2026-07-01·2026-03-12 거래 시작 전입니다. 기존 캐시의 상장 이후 결손 0. 그러나 listing은 옛 회사명/IPO 날짜, Yahoo는 현대 회사명/거래 시작일이므로 identity 충돌이 있습니다.
- 첫 후속 작업: 별도 원문을 입력으로 issuer/security·exchange/currency·유효기간 identity 대사와 재사용 티커 회귀 진단을 계획합니다. 기존 원본 캐시와 acceptance는 보존하고, 독립 scope 승인 후 제한된 구현 후보로 진행합니다. 단순 티커·이름·가격 시작일만으로 정상 판정하지 않습니다.
- 그다음: 당시 universe 적격성·상장 근거·시각 출처를 갖춘 별도 corrected candidate를 만들고 실제 상장 후 가격 결손만 수집합니다. TSX/CAD 연결·가격 보간·사후 종목 편입 금지.
- 아직 미충족: 전체 provider/PIT coverage, action 시각/권리/가격, 정식 자료 acceptance와 OOS. R1-05 미완료 유지. 현재 관찰을 수익률 개선으로 보고하지 않습니다.
- 증거 폴더: `/home/kwl/.local/share/jusik/portfolio-audit/20260929-listing-identity-evidence/`; `profile.json`에서 원문·hash·정확한 UTC 기록을 확인합니다.
- 운영: 기록 통합 동안 pause, 이후 기존 자동 runner 재개. 사용자 루트 `HANDOFF.md` 보존; raw·cache·mandate 변경 없음.

다음 시작: “이번 공시와 기존 listing/Yahoo의 identity 충돌을 읽고, 더 긴 가격 재요청에 앞서 두 종목의 기간별 identity 진단과 보호를 가장 좁은 작업으로 진행해 줘.”
