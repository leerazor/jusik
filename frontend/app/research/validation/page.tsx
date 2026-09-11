import Link from "next/link";
import {
  getBoundaryEvidence,
  getBoundaryCaptureStatus,
  getLatestPortfolioRobustness,
  getProspectiveReadiness,
  getProspectiveRegistrationStatus,
  getSignalValidation,
  researchAmount,
  type BoundaryEvidence,
  type PortfolioRobustness,
  type BoundaryCaptureStatus,
  type ProspectiveReadiness,
  type ProspectiveRegistrationStatus,
  type SignalValidation,
} from "@/lib/research";

export const dynamic = "force-dynamic";

type PageProps = { searchParams: Promise<{ local_date?: string }> };

const evidenceLabels = {
  captured: "실제 사용 시세 보존",
  legacy_sample_only: "기존 분 표본만 보존",
  missing: "증거 없음",
  mismatch: "체결 정보 불일치",
} as const;

const aggregateLabels: Record<string, string> = {
  selected_base: "fold별 사전 선택",
  fixed_base: "고정 후보",
};

const prospectiveStatusLabels: Record<ProspectiveRegistrationStatus["status"], string> = {
  not_registered: "미등록",
  planned: "등록 완료 · 시작 전",
  observing: "미래 관측 진행 중",
  window_elapsed: "관측 기간 종료 · 통과 판정 아님",
  identity_mismatch: "등록 identity 불일치",
  invalid_contract: "등록 계약 검증 실패",
};

const prospectiveMetricLabels: Record<string, string> = {
  net_return_pct: "비용 차감 원화 수익률",
  nav_max_drawdown_pct: "NAV 최대 낙폭",
  turnover_pct: "시작 NAV 대비 회전율",
  transaction_cost_krw: "거래 비용",
  fx_cost_krw: "환전 비용",
  execution_quote_evidence: "실제 체결 시세 근거",
};

const boundaryStateLabels: Record<ProspectiveReadiness["start_boundary"]["state"], string> = {
  not_due: "경계 전",
  missing: "exact checkpoint 없음",
  unverified_candidate: "미검증 후보",
};

const executionStateLabels: Record<ProspectiveReadiness["execution_evidence"]["state"], string> = {
  unobserved: "체결 미관측",
  linked_integrity: "sidecar 연결 무결성 확인",
  incomplete: "체결 근거 불완전",
};

const captureStateLabels: Record<BoundaryCaptureStatus["boundaries"][number]["state"], string> = {
  scheduled: "경계 대기",
  collecting: "원시 snapshot 수집 중",
  captured_raw: "원시 snapshot 보존",
  captured_with_issues: "누락·제한 포함 원시 snapshot",
  error: "수집 오류",
};

const evidenceCheckLabels: Record<BoundaryEvidence["checks"][number]["state"], string> = {
  pass: "확인",
  fail: "모순",
  unknown: "확인 불가",
  not_applicable: "판정 대상 아님",
};

const boundaryEvidenceStateLabels: Record<BoundaryEvidence["state"], string> = {
  not_due: "경계 전",
  missing: "원시 기록 없음",
  unavailable: "검사 불가",
  inspected: "부분 일관성 검사 완료",
};

const boundaryEvidenceCheckNames: Record<string, string> = {
  artifact_integrity: "파일 내용 무결성",
  snapshot_identity: "session·정책·source 일치",
  capture_completeness: "원시 수집 생략 여부",
  captured_counts: "표별 건수 일치",
  duplicate_identifiers: "식별자 중복",
  input_payload_hash: "입력 원문 SHA 재검증",
  detail_limit: "상세 표시 한도",
  ledger_commit_timing: "원장 반영 시각",
  corporate_action_completeness: "기업행동 완결성",
  valuation_policy: "경계 가격·환율 선택",
  session_identity: "체결 session",
  decision_reference: "판단 참조",
  input_reference: "입력 참조",
  input_timing: "입력 cutoff·기록 시각",
  execution_quote_reference: "실제 사용 시세 참조",
  symbol_consistency: "종목 일치",
  timestamp_consistency: "시장·수신 시각 일치",
  execution_currency: "체결 통화 출처",
  execution_price: "체결가 산술",
  execution_quote_hash: "시세 원문 SHA 재검증",
  notional_arithmetic: "원화 거래대금 산술",
  cost_range: "비용 값 범위",
  decision_timing: "판단 뒤 시장·수신 시각",
  decision_expiration: "처리 시각 기준 만료",
  boundary_timing_diagnostic: "경계 전후 진단",
  latest_price_candidate: "최신 시세 후보",
  latest_price_boundary_timing: "경계까지 수신된 시세 후보",
  historical_price_candidate: "과거 가격 후보",
  fx_candidate_availability: "환율 후보 이용 가능 시각",
  point_in_time_selection: "경계 시점 자료 선택",
};

