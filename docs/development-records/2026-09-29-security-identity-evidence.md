# 증권 식별자 원문 보강

- 상태: 원문 확보·해시 검증·독립 검토 완료. R1-05 전체 자료 승인 미완료.
- 날짜: 2026-09-29. 작업 범위: 무료 공개 SEC 원문을 이용한 사후 identity 원인 조사.
- 선행: [기존 listing/가격 충돌](2026-09-29-listing-identity-evidence.md), 원 attempt `b6af09572cc2405a8aa63be725c27235`의 `reconciliation.json`.
- 제약: 현재 구독 2026-10-04까지, 추가 지출 미승인. 공개 문서 최대 6개, 문서당 8 MiB·요청당 30초, credential·유료 API·새 금융 실험 없음.

## 새로 확보한 사실

| 원문 | 문서에 적힌 발행사와 증권 식별자 | 날짜와 해석 범위 |
| --- | --- | --- |
| [Neutron Schedule 13G](https://www.sec.gov/Archives/edgar/data/1543151/000155278126000443/xslSCHEDULE_13G_X02/primary_doc.xml) | Neutron Holdings, Inc.; CUSIP `64125S104` | 보고 대상 사건 2026-06-30, 서명 2026-08-13. 사건일을 상장일·identity 효력일로 간주하지 않습니다. |
| [MDA Space Schedule 13G](https://www.sec.gov/Archives/edgar/data/1857047/000159680026000008/xslSCHEDULE_13G_X02/primary_doc.xml) | MDA Space Ltd.; CUSIP `55293N109` | 사건 2026-03-31, 서명 2026-05-11. 미국·캐나다 시장별 가격 이력은 별도입니다. |
| [구 Lime Schedule 13E-3](https://www.sec.gov/Archives/edgar/data/1065860/000110465916157139/a16-19615_1sc13e3a.htm) | Lime Energy Co.; 표지 CUSIP `284868106` | 서명 2016-11-15. 아래 13F와 다른 값이며 원문 그대로 보존합니다. |
| [구 Lime 보유 보고 13F](https://www.sec.gov/Archives/edgar/data/1422771/000095012316013407/xslForm13F_X01/form13fInfoTable.xml) | Lime Energy Co.; CUSIP `53261U304`, ISIN `US53261U3041` | 보유기관 보고 자료입니다. 위 값과의 전환·오류 여부나 전체 유효기간을 확정하지 않습니다. |
| [구 MDA 의결권 보고 N-PX](https://www.sec.gov/Archives/edgar/data/809586/000114420418043917/tv500649_n-px.htm) | MacDonald, Dettwiler and Associates Ltd.; 표기 `CINS 554282103`, ticker MDA, Canada | 주주총회 2017-07-27. 주총일을 상장일로, 캐나다 자료를 미국 가격으로 대체하지 않습니다. |

EDGAR URL의 CIK는 경로의 제출자 정보일 수 있습니다. Neutron 13G의 제출자는 Uber이므로
경로 `1543151`을 Neutron 발행사 식별자로 사용하지 않습니다. 기존 인수 8-K의 제출자도
Willdan이며 해당 URL만으로 구 Lime의 issuer CIK를 만들지 않습니다.

## 결론과 다음 작업

현대 증권의 식별자와 과거 문서의 식별자 관찰을 확보했습니다. Alpha listing 행에는 이 키가
없으므로 이름·ticker만으로 직접 결속하지 않습니다. 구 Lime 식별자 충돌, 종목별 전체
유효기간, 당시 provider 관측·적격성 receipt는 미해결입니다. 공시 사건일·서명일과 이번
`captured_at`을 구분하고 `historical_observed_at`은 null로 유지합니다.

수집은 5개 문서 HTTP 200에서 종료했습니다. 다음은 같은 가격 요청 반복이 아니라
이 근거가 필요한 identity 보호 작업을 구체화하고 별도 scope 검토하는 것입니다.
원본 366 결측을 정상 coverage로 바꾸거나 종목을 삭제하지 않습니다. R1-05·R4·PIT·OOS·
PAPER/live 상태와 기존 mandate는 변경하지 않았으며 새 수익성 결과는 없습니다.

## 검증과 증거

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260929-security-identity-evidence/`.
- `sources.json`: 요청 URL, 최종 URL, 실제 capture 시각, HTTP 상태, byte 수, 원문 SHA-256.
- `profile.json` SHA-256: `56fec8d067d13925b12f289caeda31b56590d685412fef4c41ac96ab4f2f4f84`.
- 5개 원문 SHA와 발행사/식별자 텍스트를 재검증했습니다. 기존 profile SHA
  `bb7c48d95552833b238e9507ef15360b476a3330c0aeb9abc5c09cdb5e901de1`은 불변입니다.
- 제품 코드·원 캐시·가격·provider metadata·운영 원장·투자 승인·원격 push 변경 없음.
- 독립 review: PASS (식별자 후보 보강의 정확성 범위). 새 5개 원문·manifest·profile,
  기존 profile과 결과·공시·Alpha·Yahoo 원문 해시를 별도로 확인했고 중대 지적은 없었습니다.
  이 검토는 자료 acceptance나 금융 성과 검증이 아닙니다.
