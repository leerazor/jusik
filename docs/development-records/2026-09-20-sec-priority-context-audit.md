# SEC priority context audit

- 상태: 비권위 검토 보조 완료; operator verification·ledger 적용 보류
- 기록 시각: 2026-09-20T05:35:00Z
- 입력: 기존 priority packet 8개와 local SEC HTML 원문만 읽었습니다. 원문·queue·form은
  수정하지 않았습니다.

## 확인된 검토 주의점

- `ADAMI` filing은 common/preferred 여러 class의 배당을 함께 언급하지만 본문만으로
  단일 보통주 amount·ex-date를 확정하지 않습니다.
- `ATXG` filing은 1-for-15 reverse split을 보상 grant 조정 맥락에서 언급합니다.
- `AVX` filing은 1:2~1:12 reverse split 승인 범위를 언급하며 실제 ratio/effective date를
  확정하는 후속 원문이 필요합니다.
- `BMRC` filing은 `$0.25` cash dividend와 record/payable date를 언급하지만 ex-date와
  대상 share basis를 별도 확인해야 합니다.
- `IMUX` filing은 1-for-10 reverse split, amendment/effective 및 거래 개시 시점을
  언급하지만 action ledger용 법적·가격 적용 경계를 operator가 확인해야 합니다.
- `RWT` 두 filing 중 하나는 common/preferred 현금배당, 다른 하나는 dividend-equivalent
  rights를 다루므로 동일한 dividend action으로 합치면 안 됩니다.

이 내용은 자동 추출 사실이나 승인 사실이 아니며, `operator_verified=false` 상태를
유지합니다. 특히 symbol/source identity와 PIT link는 정본 queue 및 원문 대조 후 별도
확정해야 합니다.

## 다음 조건

operator가 양식의 필수 facts·revision/content hash·PIT link를 채운 뒤 정본 queue 연결
validator가 `ready=true`를 반환해야 `ReviewManifest` 검토를 시작할 수 있습니다. 그 전에는
action ledger, NAV, 성과, PAPER/live에 적용하지 않습니다.