function utcDate(offsetDays = 0) {
  const value = new Date();
  value.setUTCDate(value.getUTCDate() + offsetDays);
  return value.toISOString().slice(0, 10);
}

function validLocalDate(value: string | undefined) {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : undefined;
}

function ProspectivePanel({ result }: { result: ProspectiveRegistrationStatus | null }) {
  if (!result) {
    return <section className="panel pending-panel"><h2>미래 평가 등록 상태를 읽을 수 없습니다</h2><p className="muted">기존 신호와 과거 robustness 조회에는 영향을 주지 않습니다.</p></section>;
  }
  const registration = result.registration;
  const warning = result.status === "identity_mismatch" || result.status === "invalid_contract";
  return <section className="panel research-section">
    <div className="section-title simple"><h2>사전 고정 미래 PAPER 평가</h2><span className="badge">{prospectiveStatusLabels[result.status]}</span></div>
    {!registration ? <p className="basis">현재 활성 PAPER session에 연결된 immutable 평가 계약이 없습니다. 이 상태는 미래 검증 실패나 통과를 뜻하지 않습니다.</p> : <>
      <dl className="metric-list prospective-metrics">
        <div><dt>등록 시각</dt><dd>{registration.registered_at}</dd></div>
        <div><dt>관측 기간</dt><dd>{registration.evaluation_start_at}–{registration.evaluation_end_at} ({registration.evaluation_duration_days}일)</dd></div>
        <div><dt>session / source</dt><dd title={`${registration.session_id} / ${registration.source_run_id}`}>{registration.session_id.slice(0, 12)} / {registration.source_run_id.slice(0, 12)}</dd></div>
        <div><dt>계약 SHA</dt><dd title={registration.contract_sha256}>{registration.contract_sha256.slice(0, 16)}</dd></div>
        <div><dt>코드 identity</dt><dd title={registration.code_identity.sha256}>{registration.code_identity.sha256.slice(0, 16)}</dd></div>
        <div><dt>허용 손실 / 정책 방어</dt><dd>{registration.user_loss_tolerance_pct}% / {registration.policy_defense_drawdown_pct}%</dd></div>
      </dl>
      {warning && <p className="notice">등록 계약과 현재 session·source·앱 시작 코드·현재 디스크 코드 중 하나가 일치하지 않습니다. 기간 상태보다 이 불일치를 우선하며 성과 판정을 만들지 않습니다. 사유: {result.reason ?? "확인 불가"}</p>}
      <div className="table-wrap"><table><thead><tr><th>평가 항목</th><th>등록된 정의</th></tr></thead><tbody>
        {registration.evaluation.metrics.map((metric) => <tr key={metric.name}><td>{prospectiveMetricLabels[metric.name] ?? metric.name}</td><td>{metric.definition}</td></tr>)}
        <tr><td>현금 benchmark</td><td>{registration.evaluation.cash_benchmark_return_pct}%</td></tr>
      </tbody></table></div>
      <p className="notice">현재 종가 checkpoint만으로는 평가 시작·종료 시점의 NAV 증거를 충족하지 못합니다. 경계 NAV 검증은 추가 개발이 필요하며, planned는 평가 준비 완료를 뜻하지 않습니다.</p>
      <p className="basis">시작 NAV는 초기 현금 1억원으로 대체하지 않으며 시작·끝 평가 근거가 없으면 향후 계산은 불완전합니다. PAPER 계약이고 자동 승격 대상이 아닙니다.</p>
      <p className="basis">앱 시작 코드 {result.app_start_code_identity_sha256?.slice(0, 16) ?? "확인 불가"} · 현재 디스크 코드 {result.current_disk_code_identity_sha256?.slice(0, 16) ?? "확인 불가"} · source manifest {result.current_source_manifest_sha256?.slice(0, 16) ?? "확인 불가"}</p>
    </>}
    <p className="basis">서버 UTC 등록 시각은 암호학적 타임스탬프가 아니며 과거 코드가 이후 복원되지 않았음을 증명하지 않습니다. 미래 판단별 입력은 PAPER 원장에서 별도로 고정됩니다.</p>
  </section>;
}

