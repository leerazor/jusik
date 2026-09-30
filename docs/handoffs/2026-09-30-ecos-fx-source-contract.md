# ECOS 환율 원천 계약 인계

- 갱신: 2026-09-30T04:44:15Z. 저장소 `/home/kwl/projects/jusik`, `main`; 통합 `cbd63b9ad5298096f0424a18ab07f4291bf55c5f`. 전용 worktree와 브랜치는 통합 검증 후 정리했다.
- 목표·상태: 공식 ECOS 항목과 한국은행 산정 기준을 기존 진단 문서에 반영하는 문서 작업. [사용 문서](../ecos-fx-comparison.md)와 [개발 기록](../development-records/2026-09-30-ecos-fx-source-contract.md)에 결정·근거를 남겼다.
- 확인된 범위: ECOS 첫 10행 항목 응답은 `731Y001/D/0000001`을 원/미국달러 매매기준율·원 단위로 표시한다. 해당 응답은 최초 공표시각·vintage를 제공하지 않는다. 한국은행 FAQ는 최근 거래일 미달러 현물환율의 거래량 가중평균을 설명한다. 관측일·기초 거래일 mapping, 정확한 갱신시각, 과거 revision은 미확인이다.
- 적용 경계: FRED 뉴욕 정오 매입환율과의 차이를 오류·성과로 해석하거나 ECOS로 결손을 자동 보충하지 않는다. NAV/PIT·성과 적용과 임의 1일 지연은 보류한다. 재개에는 날짜 의미, 공표 시간대·최초 사용 가능 시점, revision/vintage, 기존 FX 적용 계약 정합성 검증이 필요하다.
- 검증: `verification.json`의 backend 소스·테스트 2개, 조회 산출물 6개, baseline 1개 해시 일치 및 backend tree 불변. 이번 작업에서 공식 항목 metadata와 FAQ를 새로 확인·보존했고 두 자료의 해시는 manifest와 일치한다. 기존 통합 pytest 182개·Ruff·strict mypy 증거를 재사용했으며 전체 테스트와 기존 4일 환율 재조회는 생략했다. manifest SHA-256 `e47a5ea28a90b05c4963702b515693693f8617da9ea776902bf29bfcd8767188`.
- 운영: 감독자 확인 시점에 systemd runner는 paused, service/timer inactive, 실행 task 없음. 같은 thread의 Codex heartbeat `automation`은 ACTIVE·30분 간격(Toss 제외). 중복 writer를 막기 위해 기존 runner를 동시에 재개하지 않는다. 실제 주문·배포·원격 push 없음.
- 완료: 독립 review PASS 및 main 문서 일치·상대 링크·출처 SHA·backend 불변·diff 검사 통과. 증거는 `/home/kwl/.local/share/jusik/portfolio-audit/20260930-ecos-fx-source-contract/integration-verification.json`. 이번 문서 작업의 남은 필수 단계 없음.
- 다음 행동: 현재 mandate와 작업 등록부에서 실제 READY 연구 후보를 확인해 작은 독립 작업을 고른다. 동일 ECOS 근거 재조회는 반복하지 않는다. 과거 DART 키 부재 등 외부 상태는 다음 필요 시 새로 확인하며 비밀값을 기록하지 않는다.

다음 세션 시작: “이 인계와 현재 mandate·작업 등록부를 확인하고 실제 READY 연구 후보 중 다음 좁은 작업을 선정해줘.”
