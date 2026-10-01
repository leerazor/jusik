# SP 상장 이력 SEC 원천 조회 게이트

- 상태: 첫 검색 단계는 원문 진입 전 차단; 별도 승인한 8-K 원문에서 합병 완료 확인. 실제 거래중단·상장폐지일과 자료 인수는 미확인. 작업 `sp-listing-source-20261001`, 기준 `6e6a0a5`. 생산 코드·정책·캐시·기존 원본 불변.
- 처음 보존한 [선택 발췌](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/search-snapshot-initial.json)는 전체 응답이 아니었다. 독립 검토 후 [원래 검색 도구의 전체 렌더링 응답](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/full-search-response.txt) 5개 결과를 세션 로그에서 복구해 [호출·응답 결속](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/full-search-provenance.json)과 SHA로 보존했다. 검색 결과는 SEC 원문 본문이나 HTML bytes가 아니다. [확정 proxy URL](https://www.sec.gov/Archives/edgar/data/1059262/000119312524005660/d152391ddefm14a.htm)의 결과는 SP Plus 보통주와 Nasdaq `SP`를 연결하지만 합병·상폐는 조건부 또는 예정 표현이다.
- 첫 검색 단계에 보인 [8-K URL](https://www.sec.gov/Archives/edgar/data/1059262/000119312524140235/d833024d8k.htm)의 제목은 `8-K`였으며 정확한 제출일은 해당 발췌에 없었다. 보이는 도입부는 SP Plus·Metropolis 합병계약을 설명하지만 완료·상장폐지·거래 중단 날짜와 `SP` 기호를 함께 확인해 주지 않았다. 첫 단계에는 URL을 열지 않았으며 본문 부재를 주장하지 않았다.
- [첫 단계 전체 결과 재판정](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/result.json): proxy 2개는 조건형, 계약 전시 1개는 합병 합의, 8-K의 보이는 발췌는 계약 도입부, 투표 표 1개는 채택안이다. 다섯 결과 어디에도 완료 사건과 `SP` 증권 identity가 함께 보이지 않아 사전 게이트 미충족. 이 단계 원문 open/GET 0회, 복구 과정의 검색·Yahoo 요청·재시도 0회였다. 당시 합병 완료 여부·효력/거래 중단일 등은 미확인이었다.
- [별도 승인된 8-K 원문 판정](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/supplemental-assessment.json): 고정 URL GET 1회, HTTP 200, 원문 SHA `97acd23653c5a4afec1fae9f158f9822bd8d022e18d1d99ded171538668ad999`. 표지는 SP Plus Corporation 보통주와 Nasdaq Global Select Market 기호 `SP`를 직접 연결한다. Item 2.01은 합병 효력·완료일 **2024-05-16**을 확인한다. Item 3.01은 같은 날 회사가 Nasdaq에 개장 전 거래중단을 **요청**하고 Form 25 제출도 **요청**했다고 한다. 실제 거래중단 실행·Form 25 제출·상장폐지 완료일은 이 원문만으로 확인하지 못했다.
- 기존 22종목 추적과 2025 Alpha Active 표기 간 모순을 진단하는 근거지만, Alpha/Yahoo의 역사적 증권 identity 연결이나 404 원인 증명은 아니다. 재선정·PIT·관측시각·coverage·NAV·성과 적격은 승격하지 않는다.
- 검증: 첫 단계 [결속](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/binding.json)은 불변이다. 새 [원문 결속](/home/kwl/.local/share/jusik/portfolio-audit/20261001-sp-listing-source/supplemental-binding.json)에 별도 scope·선행 sentinel·원문·판정 SHA, 보호 파일 4개 불변과 문서 링크를 보존했다. 추가 검색·링크 순회·재시도 0회, 요청 10 MiB/30초·전체 60초 제한. 생산 코드 불변으로 pytest·Ruff·mypy·build는 재실행하지 않았다. 주문·금융 실험·추가 결제·서비스·push 변경 없음.
- 재개: 실제 Nasdaq 거래중단 또는 Form 25 제출·상장폐지 이행 자료의 정확 URL이 있으면 별도 범위에서 확인한다. 기존 8-K·검색을 반복하지 않으며, 그 뒤에도 Alpha/Yahoo identity와 당시 이용 가능성·기간별 봉 근거를 독립 확인해야 한다.
- workflow 판단: 첫 검색 단계에서는 게이트 미충족으로 원문 요청을 중지했고, 이후 독립 승인된 정확 8-K만 조회했다.
- 근거: 총 검색 1회·SEC 원문 GET 1회(첫 단계 0회, 보충 단계 1회); 시간·비용 절감 비교치는 미측정이다.
- 다음 조정: 합병 완료는 확인됐다. 실제 거래중단·상장폐지 이행과 Alpha/Yahoo identity·자료/PIT 적격은 새 근거가 있을 때만 재검토한다.

## 통합과 종료

- 구현 `c2231c4`, local main `cebe5a0dc96875f21c644deb2a5875528013a673`. 독립 review PASS, main 원문8·문서2·보호4 해시 일치, backend 변경 없음. 추가 조회·동일 테스트 재실행 없음.
- 검색 도구의 전체 반환을 원래 세션에서 복구해 최초 발췌본과 함께 보존했다. 원문 읽기 허가와 자료·성과 인수 기준을 구분하여 보충 1회만 실행했다.
- worktree/branch 정리와 runtime 설정 보존 완료. 종료 문서와 운영 관찰은 audit `closeout.json`, `cleanup.json`, `runner-resume.json`을 따른다. 결손22·PIT·비용 포함 비교 차단은 유지한다.