function ProspectiveReadinessPanel({ result }: { result: ProspectiveReadiness | null }) {
  if (!result) {
    return <section className="panel pending-panel"><h2>미래 평가 준비 근거를 조회할 수 없습니다</h2><p className="muted">등록 상태와 별도인 읽기 전용 검사를 사용할 수 없습니다. 준비 완료나 평가 결과로 해석하지 않습니다.</p></section>;
  }
  const execution = result.execution_evidence;
  return <section className="panel research-section">
    <div className="section-title simple"><h2>미래 평가 경계·체결 근거 준비 상태</h2><span className="badge">수집기 미구현</span></div>
    <p className="notice">경계 NAV 검증 수집기는 구현되지 않았습니다. 정확한 시각의 checkpoint가 있어도 평가에 사용한 자료의 출처가 없어 미검증 후보이며, NAV 값이나 평가 준비 완료를 표시하지 않습니다.</p>
    <dl className="metric-list prospective-metrics">
      <div><dt>시작 경계</dt><dd>{boundaryStateLabels[result.start_boundary.state]}<br /><small>{result.start_boundary.boundary_at}</small></dd></div>
      <div><dt>종료 경계</dt><dd>{boundaryStateLabels[result.end_boundary.state]}<br /><small>{result.end_boundary.boundary_at}</small></dd></div>
      <div><dt>계약 구간 체결</dt><dd>{executionStateLabels[execution.state]}</dd></div>
      <div><dt>전체 / 검사 체결</dt><dd>{execution.total_fill_count} / {execution.inspected_fill_count}건</dd></div>
      <div><dt>연결 / 누락 / 불일치</dt><dd>{execution.captured_count} / {execution.missing_count} / {execution.mismatch_count}건</dd></div>
      <div><dt>검사 제한</dt><dd>{execution.truncated ? `${execution.uninspected_fill_count}건 미검사` : "잘림 없음"}</dd></div>
    </dl>
    {(result.start_boundary.candidate_checkpoint_at || result.end_boundary.candidate_checkpoint_at) && <p className="basis">후보 checkpoint / 실제 인지 시각: 시작 {result.start_boundary.candidate_checkpoint_at ?? "-"} / {result.start_boundary.candidate_actually_known_at ?? "-"} · 종료 {result.end_boundary.candidate_checkpoint_at ?? "-"} / {result.end_boundary.candidate_actually_known_at ?? "-"}</p>}
    <p className="basis">계약 구간 체결은 fill 수신 시각을 기준으로 포함합니다. sidecar 검사는 원문 SHA와 quote 모델, 종목, 시장·수신 시각의 연결 무결성만 확인합니다. 가격·통화·슬리피지나 재무 계산의 정확성을 증명하지 않으며, 체결 0건도 통과가 아닙니다.</p>
  </section>;
}

