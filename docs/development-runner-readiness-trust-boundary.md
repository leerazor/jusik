# 외부 readiness trust-boundary 결정안

- 상태: 준비용 초안, **미승인·미적용**. publisher·scheduler 구현이나 신뢰 기준 확정이 아닙니다.
- 범위: 실행 신원, 독립 hash pin과 receipt publication만 다룹니다. mandate, 시장자료 허용, 투자 gate, FINAL_VALIDATION/OOS는 변경하지 않습니다.

## 현재 검증 경계

v1 consumer는 receipt 밖에서 온 `ReadinessExpectations`와 receipt/provenance를 비교합니다. 여기에는 task/attempt, request criteria, receipt SHA, producer/validator ID와 source SHA가 포함됩니다. 그러나 consumer는 launcher가 해당 bytes를 실제 실행했는지, 실행자가 그 receipt를 만들었는지 인증하지 않습니다. producer가 pin된 hash 문자열을 provenance에 복사하는 것만으로는 실행 증명이 되지 않습니다. 따라서 source pin과 실제 `task/attempt → 실행 snapshot → receipt SHA`를 묶은, 독립 검증 가능한 실행 증거가 함께 필요합니다. 현재 v1에는 이 attestation 경계가 구현되어 있지 않습니다.

기존 expanded-universe 자료에는 과거 collector 실행 SHA가 없습니다(null). 현재 파일의 hash는 과거 실행을 증명하지 않습니다. validator receipt 및 원자 publication 경계도 없습니다. 8개 gate는 `BLOCKED`, scheduler와 held-band OOS는 각각 기존 조건에 따라 `PENDING/BLOCKED`입니다.

## 권고안과 대안

| 선택지 | 실행 주체와 독립 pin 경로 | 장점 | 부담·한계 |
| --- | --- | --- | --- |
| **A. 분리 실행자와 서명된 실행 attestation** | producer와 별도 운영자가 immutable producer/validator snapshot을 pin된 manifest로 승인하고, 별도 권한의 launcher가 그 snapshot만 실행합니다. attestor는 실행을 직접 감독하고 실제 snapshot/output bytes에서 hash를 계산해 task/attempt, criteria digest, 두 source hash, raw receipt SHA를 묶어 별도 보유 키로 서명·원자 게시합니다. 오프라인 verifier는 producer가 아닌 경로에 독립 배포된 trust root로 이를 검증한 뒤 v1에 독립 기대값을 제공합니다. | 승인된 source identity와 실제 실행·receipt를 가장 강하게 연결합니다. | v1은 attestation을 읽지 않으므로 verifier/bridge 계약의 별도 설계·review가 필요합니다. 최초 공개 trust root의 독립 bootstrap, 배포, 검증기 갱신, 서명키 보관·백업·회전·철회 책임과 운영이 추가됩니다. root와 manifest를 같은 권한자가 바꿀 수 있으면 순환 신뢰입니다. 현재 이런 기반이 있다고 가정하지 않습니다. |
| B. 보호된 저장소의 reviewer 승인 manifest | producer와 권한이 분리된 reviewer가 producer·validator source hash의 versioned manifest를 승인합니다. launcher는 해당 불변 snapshot을 실행합니다. producer와 분리된 trusted run controller가 실제 실행을 관찰하고 snapshot/output hash를 계산해야 합니다. | 무료·오프라인으로 가능하고 source hash 변경 이력이 남습니다. 별도 키 기반이 없어 운영이 비교적 단순합니다. | 보호된 review 권한과 run controller 권한이 실제로 분리되어야 합니다. manifest만으로 실행 여부나 receipt 생성 주체를 증명하지 못하므로 실행 증거가 없으면 `PENDING`입니다. 현재 branch protection·독립 owner가 이 보장을 제공한다고 확인된 바 없습니다. |
| C. 별도 host/attestation service | producer·저장소와 분리된 host/service가 source pin, 실행, receipt hash attestation과 배포를 맡습니다. 검증기는 별도 trust root를 사용합니다. | repo/producer 권한과 실행 증거를 분리하기 쉽습니다. | 권한·credential, 가용성·복구, 서비스 운영과 실제 비용이 생길 수 있습니다. 현재 존재나 구매를 전제하지 않습니다. |
| D. producer self-report 또는 사후 현재-file hash | producer가 receipt에 hash를 기록하거나 실행 뒤 현재 source를 hash합니다. | 디버깅에는 저렴하고 간단합니다. | 독립 pin도 실행 증명도 아닙니다. 진단에만 쓰고 trust 근거로는 거부해야 합니다. |

**조건부 권고:** 지금은 publisher를 보류합니다. 최소 비용의 다음 설계 후보는 독립 reviewer 권한 분리가 실제 확인될 때만 B를 source allowlist로 검토하고, 별도의 authenticated execution-to-receipt 증거를 반드시 요구하는 것입니다. 현재 그 실행 증거 경로와 reviewer 권한 분리는 확인되지 않았으므로 어떤 안도 적용하지 않고 `PENDING`을 유지합니다. 위협 모델상 저장소·실행 host 관리자의 변조도 방어해야 한다면 A/C의 별도 attestor와 trust-root bootstrap을 먼저 결정해야 합니다. 이는 설계 권고이며 승인이나 provisional trust 기준이 아닙니다.

