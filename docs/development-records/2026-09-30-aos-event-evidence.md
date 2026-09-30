# AOS 배당 source-only 근거 보강

- 상태: 단일 배당락일 **출처 표기** 확인 완료; 과거 자료 인수·PIT·성과 적격은 미완료
- 기록 시각: 2026-09-30T08:47:55.197879+00:00
- 작업 slug: `aos-event-evidence-20260930`
- 기준/통합: `2d049b9c4de9cf9ce09697eecb4a96a2cc286b18` / 감독자 확정 예정
- 범위: 기존 AOS 한 사건의 source-only 근거. 생산 모델·준비 자료·정책·시세 캐시 변경 없음

## 증거와 판정

- 조회 전에 [source-only v1](/home/kwl/.local/share/jusik/portfolio-audit/20260930-aos-event-evidence/aos-source-evidence-v1.json) SHA `05b7c37886a244dd606a858549ba5b170208eed75c53f4fdfdcf9ef464d62112`에 기존 AOS 발표·배포본의 USD 0.36, 기준일 2025-10-31, 지급일 2025-11-17을 결속했다. 배포본 표기는 `2025-10-13 17:54 ET`이며 당일 EDT(UTC-04:00) 기준 `21:54 UTC` **분 정밀도**다. 명목상 `[21:54,21:55)` 구간은 표시 해석일 뿐 실제 공표 순간·과거 이용 가능성의 경계가 아니다. `ex_date`, 공급자 `observed_at`, `available_at`은 이 단계에서 null이다.
- 고정 검색어로 공식 검색 1회, [A. O. Smith 투자자 사이트 배당이력](https://investor.aosmith.com/stocks/dividend-history) 원문 열기 1회. [검색 렌더링 스냅샷](/home/kwl/.local/share/jusik/portfolio-audit/20260930-aos-event-evidence/search-snapshot.json)의 `Declared | Ex-Date | Record | Payable | Amount | Type` 대상 행은 `2025-10-13 | 2025-10-31 | 2025-10-31 | 2025-11-17 | 0.36 | U.S. Currency`다. 금액·기준일·지급일이 기존 근거와 일치해 **출처가 표시한 배당락일 2025-10-31**을 [결과 JSON](/home/kwl/.local/share/jusik/portfolio-audit/20260930-aos-event-evidence/result.json)에 추가했다.
- 원문 open 렌더링에는 대상 행 자체가 빠져 있으므로 그 행을 직접 열람 확인했다고 주장하지 않는다. [원문 스냅샷](/home/kwl/.local/share/jusik/portfolio-audit/20260930-aos-event-evidence/issuer-history-snapshot.json)은 역사 배당 표가 발행사 호스트에 있으나 제3자 Mergent 제공이라는 고지를 확인한다. 검색·open 스냅샷 SHA는 각각 `61795cd7847e3a5361fdafdb0d67bb3d38667f3a01d569dc340e4fef04c5cf4a`, `d2a72783f75ef981c101412dfd3b98060192545d7f946d85834a247c6c53f654`로 **web 도구 렌더링 텍스트/JSON** 해시이며 원본 HTML 바이트 해시가 아니다.
- Yahoo occurrence의 달력일도 10-31이지만 `13:30Z`의 의미·Yahoo 날짜 역할과 공식 배당락일의 동일성, 장중 효력 시점은 입증되지 않았다. 제3자 표의 역사 버전·공급자 관측시각·당시 이용 가능성도 미확인이다. 이 날짜를 `DividendAction` 또는 연구 준비 입력으로 승격하지 않는다. 이전 [9행 계약 감사](2026-09-30-event-observation-contract.md)의 나머지 필드 결손은 그대로다.

## 검증·영향·재개

- `python3` 표준 라이브러리로 날짜 ISO 변환, `Decimal('0.36')`, 대상 검색행의 6열 연결, 기존 amount/record/payment와의 일치, scope 보호 15개 SHA·증거 결속·null 미승격·검색1/open1 예산을 확인했다. 실제 시장 요청·금융 실험·주문·PAPER·배포·push·서비스 변경 0회. 코드 변경이 없어 기존 247개 테스트는 반복하지 않았다.
- 기능·API·설정·생산 데이터 계약은 바뀌지 않아 기능 문서를 수정하지 않았다. 다음은 Yahoo 사건의 날짜 역할, 과거 공급자 공개 가능성·vintage, 자격 경계를 별도 좁은 범위에서 확인할 근거가 생길 때만 재개한다. 같은 출처 재검색이나 125건 확대 조회는 이번 근거로 승인하지 않는다.
- workflow 판단: 도움 됨 — 기존 source-only 계약·행렬을 재사용하고 정확한 한 배당락일만 조회했다.
- 근거: 공식 검색 1회·원문 열기 1회, 보호 15개 SHA 일치, 생산 코드·준비 자료 변경 0. 시간·호출 절감 비교값은 미측정이다.
- 다음 조정: 유지 — 원문 출처 역할과 렌더링 한계를 함께 기록하고 자료 인수·성과 검증과 분리한다.