function BoundaryCapturePanel({ result }: { result: BoundaryCaptureStatus | null }) {
  if (!result) {
    return <section className="panel pending-panel"><h2>평가 경계 원시 증거를 조회할 수 없습니다</h2><p className="muted">PAPER 원장과 등록 계약은 이 조회와 별도로 유지됩니다.</p></section>;
  }
  return <section className="panel research-section">
    <div className="section-title simple"><h2>평가 경계 원시 증거 수집</h2><span className="badge">{result.running ? "5초 감시 실행 중" : "감시 중지"}</span></div>
    <p className="basis">마지막 실제 확인 {result.last_poll_at ?? "아직 없음"}<br />시작 코드 {result.collector_startup_sha256.slice(0, 16)}<br />현재 코드 {result.collector_current_sha256?.slice(0, 16) ?? "확인 불가"}</p>
    <dl className="metric-list prospective-metrics">{result.boundaries.map((item) => <div key={item.boundary}><dt>{item.boundary === "start" ? "시작" : "종료"} 경계</dt><dd>{captureStateLabels[item.state]}<br /><small>경계 시각 {item.boundary_at}</small>{item.read_started_at && <><br /><small>읽기 시작 {item.read_started_at}</small><br /><small>읽기 완료 {item.read_finished_at ?? "확인 불가"}</small><br /><small>경계 후 수집 지연 {item.capture_lag_seconds ?? "-"}초</small></>}{item.error_code && <><br /><small>오류 {item.error_code}</small></>}{item.issue_count > 0 && <><br /><small>누락·제한 {item.issue_count}종류</small></>}{item.download_available && <><br /><a href={`/research/validation/boundary-download/${item.boundary}`}>원시 기록 내려받기</a></>}</dd></div>)}</dl>
    <p className="notice">이 파일은 경계 이후 한 읽기 전용 검사에서 실제로 관측한 원장 기록입니다. 경계 시점 상태를 소급 재구성한 값, 승인된 NAV 또는 평가 입력 완성을 뜻하지 않습니다. 누락이나 용량 제한이 있어도 최초 파일을 고정합니다.</p>
  </section>;
}

function BoundaryEvidencePanel({ results }: { results: Array<BoundaryEvidence | null> }) {
  return <section className="panel research-section">
    <div className="section-title simple"><h2>원시 경계 자료 부분 일관성</h2><span className="badge">NAV 승인·수익률 계산 없음</span></div>
    <p className="basis">고정된 원시 기록 안의 참조, 시각, 종목과 재현 가능한 체결 산술만 검사합니다. 전체 통과 상태는 만들지 않습니다.</p>
    {results.map((result, index) => !result ? <p className="notice" key={index}>{index === 0 ? "시작" : "종료"} 경계 검사를 조회할 수 없습니다.</p> : <div key={result.boundary}>
      <div className="section-title simple subsection-title"><h3>{result.boundary === "start" ? "시작" : "종료"} 경계</h3><span className="muted">{boundaryEvidenceStateLabels[result.state]}</span></div>
      <dl className="metric-list prospective-metrics">
        <div><dt>원시 기록</dt><dd title={result.artifact_sha256 ?? undefined}>{result.artifact_sha256?.slice(0, 16) ?? "없음"}</dd></div>
        <div><dt>체결 전체 / 상세</dt><dd>{result.fill_total_count} / {result.fill_detail_count}건</dd></div>
        <div><dt>모순 / 확인 불가</dt><dd>{result.fill_failed_count} / {result.fill_unknown_count}건</dd></div>
        <div><dt>경계 뒤 체결</dt><dd>{result.post_boundary_fill_count}건 · 운영 장애 아님</dd></div>
        <div><dt>보유 종목 전체 / 상세</dt><dd>{result.position_total_count} / {result.position_detail_count}건</dd></div>
        <div><dt>평가 입력 완성</dt><dd>아니요</dd></div>
      </dl>
      {result.checks.length > 0 && <div className="table-wrap"><table><thead><tr><th>검사</th><th>상태</th><th>설명</th></tr></thead><tbody>{result.checks.map((check) => <tr key={check.name}><td>{boundaryEvidenceCheckNames[check.name] ?? check.name}</td><td>{evidenceCheckLabels[check.state]}</td><td>{check.detail}</td></tr>)}</tbody></table></div>}
      {result.fills.length > 0 && <details><summary>체결 상세 {result.fill_detail_count}건</summary><div className="table-wrap"><table><thead><tr><th>체결</th><th>저장 / 재현 체결가</th><th>저장 / 재현 거래대금</th><th>검사</th></tr></thead><tbody>{result.fills.map((fill, index) => <tr key={`${fill.fill_id}-${index}`}><td>{fill.symbol} {fill.side} · {fill.received_at}<br /><small>{fill.after_boundary ? "경계 뒤 관측" : "경계 이전·동시 관측"}</small></td><td>{fill.stored_local_price} / {fill.expected_local_price ?? "확인 불가"}</td><td>{fill.stored_notional_krw} / {fill.expected_notional_krw ?? "확인 불가"}</td><td>{fill.checks.map((check) => `${boundaryEvidenceCheckNames[check.name] ?? check.name}: ${evidenceCheckLabels[check.state]}`).join(" · ")}</td></tr>)}</tbody></table></div></details>}
      {result.positions.length > 0 && <details><summary>보유 종목 후보 자료 {result.position_detail_count}건</summary><div className="table-wrap"><table><thead><tr><th>종목</th><th>수량 / 통화</th><th>검사</th></tr></thead><tbody>{result.positions.map((position, index) => <tr key={`${position.symbol}-${index}`}><td>{position.symbol}</td><td>{position.quantity} / {position.currency}</td><td>{position.checks.map((check) => `${boundaryEvidenceCheckNames[check.name] ?? check.name}: ${evidenceCheckLabels[check.state]}`).join(" · ")}</td></tr>)}</tbody></table></div></details>}
    </div>)}
    <p className="notice">최신 시세는 읽기 시점 후보일 뿐 경계 가격이 아닙니다. 체결 환율의 외부 원문, 원장 commit 시각, 기업행동 완결성과 경계 NAV는 증명하지 않습니다.</p>
  </section>;
}

