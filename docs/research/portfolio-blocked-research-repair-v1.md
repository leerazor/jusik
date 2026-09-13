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

## 복구 상태와 재개 조건

cadence blocker는 `source_paths` resolver가 입력 검증과 metadata 출력을 모두
사용하도록 materialize되어 재개 가능한 상태다. 과거 cadence 구현 테스트에
남아 있던 strict mypy 오류 4건은 별도 보존 이력으로 남아 있으며, 이 복구가
그 테스트나 과거 task를 완료 처리했다고 해석하지 않는다.

calendar blocker의 +1 KRW terminal cash 변조는 새 validator가 거부한다. 다만
보존 synthetic calendar fixture를 `PortfolioInput`으로 다시 읽을 때
normalizer가 `bars`를 필터링하면서 `adjustment_factors`를 함께 동기화하지
않는 별도 문제가 확인되었다. 따라서 calendar 연구의 전체 재개는 이
normalizer/factor 동기화 수정을 별도 offline 작업으로 검토한 뒤에만 가능하다.
검증된 probe 기록은
`/home/kwl/.local/share/jusik/portfolio-audit/portfolio-blocked-research-repair-v1-122f67291266410d8706be0ade14e940/archive-probe-result.json`
에 보존한다.

materializer CLI는 backend 디렉터리에서 다음처럼 실행할 수 있다.

```bash
python -m jusik.research_portfolio_offline_repair \
  /path/to/originals /path/to/repaired
```
