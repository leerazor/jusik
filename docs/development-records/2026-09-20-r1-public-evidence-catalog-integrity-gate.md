# R1 public evidence catalog 무결성 gate

- 상태: 기술 gate 완료·coverage/PIT/economic acceptance 미완료
- 구현: `public_evidence_catalog_sha256()`가 catalog digest를 재계산하고,
  `verify_public_evidence_catalog()`가 SHA·item count·source count를 검증합니다.
  `build_public_evidence_symbol_coverage()`는 집계 전에 이 검증을 수행하며 변조·불일치
  catalog는 fail-closed로 거부합니다.
- 검증: public evidence 관련 pytest `16 passed`, Ruff, `git diff --check` 통과.
- strict mypy: catalog 자체의 기존 Pydantic decorator 오류와 의존 모듈의 기존 오류가
  남아 non-zero였습니다. 이번 gate 추가로 새 오류가 발생하지 않았습니다.
- 제한: source catalog 무결성은 provider 전체 coverage·PIT completeness·action 사실을
  증명하지 않습니다. R1-05 checkbox, 경제 평가, 원장·성과·PAPER/live 승격은 변경하지
  않았습니다.