function SignalPanel({ result }: { result: SignalValidation | null }) {
  if (!result) {
    return (
      <section className="panel pending-panel">
        <h2>실시간 신호 증거를 읽을 수 없습니다</h2>
        <p className="muted">
          PAPER 원장과 수집 서비스는 이 조회 실패와 별도로 계속 동작합니다.
        </p>
      </section>
    );
  }
  return (
    <section className="panel research-section">
      <div className="section-title simple">
        <h2>저장된 실시간 신호 증거</h2>
        <span className="muted">거래소 현지일 {result.local_date}</span>
      </div>
      <p className="basis">
        분 단위 저장 표본을 실제 거래소 정규장과 비교했습니다. 미관측 분은
        tick 유실이나 서비스 장애로 단정할 수 없으며 가용성 SLA가 아닙니다.
      </p>
      <dl className="metric-list">
        <div><dt>정규장 지연 표본</dt><dd>{result.latency.sample_count}건</dd></div>
        <div><dt>중앙값 / p95</dt><dd>{result.latency.median_milliseconds ?? "-"} / {result.latency.p95_milliseconds ?? "-"} ms</dd></div>
        <div><dt>최대 지연</dt><dd>{result.latency.maximum_milliseconds ?? "-"} ms</dd></div>
        <div><dt>15초 초과</dt><dd>{result.latency.over_15_seconds_count}건</dd></div>
        <div><dt>2초 초과 미래 시각</dt><dd>{result.latency.future_over_2_seconds_count}건</dd></div>
        <div><dt>저장된 판단 / 체결</dt><dd>{result.decisions.length} / {result.executions.length}건</dd></div>
        <div><dt>체결 경로 증거</dt><dd>{result.operational_evidence === "captured_fills" ? "실제 사용 시세 보존" : "아직 운영 증거 없음"}</dd></div>
      </dl>
      <div className="table-wrap"><table>
        <thead><tr><th>종목</th><th>상태</th><th>완료 분</th><th>관측 분</th><th>미관측 분</th><th>정규장 밖 행</th><th>gap</th></tr></thead>
        <tbody>{result.coverage.map((item) => <tr key={item.symbol}>
          <td>{item.symbol}</td><td>{item.session_state}</td><td>{item.expected_completed_minutes}</td><td>{item.observed_completed_minutes}</td><td>{item.missing_minutes}</td><td>{item.outside_regular_rows}</td>
          <td>{item.gaps.map((gap) => `${gap.start_at.slice(11, 16)}–${gap.end_at.slice(11, 16)} (${gap.minutes})`).join(" · ") || "없음"}</td>
        </tr>)}</tbody>
      </table></div>
      <div className="section-title simple subsection-title"><h3>종목별 정규장 지연</h3><span className="muted">각 저장 행을 그대로 집계</span></div>
      <div className="table-wrap"><table>
        <thead><tr><th>종목</th><th>표본</th><th>중앙 / p95 / 최대 ms</th><th>15초 초과</th><th>2초 초과 미래 시각</th></tr></thead>
        <tbody>{result.symbol_latency.map((item) => <tr key={item.symbol}>
          <td>{item.symbol}</td><td>{item.sample_count}</td><td>{item.median_milliseconds ?? "-"} / {item.p95_milliseconds ?? "-"} / {item.maximum_milliseconds ?? "-"}</td><td>{item.over_15_seconds_count}</td><td>{item.future_over_2_seconds_count}</td>
        </tr>)}</tbody>
      </table></div>
      <div className="section-title simple subsection-title"><h3>지연 경계 초과 표본</h3><span className="muted">전체 {result.latency_anomalies.total_count}건 중 {result.latency_anomalies.items.length}건 표시{result.latency_anomalies.truncated ? ` · 최근 ${result.latency_anomalies.limit}건으로 제한` : ""}</span></div>
      {result.latency_anomalies.items.length === 0 ? <p className="basis">정규장에서 15초를 초과하거나 2초보다 앞선 시각으로 기록된 표본이 없습니다.</p> : <div className="table-wrap"><table>
        <thead><tr><th>종목</th><th>종류</th><th>저장 이유</th><th>시장 시각</th><th>수신 시각</th><th>정확한 차이 ms</th><th>관측 ID</th></tr></thead>
        <tbody>{result.latency_anomalies.items.map((item) => <tr key={item.observation_id}>
          <td>{item.symbol}</td><td>{item.kind === "future" ? "미래 시각" : "15초 초과"}</td><td>{item.reason}</td><td>{item.market_at}</td><td>{item.received_at}</td><td>{item.milliseconds}</td><td title={item.observation_id}>{item.observation_id.slice(0, 12)}</td>
        </tr>)}</tbody>
      </table></div>}
      <p className="basis">상세 표본은 시장 시각 내림차순, 수신 시각 내림차순, 종목·관측 ID 오름차순입니다. 같은 분이라도 저장 이유가 다르면 별도 행입니다. 이 값만으로 과거 공백의 원인이나 현재 feed 상태를 추정하지 않습니다.</p>
      <div className="section-title simple subsection-title"><h3>저장된 판단</h3><span className="muted">recorded → input cutoff → expiry</span></div>
      {result.decisions.length === 0 ? <p className="notice">관측 자료는 있지만 이 날짜에 저장된 판단과 체결은 없어 운영 체결 경로가 아직 검증되지 않았습니다.</p> : <div className="table-wrap"><table>
        <thead><tr><th>판단</th><th>기록 / 만료</th><th>입력 / cutoff</th><th>상태</th><th>지시 / 대기 / 체결</th></tr></thead>
        <tbody>{result.decisions.map((item) => <tr key={item.decision_id}>
          <td>{item.decision_id.slice(0, 10)}</td><td>{item.recorded_at}<br />{item.expires_at ?? "없음"}</td>
          <td title={item.input_version}>{item.input_version.slice(0, 10)}<br />{item.input_cutoff_at ?? "미보존"}</td><td>{item.state}</td>
          <td>{item.intent_count} / {item.pending_intent_count} / {item.fill_count}</td>
        </tr>)}</tbody>
      </table></div>}
      <div className="section-title simple subsection-title"><h3>판단과 체결 시세 연결</h3><span className="muted">decision recorded → exact quote → fill</span></div>
      {result.executions.length === 0 ? <p className="basis">이 날짜에 저장된 체결이 없습니다.</p> : <div className="table-wrap"><table>
        <thead><tr><th>종목 / 판단</th><th>판단 기록 / cutoff</th><th>실제 사용 시세</th><th>체결</th><th>증거</th></tr></thead>
        <tbody>{result.executions.map((item) => <tr key={item.fill_id}>
          <td>{item.symbol}<br /><span title={item.decision_id}>{item.decision_id.slice(0, 10)}</span></td>
          <td>{item.decision_recorded_at}<br />{item.input_cutoff_at ?? "미보존"}</td>
          <td>{item.execution_quote ? `${item.execution_quote.market_at} · ${item.execution_quote.price} ${item.execution_quote.currency}` : "미보존"}</td>
          <td>{item.fill_market_at}<br />{item.side} {item.quantity}주 · {item.fill_local_price}</td>
          <td>{evidenceLabels[item.evidence]}<br /><small title={item.quote_sha256 ?? undefined}>{item.quote_sha256?.slice(0, 12) ?? "hash 없음"}</small></td>
        </tr>)}</tbody>
      </table></div>}
      <p className="basis">현재 연결 상태: {result.current_feed?.state ?? "조회 불가"} · reconnect {result.current_feed?.reconnect_count ?? "-"}회 · durable feed 상태 이벤트 {result.durable_feed.event_count}건(현재 session 범위). 현재 ACK와 protocol counter는 현재 프로세스 연결 epoch 값입니다.</p>
    </section>
  );
}

