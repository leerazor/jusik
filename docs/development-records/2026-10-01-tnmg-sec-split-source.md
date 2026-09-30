# TNMG 분할 SEC 주 문서 원천 확인

- 상태: 주 문서 2건 조회 완료, 2025 날짜 충돌은 차단. 작업 `tnmg-sec-split-source-20261001`, 기준 `60fd537`. 생산 코드·캐시·정책·준비 자료 불변.
- 고정된 SEC [2025 6-K](https://www.sec.gov/Archives/edgar/data/2013186/000121390025123776/ea0270323-6k_tnlmedia.htm)와 [2026 6-K](https://www.sec.gov/Archives/edgar/data/2013186/000121390026096959/ea0304379-6k_tnl.htm)를 각 1회 GET했다. 원문 SHA는 각각 `7668d94407b948280137d98e01466c3e56b4c03dadfb27737d6eb14952b0d630`, `76fa939531716064c2203e1bda9b9f17778eef71f4bad4f82de9a7957e113386`. [판정과 원문 결속](/home/kwl/.local/share/jusik/portfolio-audit/20261001-tnmg-sec-split-source/assessment.json)에 accession·날짜·비율을 보존했다.
- 2025 주 문서는 2025-12-19 발표 및 `1-for-20` 병합을 명시하지만, 조정 기준 거래 시작일을 **2024-12-23**으로 기재한다. 대상 2025-12-23과 연도 충돌을 임의 오탈자로 고치지 않는다. 발행주식 수의 2025-12-18은 press release 날짜가 아니며, Exhibit 99.1 목록은 보도자료를 **2025-12-05**로 표기한다. 이 날짜들의 역할과 충돌 해소는 별도 근거가 필요하다.
- 2026 주 문서는 `1-for-8` 병합과 **2026-09-08 개장부터 조정 기준으로 거래될 것으로 예상**한다고 명시한다. 실제 효력·완료를 확인한 표현은 아니다. 두 SEC 접수 시각은 최초 공개 가능 시각이나 Yahoo 공급자 `observed_at`의 증명이 아니다.
- 주 문서가 가리키는 전시자료 URL은 [2025 Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/2013186/000121390025123776/ea027032301ex99-1_tnlmedia.htm), [2026 Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/2013186/000121390026096959/ea030437901ex99-1.htm)이다. 이번 요청 범위 밖이라 조회하지 않았다.
- 검증: SEC metadata·고정 URL·보호 8개 SHA·URL별 선행 sentinel·응답/binding·문서 링크를 [verification](/home/kwl/.local/share/jusik/portfolio-audit/20261001-tnmg-sec-split-source/verification.json)에 결속했다. GET 2회, 검색·재시도·리다이렉트·Exhibit 조회 0회; 각 10 MiB·요청 30초·전체 60초 상한. 감사 스크립트 Ruff/strict mypy 통과. 생산 코드가 불변이므로 기존 테스트·빌드는 반복하지 않았다. 주문·추가 결제·서비스·push 변경 없음.
- 남은 차단: 2025 날짜 충돌, 최초 공개 가능 시점, 사건 관측시각, Yahoo quote raw/adjusted 기준 및 2026-09-08 결손 가격. 이 원문만으로 분할 회계·NAV·PIT·성과 입력을 승인하지 않는다. 다음 독립 범위에서 2025 Exhibit의 고정 URL부터 충돌을 확인할 수 있으나 이번 자료는 다시 조회하지 않는다.
- workflow 판단: 기존 submissions에서 특정한 두 원문만 조회해 날짜 충돌과 근거 범위를 분리했다.
- 근거: 실제 GET 2회·Exhibit 0회, 보호 8개 SHA 일치. 시간·비용 절감 비교치는 미측정이다.
- 다음 조정: 2025 충돌을 별도 원문으로 해소하기 전에는 날짜를 확정하지 않는다.
