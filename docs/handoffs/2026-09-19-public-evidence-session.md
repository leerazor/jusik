# 2026-09-19 공개 evidence 자동수집 세션 인계

- 갱신: 2026-09-20T07:20:00+09:00
- 저장소: `/home/kwl/projects/jusik`
- branch: `main`
- 현재 로컬 HEAD: `0541f1f` (`docs: update SEC candidate handoff`); 원격 push 없음.

## 목표와 상태

무료 공개 자료만으로 R1-02/R1-04/R1-05의 수동 수집을 줄이는 자동 evidence 경로를
구축했습니다. 기술 slice는 완료했지만 전체 R1 acceptance와 strict PIT coverage는
아직 미완료입니다.

## 완료

- `backend/jusik/research_public_evidence.py`: Nasdaq Trader RSS 날짜별 거래중단 원문,
  source URL, 관측 시각, symbol/reason, SHA-256 보존.
- `backend/jusik/research_sec_evidence.py`: SEC submissions JSON, accession/form,
  filing/acceptance 시각, primary document, 관측 시각, SHA-256 보존.
- `docs/continuous-development-session.md`: 3시간 세션 정책과 2026-09-20 02:22:09
  KST 마감 시각을 실행기 필수 문서로 고정.
- `docs/development-records/2026-09-19-public-halt-evidence.md`: 개발 기록.
- `backend/jusik/research_alpha_actions.py`: Alpha Vantage `DIVIDENDS`/`SPLITS`
  원문·배당/분할 날짜·수량·관측 시각·SHA-256 보존. 실제 NVDA 2024–2025 응답
  10건을 파싱했습니다.
- `backend/jusik/research_public_evidence_catalog.py`: 세 공급자의 evidence를
  source-specific identity와 raw SHA로 결합하고 `coverage=incomplete`를 강제합니다.
- 2026-09-20 bounded batch: 미국 registry 10개 심볼에서 Alpha 53 actions와 Nasdaq
  raw 45건(요청 기간 catalog 27건)을 수집했습니다. Nasdaq HTML symbol parser 결함을
  수정하고 기존 raw 재파싱에서 `SYMBOL` 오인식 0건을 확인했습니다.
- SEC ticker map으로 8/10 심볼을 CIK에 매핑해 submissions 6,243건을 수집했고,
  요청 기간 catalog에 1,517건을 연결했습니다. SOXL/TQQQ는 매핑 누락으로 기록했습니다.
- SEC accession의 primary document URL 재현과 본문 키워드 후보(`SecFilingCandidate`)를
  추가했습니다. 후보는 `candidate/incomplete` 성격이며 권리·가격 확정이나 acceptance
  승격에 사용하지 않습니다.
- 2024–2025 범위에서 SEC 8-K/8-K/A 문서 3건을 bounded fetch했습니다. 3건 모두 raw
  저장에 성공했고 후보는 merger 1건·빈 후보 2건입니다. audit 경로는
  `/home/kwl/.local/share/jusik/portfolio-audit/20260920-sec-filing-candidates/`입니다.
- 최대 3개 문맥 snippet을 `candidates.json`으로 저장했으며, merger 후보가 XBRL 문맥의
  정규식 false positive일 수 있음을 확인했습니다. 따라서 event 승격은 보류합니다.
- 승격 시에는 기존 `research_action_review.py`의 `ReviewInput`/`ExtractedFacts`/
  `ActionReview` 계약을 재사용하고, 자동 원장 적용 금지·날짜/금액/권리 비교를 통과해야
  합니다. SEC 후보에 별도 승격 경로는 만들지 않았습니다.
- `build_sec_action_review_input()`을 추가해 위 경계를 코드로 고정했습니다. operator
  verification·수동 facts·단일 split/dividend 후보가 없으면 fail-closed입니다.

## 검증

- SEC 관련 pytest 5개 및 Ruff 통과.
- 전체 backend pytest는 1615 passed, 7 failed. 실패는 기존 investor 상태 기대치,
  frozen archive/hash, prospective status 기대치에 해당하며 이번 SEC 파일 변경과 무관합니다.
- Nasdaq RSS 실제 1일 조회 45건 성공.
- SEC CIK 1045810 실제 submissions 조회 1,000건 성공.
- API key, 주문, PAPER/live, 운영 DB/원격 설정 변경 없음.

## 운영

- roadmap runner timer/service: inactive (수동 작업과 자동 실행 충돌 방지를 위해 유지)
- Windows 종료는 handoff 저장 후 별도 요청 범위로 남겼으며, 종료하면 현재 실행 세션이
  끊기므로 이 기록을 먼저 저장했습니다.
- 기존 루트 `HANDOFF.md`는 사용자 작성 이력으로 보존하고 수정하지 않음.

## 남은 작업

1. SEC 후보 adapter를 실제 수동 review manifest/audit에 연결하되, 확정 event 승격 조건을
   먼저 정의.
2. 전체 대상 기간의 halt coverage를 공식 자료로 확장하되 호출 예산과 PIT 한계를
   명시적으로 기록.
3. SEC filing에서 corporate-action event를 추출하되 원문 accession과 acceptance 시각을
   유지하고, 불완전 coverage는 성공으로 표시하지 않음.
4. 중복 운영 문서는 삭제하지 말고 canonical 문서 링크만 정리한 뒤 최종 검증.
5. 세션 종료 전 최종 테스트·커밋 상태를 확인. 원격 push는 금지.

다음 세션 시작 명령: 이 파일과 `docs/continuous-development-session.md`를 읽고 `git
status`, runner 상태, 원격 HEAD를 확인한 뒤 Alpha Vantage evidence 연결부터 재개합니다.