function RobustnessPanel({ result }: { result: PortfolioRobustness | null }) {
  if (!result) {
    return <section className="panel pending-panel"><h2>포트폴리오 robustness 결과가 없습니다</h2><p className="muted">고정 입력의 독립 실행이 완료되면 표시됩니다.</p></section>;
  }
  const download = (name: string) => `/research/validation/download/${result.run_id}/${name}`;
  return (
    <section className="panel research-section">
      <div className="section-title simple"><h2>포트폴리오 rolling robustness</h2><span className="muted">후향 자료 재사용 · 자동 승격 없음</span></div>
      {!result.calculation_complete && <p className="notice">계산이 완전하지 않습니다. 실패한 fold의 수치는 성과 결과로 해석하지 않습니다.</p>}
      <p className="basis">각 fold는 후보 선택 80 union dates 뒤의 OOS 80 dates를 현금 1억원에서 독립 시작했습니다. fold 수익률은 복리 연결하지 않았습니다.</p>
      <dl className="metric-list">
        <div><dt>완전 fold</dt><dd>{result.fold_count - result.failed_fold_count}/{result.fold_count}</dd></div>
        <div><dt>simulation 평가</dt><dd>{result.simulation_evaluation_count}/147</dd></div>
        <div><dt>미사용 tail</dt><dd>{result.unused_tail_count} union dates</dd></div>
        {result.calculation_complete && result.aggregates.map((item) => <div key={item.role}>
          <dt>{aggregateLabels[item.role] ?? item.role}</dt>
          <dd>중앙 {item.median_return_pct === null ? "-" : `${researchAmount(item.median_return_pct, 6)}%`} · 최악 {item.worst_return_pct === null ? "-" : `${researchAmount(item.worst_return_pct, 6)}%`}<br />균등 초과 {item.benchmark_beat_count}/{item.fold_count} · 비용 2배 drag 중앙 {item.median_cost_drag_percentage_points === null ? "-" : `${researchAmount(item.median_cost_drag_percentage_points, 6)}pp`} · 무거래 {item.zero_trade_fold_count}개</dd>
        </div>)}
      </dl>
      <div className="table-wrap"><table>
        <thead><tr><th>fold</th><th>선택 / OOS 구간</th><th>사전 선택 후보</th><th>선택 / 균등 / 고정 수익률</th><th>선택 / 균등 / 고정 MDD</th><th>선택 거래 / turnover</th></tr></thead>
        <tbody>{result.folds.map((fold) => {
          const selected = fold.oos.find((item) => item.role === "selected_base");
          const equal = fold.oos.find((item) => item.role === "equal_baseline");
          const fixed = fold.oos.find((item) => item.role === "fixed_base");
          const complete = fold.status === "completed" && selected?.complete && equal?.complete && fixed?.complete;
          const reasons = [...(selected?.incomplete_reasons ?? []), ...(equal?.incomplete_reasons ?? []), ...(fixed?.incomplete_reasons ?? [])].join(", ");
          return <tr key={fold.fold}>
            <td>{fold.fold}</td><td>{fold.selection_start}–{fold.selection_end}<br />{fold.oos_start}–{fold.oos_end}</td><td>{fold.selected_candidate?.id ?? fold.failure_reason}</td>
            <td>{complete ? `${researchAmount(selected.metrics.total_return_pct, 6)}% / ${researchAmount(equal.metrics.total_return_pct, 6)}% / ${researchAmount(fixed.metrics.total_return_pct, 6)}%` : `불완전: ${fold.failure_reason ?? reasons}`}</td>
            <td>{complete ? `${researchAmount(selected.metrics.max_drawdown_pct, 6)}% / ${researchAmount(equal.metrics.max_drawdown_pct, 6)}% / ${researchAmount(fixed.metrics.max_drawdown_pct, 6)}%` : "-"}</td>
            <td>{complete ? `${selected.metrics.trade_count} / ${researchAmount(selected.metrics.turnover_pct, 6)}%` : "-"}</td>
          </tr>;
        })}</tbody>
      </table></div>
      <p className="basis">고정 정책은 low_turnover_combined, 종목 20%·전체 60%·레버리지 ETF 합산 20%·낙폭 10% 방어·4주 주기를 유지합니다. signal window 15/25와 volatility window 45/75는 한 번에 한 변수만 바꾼 민감도이며 결과로 재선택하지 않습니다.</p>
      <div className="artifact-links">{[...result.artifacts, "manifest.json"].map((name) => <a className="secondary-button" href={download(name)} key={name}>{name}</a>)}</div>
    </section>
  );
}

