---
name: artificial-analysis-model-efficiency
description: Fetch sanitized Artificial Analysis model data and compare benchmark quality and costs without automatic cheap-first routing.
---

# Artificial Analysis 모델 비교

첫 시도 해결 품질을 우선합니다. 가격이나 Intelligence Index만으로 모델을 낮추거나 실패 뒤 저가 모델로 재시도하지 않습니다. 같은 과제에서 품질이 동등하다는 검토 근거가 있을 때만 실제 작업 비용을 함께 비교합니다. 근거가 없으면 현재 명시 선택을 유지합니다.

프로젝트 디렉터리에서 실행합니다.

```bash
python "${CODEX_HOME:-$HOME/.codex}/skills/artificial-analysis-model-efficiency/scripts/analyze_models.py" \
  --env-file .env --json-output /path/to/private-audit/aa-catalog.json
```

helper는 dotenv의 지원 API-key 변수만 읽으며 shell로 실행하지 않습니다. API-key를 출력하거나 저장하지 않습니다. 기존 `ARTIFICAL_ANALYSIS_API`와 표준 Artificial Analysis 변수명을 지원합니다. pagination을 끝까지 확인하고 다른 origin으로 인증 헤더가 전달되는 redirect를 거부합니다. `--json-output`은 지정 파일을 원자 교체하며 원시 응답과 인증 자료는 저장하지 않습니다.

기본 보고서는 모델별 Index·benchmark task cost·token 가격과 Pareto 상태를 보여주는 참고 자료입니다. 추천 순위나 Index/price 기반 자동 선택이 아닙니다. 누락된 비용은 unknown으로 남깁니다. 과거 band 보고서가 명시적으로 필요할 때만 `--band-width 5`를 사용합니다.

JSON schema v1은 `schema_version`, UTC `fetched_at`, `index_version`, `response_sha256`, `complete`, `models`를 담습니다. 모델 항목은 `aa_slug`, `index`, `benchmark_task_cost_usd`, `input_usd_per_million`, `output_usd_per_million`뿐입니다. 숫자는 Decimal 문자열 또는 null입니다. `complete`는 검증한 전체 API pagination에서 추출한 OpenAI catalog가 완전함을 뜻합니다.

결과에는 조회 시각, Index 버전, 응답 hash와 [Artificial Analysis 출처](https://artificialanalysis.ai/data-api/docs)를 표시합니다. benchmark task cost는 실제 Codex 작업 비용이 아닙니다. token 가격은 USD per million tokens입니다. free 응답만으로 현재 지원·폐기 상태나 host model 가용성을 판단하지 않습니다.

## jusik 선택에 반영

`.codex/model-routing.json`, `backend/jusik/model_routing.py`, `docs/agent-tooling.md`를 먼저 읽습니다. JSON은 비교·검토 자료이며 runtime이 가격으로 선택하지 않습니다. 정확한 AA slug와 host model+effort 쌍을 확인하고, 과제 품질 근거와 사용자 지시에 따라 중앙 `profiles.<profile>.selected`를 명시 변경합니다. registry에 없는 model/effort를 임의 추정하지 않습니다. 품질이 더 높은 모델을 가격 때문에 제외하지 않습니다. 같은 점수나 같은 pass count만으로 품질 동등성을 주장하지 않습니다.

중앙 선택은 native `resolve`/`check`, roleless adapter, runner가 함께 읽습니다. 호출 권한, 독립 검토와 중대 진단 escalation 조건은 모델 비교와 별도입니다. 이미 로드된 named role의 hot reload는 주장하지 않습니다. 글로벌 skill 설치와 중앙 정책 변경은 사용자가 요청한 작업 범위에서 수행합니다. 일반 프로젝트에서도 이 helper는 jusik backend 없이 사용할 수 있습니다.