## 갱신·철회, 실패와 복구

- producer와 validator hash는 별개로 pin합니다. 변경은 기존 값을 덮어쓰지 않고 승인자, 적용 시점/attempt 경계, 이전·신규 hash가 남는 새 manifest generation으로 추가합니다. 새 실행 전에 고정된 snapshot과 pin을 대조합니다.
- 서명을 택하면 key 회전과 hash 변경을 분리 기록합니다. 신규 key는 이미 신뢰된 root 또는 별도 승인된 bootstrap 절차로 등록하고, verifier가 root를 읽는 독립 배포 경로와 root 업데이트 권한도 기록해야 합니다. 철회 상태는 독립 배포된 단조 증가 generation과 유효기간으로 최신성을 검사하고, verifier는 마지막으로 본 generation을 되돌릴 수 없어야 합니다. Offline 검증은 trusted clock으로 expiry를 확인해야 합니다. verifier가 generation을 안전하게 보존하지 못하거나 현재 상태를 인증할 수 없으면 stale 여부가 불명확한 것으로 fail closed합니다. 철회 상태가 없거나 만료·stale이면 fail closed합니다. 오프라인 verifier에 즉시 전파된다고 주장하지 않으며, 즉시성은 신선한 상태가 실제 배포·확인된 범위에 한정됩니다. 과거 receipt를 삭제·수정하지 않습니다. 손상 시점을 입증할 수 없을 때 과거 receipt의 효력을 취소할지는 사용자 결정입니다.
- pin/attestation 누락, unknown·revoked key, source/validator/attempt/receipt SHA 불일치, dirty snapshot, 부분 게시, 철회 상태 누락·만료·generation rollback, 검증 실패는 fail closed합니다. 독립 기대값을 제공하지 않고 task만 `PENDING/BLOCKED`로 둡니다. self-report fallback, 자동 gate 승격, scheduler/OOS 재개는 하지 않습니다.
- 실패 attempt와 원본 artifact는 보존하고 불완전한 staging은 격리합니다. 원인 수정 후 새 pin generation·새 attempt로 실행합니다. 독립 verifier가 실행 attestation과 raw receipt SHA를 확인한 다음 v1 consumer에 기대값을 전달해 재검증합니다. 과거 null 실행 hash는 소급 보완하지 않습니다. `bound`여도 gate 상태는 별도이며 자동 변경하지 않습니다.

## 검증·운영 부담

선택된 경계의 test-only fixture는 source/validator mismatch, task·attempt·receipt SHA 불일치, unknown/revoked key, 최초 root 교체, key 회전, 누락·만료·rollback된 철회 generation, dirty source, 중복·부분 게시, restart 복구를 검증해야 합니다. 정상 경로도 독립 verifier가 실행 증거를 확인하고 v1 consumer가 독립 `ReadinessExpectations`로 receipt를 다시 읽는 것까지 확인합니다. 실패는 `bound`와 gate 승격 없이 종료해야 합니다. scheduler/OOS는 이 증명과 별개의 승인 단계입니다.

B는 독립 reviewer와 저장소 권한 보호 부담, A는 root/key 수명주기와 bridge 개발 부담, C는 운영·권한·credential·비용 부담이 큽니다. 어느 선택에도 manifest 승인자, 실행 책임자, 철회 권한자, 복구 담당자의 실제 지정이 필요합니다.

| 사용자 결정 필요 | 정해야 하는 내용 |
| --- | --- |
| 실행 주체·신뢰 범위 | 현재 collector를 유지할지 분리 launcher/host를 둘지, producer·repo·host 관리자 중 누구를 신뢰 경계 밖에 둘지 |
| 독립 pin과 trust root | hash manifest의 owner·저장·배포 경로, 최초 public root의 bootstrap 채널·owner, root를 verifier에 업데이트할 권한; 같은 repo/reviewer 분리로 충분한지 |
| 실행-결과 증명 | task/attempt·snapshot·receipt SHA를 누가 인증할지, 독립 verifier와 v1 사이 bridge를 별도 구현 범위로 승인할지 |
| 갱신·철회 | hash/key 회전 및 긴급 철회 권한, offline verifier가 허용할 철회 상태 최대 age와 stale 시 동작, 손상 시 과거 receipt 효력·재실행 범위 |
| 실패·복구 | fail-closed 및 artifact 보존 권고 채택 여부, 새 attempt 승인·운영 책임자 |
| 후속 연결 | 검증된 receipt 이후 scheduler 재평가를 별도 scope로 시작할지. 이것은 gate/OOS/투자 승인과 별개입니다. |

이 결정 전에는 권고와 대안 모두 참고 초안입니다. publisher, trust pin, execution attestation, scheduler binding은 구현하지 않습니다.
