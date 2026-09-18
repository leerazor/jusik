# 작은 진입 초안 provenance 감사

- 상태: 완료
- 기록 시각: 2026-09-19
- 작업 slug: `small-entry-draft-provenance-4840`
- 기준/통합: `824f2a357e9b800050138157814f9078525a15f6` / `2f729585b3aec107cb28f309a2bac9620e4d1fab`
- 범위: 고정 archive의 manifest·역할 경로·원시 SHA·canonical draft SHA·역사 자료 재사용 identity를 오프라인 검증하는 새 validator와 경계 테스트·한국어 문서를 추가했습니다. 전략·성과·PAPER/live·주문 경로는 변경하지 않았습니다.

## 변경과 결정

- `research_small_entry_draft_provenance.py`는 고정된 세 역할 파일만 읽고, 누락·중복·변조·symlink·비정규 파일·출력 덮어쓰기를 fail-closed 처리합니다.
- 결과는 `status=draft`, `runtime_activation_allowed=false`, `prospective_validation_eligible=false`를 유지합니다. 이는 실행 승인이나 미래 성과 검증이 아닙니다.
- 연구 이력에는 provenance 기술 기록만 게시했으며 성과 catalog와 수치는 변경하지 않았습니다.

## 검증

- 관련 pytest 41개 — 통과.
- Ruff check/format 및 strict mypy — 통과.
- 고정 archive CLI replay와 독립 반복 출력 SHA 대조 — 통과.
- 독립 리뷰 — PASS, blocking finding 없음.
- 임시 local research backend/frontend에서 API·웹·3개 artifact의 6개 다운로드 SHA — 모두 HTTP 200 및 일치.

## 안전·운영 상태

- 실제 주문, 외부 market-data 수집, PAPER/live 승격, 운영 DB·서비스·runner 설정, 원격 push — 0회.
- 검증 중 띄운 local backend/frontend는 검증 후 정상 종료했습니다.

## 증거와 다음 시작

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/small-entry-draft-provenance-audit-v1-484028675d0647a0a0b47f86c46a5ca5`; 게시 결과는 `publication.json`입니다.
- history seed SHA: `f9e0ebbe6a78f6a8c2c4e8df7f6f3d86b3270e5f4388d29aa2eaec98b2c2db61`.
- 남은 작업: KOFR 공식 raw receipt와 가격·권리·UTC 경계 자료 없이는 경제 acceptance/OOS 승격을 진행하지 않습니다.
- 다음 시작: roadmap runner와 research-mandate SHA를 다시 확인하고, 실제 외부 자료가 준비된 경우에만 다음 경제 gate를 큐에 등록합니다.

