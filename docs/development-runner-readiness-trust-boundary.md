# 외부 readiness 실행 신뢰 경계 결정안

- 상태: 사용자 결정 대기, 미승인·미적용. 구현은 계속 `PENDING`입니다.
- 범위: producer/validator 실행과 그 증거를 누가 통제하는지에 관한 설계 결정입니다. 기존 연구 위임 조건, 시장자료 수용 규칙, 투자 기준과 gate는 바꾸지 않습니다.

## 우선 사용자 결정: 독립 실행과 trust-root 통제 주체

현재 v1 consumer는 외부에서 제공한 `ReadinessExpectations`와 receipt 및 provenance를 대조하지만, launcher가 특정 bytes를 실제 실행했는지 또는 실행자가 receipt를 만들었는지는 인증하지 않습니다. 기존 expanded-universe 자료에는 과거 collector 실행 source hash가 없고(null), 확인된 독립 trust-root owner나 control channel도 없습니다. 현재 파일의 hash만으로 과거 실행을 증명할 수 없습니다. 따라서 producer가 기록한 self-report만으로는 실행 주체와 receipt의 독립 결속을 만들 수 없으며, 이 경계는 구현되어 있지 않습니다.

**권고하는 역할 분리:** producer와 validator 모두로부터 독립된 trust-root owner가 최초 신뢰 기준을 설정하고 이후 갱신·철회를 통제합니다. 별도의 run controller는 승인된 immutable producer/validator snapshot만 실행하고, 실제 source 및 output bytes를 hash해 task, attempt, receipt 증거에 결속합니다. owner와 controller의 실제 인물·조직, 권한, 통신·배포 경로는 아직 정하지 않았으며 현재 존재한다고 가정하지 않습니다.

사용자에게 필요한 결정은 이 두 독립 역할을 채택할지, 그리고 각 역할과 독립 control channel을 무엇으로 지정하고 어떻게 증명할지입니다. 지정된 owner와 channel이 선택되고 권한 분리가 입증되기 전까지 어떤 구현이나 임시 trust policy도 적용하지 않습니다. 그 전에는 readiness가 `PENDING`으로 남습니다.

역할 분리를 구현할 수 있는 후보는 다음 두 가지입니다.

| 후보 | 역할 배치 | 장점 | 한계와 운영 부담 |
| --- | --- | --- | --- |
| 보호된 저장소 manifest + 별도 controller | 저장소의 보호된 승인 절차가 producer/validator hash manifest를 보관하고, 별도 run controller가 승인 snapshot을 실행해 실제 source/output hash를 기록합니다. trust-root owner는 producer/validator와 독립된 권한 및 control channel을 가져야 합니다. | 기존 저장소와 오프라인 절차를 활용할 수 있어 추가 서비스가 필요 없을 수 있습니다. manifest 변경 이력도 검토할 수 있습니다. | 저장소 보호만으로 controller가 실행한 bytes나 receipt 생성 주체가 증명되지는 않습니다. 저장소 관리자와 trust-root owner의 권한이 겹치거나 분리가 확인되지 않으면 독립성이 성립하지 않습니다. controller의 실행·증거 보존 경계를 별도로 운영해야 합니다. 현재 그러한 권한 분리가 확인되지 않았습니다. |
| 별도 host/attestation service | producer 및 manifest 저장소와 분리된 host/service가 run controller 기능과 실행 증거 생성을 맡고, 독립 trust-root owner가 그 신뢰 기준을 통제합니다. | 저장소·producer와 실행 통제의 권한을 분리하기 쉽고 실제 실행과 output hash를 한 경계에서 기록할 수 있습니다. | 별도 host/service의 소유·권한·credential·가용성·백업·복구와 비용을 운영해야 합니다. 서비스가 있다고 가정할 수 없고, 그 자체로 독립성이 증명되는 것도 아닙니다. |

이 비교는 승인된 설계 선택지가 아닙니다. 사용자 결정은 실제 주체와 control channel을 지정하고 권한 경계를 증거로 확인할 때까지 미완료입니다. 어느 후보도 선택·배포·구현하지 않으며, 구체적인 pin, attestation 또는 실패 정책을 미리 정하지 않습니다.

## 별도 승인 대상인 후속 결정

아래 항목은 우선 역할 결정과 구별되는 후속 설계·구현 범위입니다. 각각 필요한 시점에 별도 사용자 승인을 받아야 하며, 우선 결정을 승인해도 자동 승인되지 않습니다.

| 후속 결정 | 별도 승인으로 정할 내용 |
| --- | --- |
| Attestation schema와 publication | task/attempt, 실행 snapshot, 실제 source/output hash, raw receipt hash의 증거 형식, 생성·검증·원자 공개 책임과 보존 경계 |
| v1 bridge | 독립 검증 결과를 기존 `ReadinessExpectations` 및 v1 consumer에 전달하는 방식과 별도 구현 범위 |
| Hash/key 변경·철회 및 freshness | producer와 validator hash 변경 이력, 서명 key와 root 갱신·철회 통제, 오프라인 검증의 철회 상태 최신성 기준 |
| 과거 receipt | 과거 실행 hash가 빠진 receipt의 상태 및 손상·철회 이후 과거 receipt 효력 처리 |
| 실패와 복구 | 불완전하거나 검증할 수 없는 실행의 artifact 보존·격리, 재개 책임과 새 attempt 처리 |
| Scheduler 연결 | 검증된 receipt를 scheduler가 재평가에 사용하는 별도 연결 범위. 이것만으로 gate 통과나 OOS·투자 승인을 뜻하지 않음 |

이 문서는 설계 결정과 후속 승인 경계만 기록합니다. publisher, execution attestation, trust-root pin, scheduler binding은 구현되어 있지 않으며, 실제 owner와 control channel이 선택되고 검증될 때까지 `PENDING`입니다.
