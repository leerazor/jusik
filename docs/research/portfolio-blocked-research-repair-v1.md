# 포트폴리오 차단 연구 복구 어댑터

이 문서는 `portfolio-blocked-research-repair-v1`의 오프라인 복구 경계를
설명한다. 복구기는 보존된 파일을 전용 출력 디렉터리에 복사하고, 원본을
변경하지 않은 상태에서 입력 경로와 회계 끝점을 검증한다. 제품 엔진,
PAPER 엔진·DB, 브로커, 서비스, GPU와 전략 실행은 호출하지 않는다.

## 사용법

어댑터는 preregistration의 `source_paths`를 표준 계약으로 사용한다. 과거
보존 파일의 `input_paths`는 호환 별칭으로만 허용하며 두 키가 함께 있고
값이 다르면 즉시 실패한다.

```python
from pathlib import Path

from jusik.research_portfolio_offline_repair import materialize_repaired_sources

materialized = materialize_repaired_sources(
    Path("/exclusive/audit-output/originals"),
    Path("/exclusive/audit-output/repaired"),
)
```

materializer는 보존된 `cadence.py`와 `calendar.py`의 고정 SHA-256을 먼저
확인한다. 출력 디렉터리는 비어 있거나 새로 만든 경우에만 사용할 수 있고,
복구된 두 소스와 `materialization-manifest.json`은 exclusive 생성된다. 실제
preregistration 입력을 읽는 adapter는 `source_hashes`에 선언된 항목만
검증한다. 현재 frozen preregistration은 source path 5개와 source hash 3개를
가지므로, 나머지 경로에 해시를 추정해 추가하지 않는다.

독립 ledger 재구성이 끝나면 `validate_terminal_accounting`을 호출한다.
재구성 현금은 마지막 equity point의 cash와, 재구성 현금과 terminal position
value의 합은 metrics의 최종 NAV 및 마지막 equity의 NAV와 각각 비교한다.
빈 equity, 비유한 Decimal, 기존 residual 허용치 초과는 모두 거부된다.

```python
validate_terminal_accounting(
    simulation,
    reconstructed_cash,
    terminal_position_value,
    residuals={"trade": existing_trade_residual},
)
```

이 구현은 과거 차단 attempt의 이력을 고치거나 연구 결과를 완료 처리하지
않는다. 새 연구를 재개할 때도 원본 manifest·SHA와 별도 승인된 실행 조건을
먼저 확인해야 한다.
