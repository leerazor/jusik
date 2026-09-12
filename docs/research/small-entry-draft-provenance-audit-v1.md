# 작은 진입 초안 provenance 감사 v1

이 도구는 보관된 작은 진입 preregistration 초안 bundle의 provenance를 오프라인에서 검증한다. 입력은 읽기 전용으로 다루며 데이터베이스, 네트워크, 시세 수집, PAPER 엔진, 주문 실행을 호출하지 않는다.

## 사용법

```bash
cd backend
.venv/bin/python -m jusik.research_small_entry_draft_provenance \
  --bundle-root /path/to/small-entry-preregistration-draft-v1-a55b6ee8a036463da688fafe04567542 \
  --output-dir /path/to/empty-output
```

`manifest.json`의 원시 SHA-256, 세 역할의 정확한 절대 경로와 선언된 SHA-256, 실제 파일 SHA-256, 초안의 canonical SHA-256을 순서대로 확인한다. 초안은 기존 `SmallEntryPreregistrationDraft` 모델로 다시 검증하며 역사 진입 금액 분포와 원본 preregistration의 identity가 초안 선언과 일치하는지도 확인한다. bundle의 다른 manifest 항목은 열지 않는다.

성공하면 출력 디렉터리에 `public-manifest.json`과 `report.md`를 만든다. 두 파일에는 역할, raw/canonical SHA-256, 별도 identity, 검증 결과와 역사 자료 재사용·전향 검증 부적격·활성화 금지만 담기며 로컬 경로와 실행 시각은 담기지 않는다. 출력은 결정적이므로 같은 입력에서 byte 단위로 같다.

이 결과는 `status=draft`이고 `runtime_activation_allowed=false`인 감사 증거다. 검증 통과가 실행 승인이나 전향 검증 결과를 의미하지 않는다.

## 신뢰 경계

검증은 고정된 보관 snapshot의 네 파일과 원본 manifest 선언이 서로 일치하는지만 증명한다. manifest의 역할 경로는 원본 archive의 절대 경로로 고정되며, 네 파일을 다른 bundle root로 옮길 때도 파일 내용과 manifest의 원본 경로를 그대로 보존해야 한다. 임의 suffix가 붙은 경로는 역할로 인정하지 않는다.

이 결과는 자료의 외부 진본성, 연구 성능, 미래 자료에 대한 전향 검증, 실행 가능성을 증명하지 않는다. 역사 자료 재사용과 `runtime_activation_allowed=false` 계약은 검증 성공 뒤에도 유지된다.