export default async function ValidationPage({ searchParams }: PageProps) {
  const query = await searchParams;
  const selectedDate = validLocalDate(query.local_date);
  const [prospectiveResult, readinessResult, boundaryCaptureResult, startEvidenceResult, endEvidenceResult, signalResult, robustnessResult] = await Promise.allSettled([
    getProspectiveRegistrationStatus(),
    getProspectiveReadiness(),
    getBoundaryCaptureStatus(),
    getBoundaryEvidence("start"),
    getBoundaryEvidence("end"),
    getSignalValidation(selectedDate),
    getLatestPortfolioRobustness(),
  ]);
  const displayedDate = selectedDate ?? (signalResult.status === "fulfilled" ? signalResult.value.local_date : utcDate(-1));
  return (
    <main>
      <header className="research-result-header">
        <Link href="/research" className="brand"><span className="mark">J</span> jusik <span className="brand-sub">검증 증거</span></Link>
        <div className="action-row"><Link className="secondary-button" href="/research/forward">전진 관찰</Link><Link className="secondary-button" href="/research/portfolio">포트폴리오</Link><span className="badge">PAPER 연구 · 실제 주문 없음</span></div>
      </header>
      <section className="intro research-intro">
        <div><p className="eyebrow">VALIDATION EVIDENCE</p><h1>실시간 경로와 과거 robustness를 따로 확인</h1><p className="muted">저장된 관측·판단·체결 증거와 고정 과거 입력의 rolling 결과는 서로 다른 검증입니다.</p></div>
        <form method="get" className="action-row"><label>거래소 현지일 <input type="date" name="local_date" defaultValue={displayedDate} min={utcDate(-7)} max={utcDate()} required /></label><button type="submit" className="secondary-button">증거 조회</button></form>
      </section>
      <ProspectivePanel result={prospectiveResult.status === "fulfilled" ? prospectiveResult.value : null} />
      <ProspectiveReadinessPanel result={readinessResult.status === "fulfilled" ? readinessResult.value : null} />
      <BoundaryCapturePanel result={boundaryCaptureResult.status === "fulfilled" ? boundaryCaptureResult.value : null} />
      <BoundaryEvidencePanel results={[
        startEvidenceResult.status === "fulfilled" ? startEvidenceResult.value : null,
        endEvidenceResult.status === "fulfilled" ? endEvidenceResult.value : null,
      ]} />
      <SignalPanel result={signalResult.status === "fulfilled" ? signalResult.value : null} />
      <RobustnessPanel result={robustnessResult.status === "fulfilled" ? robustnessResult.value : null} />
    </main>
  );
}
