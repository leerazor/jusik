# AOS 배당 사건 단일 원문 확인

- 상태: 발행사 원문과 금액·달력일, 배포본의 분 단위 게시 표기 확인. Yahoo 사건 날짜의 역할과 실제 당시 최초 관측은 미확인
- 범위: AOS 배당 1건만 진단. 생산 코드·정책·시세 원본·준비 자료·성과 실험 변경 없음
- 기준: `07461b3`; main 통합 SHA는 감독자가 확정 예정

## 원본과 공식 근거

- 조회 전 [audit identity.json](/home/kwl/.local/share/jusik/portfolio-audit/20260930-aos-event-source/identity.json)에 기존 Yahoo 원문 SHA-256 `208075b0e7988c898334cc95f30b49e677d56ead4cfd594032a3c31ed961b052`와 `dividends` 금액 USD 0.36, epoch `1761917400` = `2025-10-31T13:30:00Z`를 고정했다. 기존 prepared SHA-256은 `c1b8220c3ffd5beb548ced1209b75442c8a4077dbeac032c9d4d0b025a3c514d`, 해당 사건 `observed_at=null`이다.
- 공식 검색 1회, [A. O. Smith 발행사 발표](https://investor.aosmith.com/news-releases/news-release-details/o-smith-increases-quarterly-dividend-036-share)와 그 페이지가 직접 연결한 [PRNewswire 배포 원문](https://www.prnewswire.com/news-releases/a-o-smith-increases-quarterly-dividend-to-0-36-per-share-302582536.html) 열기 각 1회. 발표·배포본은 2025-10-13 이사회가 주당 USD 0.36 배당을 승인했다고 표시하며, 기준일은 2025-10-31, 지급일은 2025-11-17이다. 배당락일은 표시하지 않는다.
- 배포본은 `2025-10-13 17:54 ET`를 표시한다. 이날 미국 동부는 EDT(UTC-04:00)이므로 표시된 **분**은 `2025-10-13 21:54 UTC`에 해당한다. 초 단위 시각, 실제 당시 최초 관측·배포 완료 시점, 현재 페이지의 역사 버전은 확인되지 않았다.
- Yahoo 금액은 공식 발표와 같고 Yahoo occurrence의 **달력일**은 공식 기준일과 같다. 이 일치만으로 Yahoo timestamp가 기준일을 나타내는지, 배당락일을 나타내는지, `13:30:00Z`가 어떤 확정 시각인지는 판정할 수 없다. 배포본의 분 단위 표시를 Yahoo의 `observed_at`으로 대입하지 않았다.
- [audit assessment.json](/home/kwl/.local/share/jusik/portfolio-audit/20260930-aos-event-source/assessment.json)에 판정과 보호 원본 11개 SHA 일치 결과를 보존했다. 검색·발행사·배포본 스냅샷 SHA는 각각 `ee3d1f02af448e5a7671a22f3a91ef54a9e45e4625ccbe36496bd852a7302557`, `03fa2cf6729ff8f9945157a97ddced54c4956342747daa984a6b0d68bc38b02a`, `3cee0f88982fc4d776adbefcf237f2aef31b2d0b5079309780a7bf6b00c11e54`다. 이들은 **web 도구의 렌더링 텍스트/JSON** 해시이며 원본 HTML 바이트 해시가 아니다.

## 검증과 재개

- `python3` 표준 라이브러리로 원문·prepared 식별값, EDT→UTC 분 변환, 스냅샷 결속, scope 보호 파일 11개 SHA 일치를 확인했다. 시장 요청·수집기 실행 0회, 전략·NAV·주문 0회. 코드 변경이 없어 기존 247개 테스트를 재실행하지 않았다.
- `research_input=false`, `performance_eligible=false`, `point_in_time_verified=false`를 유지한다. 한 사건의 금액·날짜 연결은 다른 124개 사건이나 전체 자료 적격성을 증명하지 않는다. 재개하려면 이 사건의 날짜 역할과 과거 최초 공개·수집 시각을 독립적으로 확인할 역사 원문 증거가 필요하다.
- workflow 판단: 도움 됨 — 범위가 고정된 단일 자료 확인에 기존 scope와 원문을 재사용했다.
- 근거: 공식 검색 1회·원문 열기 2회로 종료했고 원본 11개 SHA가 일치했다. 생산 코드 변경과 재수집은 없었다.
- 다음 조정: 유지 — 사건별 근거가 생길 때만 같은 좁은 조회를 수행하고, 날짜만 있는 자료를 정밀 PIT 시각으로 승격하지 않는다.
