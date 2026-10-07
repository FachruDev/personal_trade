"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type Health = { status: string; timestamp: string };
type BotStatus = { mode: string; freqtrade: unknown; detail?: string };
type OperationalState = { environment: string; kill_switch_enabled: boolean; freqtrade_reachable: boolean };
type BotPerformance = { status: string; mode: string; detail?: string; performance?: { profit_closed_coin?: number; profit_closed_percent?: number; profit_all_coin?: number; profit_all_percent?: number; trade_count?: number; closed_trade_count?: number } };
type ShadowFreshness = { status: string; observed_at?: string; age_seconds?: number; stale_after_seconds?: number };
type GlobalContext = ShadowFreshness & { context?: { regime?: string; market_cap_change_24h?: number | null; btc_dominance?: number | null } };
type OrderBookContext = ShadowFreshness & { context?: { pairs?: Record<string, { mid_price?: number | null; imbalance?: number | null; spread_bps?: number | null; bid_levels?: number; ask_levels?: number }> } };
type OrderBookCoverage = { status: string; observations: number; minimum_observations: number; coverage_ratio?: number | null; first_observed_at?: string | null; last_observed_at?: string | null; remaining_observations?: number; estimated_ready_at?: string | null; continuity_gap_seconds?: number };
type OrderBookResearch = { status: string; mode: string; coverage: OrderBookCoverage; pairs: string[]; horizons_minutes: number[]; evaluations: Array<{ pair: string; horizon_minutes: number; summary: Record<string, { samples: number; mean_return_bps: number | null; positive_rate: number | null }> }> };
type NewsHeadlines = { mode: string; headlines: Array<{ title: string; source: string; url: string; published_at?: string | null }> };
type BinanceMarket = { reachable: boolean; pairs: Record<string, string>; observed_at: string; clock_drift_seconds?: number; clock_synchronized?: boolean; detail?: string };
type ReleaseReadiness = { ready: boolean; environment: string; checks: Array<{ key: string; passed: boolean; detail: string }>; paper_run?: { status: string; observations: number; expected_observations: number; coverage_ratio?: number | null; required_days: number; elapsed_days?: number; progress_ratio?: number; remaining_days?: number; estimated_ready_at?: string | null; first_observed_at?: string | null; strategy?: string | null; profile?: string | null; revision?: string | null; source_sha256?: string | null } };
type MacroContext = ShadowFreshness & { detail?: string; last_attempt_at?: string; context?: { series?: Record<string, { value?: number | null; date?: string | null }> } };
type ShadowCollectionStatus = { mode: string; execution_effect: string; sources: Record<string, { enabled: boolean; configuration_valid?: boolean; cadence_seconds: number; status: string; last_success_at?: string | null; last_failure_at?: string | null }> };
type AiShadow = ShadowFreshness & { assessment?: { market_bias: string; confidence: number; risk_level: string; trade_support: boolean; event_summary: string; provider: string; model: string; input_source?: string } };
type ContextFusion = { recommendation: { decision: string; risk_multiplier: number; reasons: string[]; mode: string }; inputs_available: { global_market: boolean; macro: boolean; ai: boolean }; stale_inputs?: { global_market: boolean; macro: boolean; ai: boolean } };
type Decision = { id: number; event_type: string; payload: Record<string, unknown>; created_at: string };
type DecisionSummary = { events_observed: number; event_counts: Record<string, number>; hold_reasons: Array<{ reason: string; count: number }>; latest_by_pair: Record<string, { event_type: string; created_at: string; regime?: string; rsi?: number; adx_4h?: number; failed_conditions?: string[] }> };
type ResearchExperiment = { label: string; strategy: string; status: string; mode: string; pairs: string[]; timeframes: { entry: string; trend: string }; hypothesis: string; entry_summary: string[]; risk_profile: { research: string; promotion: string }; validation: { periods: string[]; required_profit_factor: number; required_positive_expectancy: boolean; required_trades_per_period: number; maximum_drawdown_percent: number; integrity_checks: string[]; gate_description?: string; result?: { passes: boolean; reason: string; development: ResearchPeriod; validation: ResearchPeriod; out_of_sample: ResearchPeriod } }; context_policy: string };
type ResearchPeriod = { trades: number; profit_factor: number; return_percent: number; maximum_drawdown_percent: number };
type ResearchExperiments = { experiments: ResearchExperiment[] };
type DashboardState = {
  health: Health | null;
  bot: BotStatus | null;
  operations: OperationalState | null;
  performance: BotPerformance | null;
  news: NewsHeadlines | null;
  binanceMarket: BinanceMarket | null;
  releaseReadiness: ReleaseReadiness | null;
  globalContext: GlobalContext | null;
  orderBookContext: OrderBookContext | null;
  orderBookCoverage: OrderBookCoverage | null;
  orderBookResearch: OrderBookResearch | null;
  macroContext: MacroContext | null;
  collectionStatus: ShadowCollectionStatus | null;
  aiShadow: AiShadow | null;
  contextFusion: ContextFusion | null;
  research: ResearchExperiments | null;
  decisionSummary: DecisionSummary | null;
  decisions: Decision[];
  error: string | null;
  updatedAt: Date | null;
};

const initialState: DashboardState = { health: null, bot: null, operations: null, performance: null, news: null, binanceMarket: null, releaseReadiness: null, globalContext: null, orderBookContext: null, orderBookCoverage: null, orderBookResearch: null, macroContext: null, collectionStatus: null, aiShadow: null, contextFusion: null, research: null, decisionSummary: null, decisions: [], error: null, updatedAt: null };

function formatDate(value: string) {
  return new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "medium" }).format(new Date(value));
}

function botState(bot: BotStatus | null) {
  if (!bot) return "Memuat";
  if (bot.freqtrade === "unavailable") return "Tidak terhubung";
  return "Berjalan";
}

function humanizeRunStatus(status: string) {
  const labels: Record<string, string> = {
    not_started: "belum dimulai",
    collecting: "mengumpulkan bukti",
    interrupted: "terputus",
    ready_for_release_evidence: "bukti rilis siap",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

function humanizeResearchTerm(term: string) {
  const labels: Record<string, string> = {
    development: "pengembangan",
    validation: "validasi",
    out_of_sample: "uji di luar sampel",
    four_week_continuous_collection: "empat minggu koleksi kontinu",
    "60_minute_forward_return": "return 60 menit",
    "240_minute_forward_return": "return 240 menit",
    lookahead: "anti look-ahead",
    recursive: "uji rekursif",
    fixed_buckets: "bucket tetap",
    fixed_horizons: "horizon tetap",
    shadow_only: "shadow-only",
  };
  return labels[term] ?? term.replaceAll("_", " ");
}
function humanizeResearchStatus(status: string) {
  const labels: Record<string, string> = {
    rejected: "Ditolak",
    collecting_data: "Mengumpulkan data",
    qualified: "Memenuhi syarat",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}
function humanizeReason(reason: string) {
  const labels: Record<string, string> = {
    regime_sideways: "Regime 4H sideways",
    regime_bear: "Regime 4H bearish",
    regime_high_volatility: "Volatilitas 4H terlalu tinggi",
    ema20_not_above_ema50: "EMA20 belum di atas EMA50",
    rsi_outside_range: "RSI di luar area entry",
    macd_not_bullish: "MACD belum bullish",
    macd_not_improving: "MACD belum membaik",
    volume_below_average: "Volume belum di atas rata-rata",
    indicator_data_unavailable: "Data indikator belum lengkap",
  };
  return labels[reason] ?? reason.replaceAll("_", " ");
}

function isCollected(context: ShadowFreshness | null | undefined) {
  return context?.status === "available" || context?.status === "stale";
}

function contextLabel(context: ShadowFreshness | null | undefined) {
  if (context?.status === "available") return "Tersedia";
  if (context?.status === "stale") return "Terlambat";
  return "Belum tersedia";
}

function contextAge(context: ShadowFreshness | null | undefined) {
  if (!context?.age_seconds && context?.age_seconds !== 0) return "—";
  if (context.age_seconds < 60) return `${context.age_seconds} dtk lalu`;
  if (context.age_seconds < 3_600) return `${Math.floor(context.age_seconds / 60)} mnt lalu`;
  return `${(context.age_seconds / 3_600).toFixed(1)} jam lalu`;
}

function collectionStatusLabel(status: string) {
  const labels: Record<string, string> = { collecting: "Aktif", waiting: "Menunggu", unavailable: "Perlu perhatian", configuration_invalid: "Konfigurasi perlu diperbaiki", disabled: "Dimatikan" };
  return labels[status] ?? status.replaceAll("_", " ");
}

function orderBookReadyEstimate(coverage: OrderBookCoverage | null) {
  if (!coverage) return "—";
  if (coverage.status === "ready_for_research") return "Siap dievaluasi";
  if (!coverage.estimated_ready_at) return "Menunggu snapshot pertama";
  return `Perkiraan selesai ${formatDate(coverage.estimated_ready_at)} · sisa ${coverage.remaining_observations ?? "—"} snapshot`;
}
function numberFrom(payload: Record<string, unknown>, key: string) {
  const value = payload[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function auditSummary(decision: Decision) {
  if (decision.event_type === "paper_run_continuity_interrupted") {
    const gapSeconds = numberFrom(decision.payload, "gap_seconds");
    const gapMinutes = gapSeconds === null ? null : Math.ceil(gapSeconds / 60);
    return [gapMinutes === null ? "Kontinuitas paper run terputus; segmen bukti baru akan dimulai." : `Kontinuitas paper run terputus selama ${gapMinutes} menit; segmen bukti baru dimulai.`];
  }
  const payload = decision.payload;
  const pair = typeof payload.pair === "string" ? payload.pair : null;
  const reason = typeof payload.reason === "string" ? humanizeReason(payload.reason) : null;
  const failedConditions = Array.isArray(payload.failed_conditions)
    ? payload.failed_conditions.filter((item): item is string => typeof item === "string").map(humanizeReason)
    : [];
  const parts: string[] = [];

  if (pair) parts.push(pair);
  if (reason) parts.push(reason);
  if (failedConditions.length) parts.push(`Belum lolos: ${failedConditions.join(", ")}`);

  const regime = typeof payload.regime === "string" ? payload.regime : null;
  const rsi = numberFrom(payload, "rsi");
  const adx = numberFrom(payload, "adx_4h");
  if (regime || rsi !== null || adx !== null) {
    parts.push([regime ? `Regime ${regime}` : null, rsi !== null ? `RSI ${rsi.toFixed(1)}` : null, adx !== null ? `ADX 4H ${adx.toFixed(1)}` : null].filter(Boolean).join(" · "));
  }

  const stake = numberFrom(payload, "stake_amount");
  const entry = numberFrom(payload, "entry_rate");
  const stop = numberFrom(payload, "stop_rate");
  if (stake !== null || entry !== null || stop !== null) {
    parts.push([stake !== null ? `Ukuran ${stake.toFixed(2)} USDT` : null, entry !== null ? `Entry ${entry.toFixed(4)}` : null, stop !== null ? `Stop ${stop.toFixed(4)}` : null].filter(Boolean).join(" · "));
  }

  if (!parts.length) {
    parts.push("Event operasional tercatat. Buka detail audit untuk data lengkap.");
  }
  return parts;
}

export default function Home() {
  const [state, setState] = useState<DashboardState>(initialState);
  const [refreshing, setRefreshing] = useState(false);
  const [decisionPair, setDecisionPair] = useState("all");
  const [decisionType, setDecisionType] = useState("all");

  const loadDashboard = useCallback(async () => {
    setRefreshing(true);
    try {
      const [healthResponse, botResponse, operationsResponse, performanceResponse, newsResponse, binanceMarketResponse, releaseReadinessResponse, contextResponse, orderBookResponse, orderBookCoverageResponse, orderBookResearchResponse, macroResponse, collectionStatusResponse, aiShadowResponse, fusionResponse, researchResponse, decisionSummaryResponse, decisionsResponse] = await Promise.all([
        fetch("/api/trading/health", { cache: "no-store" }),
        fetch("/api/trading/v1/bot/status", { cache: "no-store" }),
        fetch("/api/trading/v1/operational-state", { cache: "no-store" }),
        fetch("/api/trading/v1/bot/performance", { cache: "no-store" }),
        fetch("/api/trading/v1/news/headlines", { cache: "no-store" }),
        fetch("/api/trading/v1/market/binance/status", { cache: "no-store" }),
        fetch("/api/trading/v1/release/readiness", { cache: "no-store" }),
        fetch("/api/trading/v1/context/global", { cache: "no-store" }),
        fetch("/api/trading/v1/context/orderbook", { cache: "no-store" }),
        fetch("/api/trading/v1/context/orderbook/coverage", { cache: "no-store" }),
        fetch("/api/trading/v1/research/orderbook/report", { cache: "no-store" }),
        fetch("/api/trading/v1/context/macro", { cache: "no-store" }),
        fetch("/api/trading/v1/context/collection-status", { cache: "no-store" }),
        fetch("/api/trading/v1/ai/shadow/latest", { cache: "no-store" }),
        fetch("/api/trading/v1/context/fusion", { cache: "no-store" }),
        fetch("/api/trading/v1/research/experiments", { cache: "no-store" }),
        fetch("/api/trading/v1/decisions/summary", { cache: "no-store" }),
        fetch("/api/trading/v1/decisions", { cache: "no-store" }),
      ]);
      if (!healthResponse.ok || !botResponse.ok || !operationsResponse.ok || !performanceResponse.ok || !newsResponse.ok || !binanceMarketResponse.ok || !releaseReadinessResponse.ok || !contextResponse.ok || !orderBookResponse.ok || !orderBookCoverageResponse.ok || !orderBookResearchResponse.ok || !macroResponse.ok || !collectionStatusResponse.ok || !aiShadowResponse.ok || !fusionResponse.ok || !researchResponse.ok || !decisionSummaryResponse.ok || !decisionsResponse.ok) {
        throw new Error("Dashboard belum dapat mengambil data dari control API.");
      }
      const [health, bot, operations, performance, news, binanceMarket, releaseReadiness, globalContext, orderBookContext, orderBookCoverage, orderBookResearch, macroContext, collectionStatus, aiShadow, contextFusion, research, decisionSummary, decisions] = (await Promise.all([
        healthResponse.json(),
        botResponse.json(),
        operationsResponse.json(),
        performanceResponse.json(),
        newsResponse.json(),
        binanceMarketResponse.json(),
        releaseReadinessResponse.json(),
        contextResponse.json(),
        orderBookResponse.json(),
        orderBookCoverageResponse.json(),
        orderBookResearchResponse.json(),
        macroResponse.json(),
        collectionStatusResponse.json(),
        aiShadowResponse.json(),
        fusionResponse.json(),
        researchResponse.json(),
        decisionSummaryResponse.json(),
        decisionsResponse.json(),
      ])) as [Health, BotStatus, OperationalState, BotPerformance, NewsHeadlines, BinanceMarket, ReleaseReadiness, GlobalContext, OrderBookContext, OrderBookCoverage, OrderBookResearch, MacroContext, ShadowCollectionStatus, AiShadow, ContextFusion, ResearchExperiments, DecisionSummary, Decision[]];
      setState({ health, bot, operations, performance, news, binanceMarket, releaseReadiness, globalContext, orderBookContext, orderBookCoverage, orderBookResearch, macroContext, collectionStatus, aiShadow, contextFusion, research, decisionSummary, decisions, error: null, updatedAt: new Date() });
    } catch {
      setState((current) => ({
        ...current,
        error: "Control API belum tersedia. Pastikan layanan Docker API sedang berjalan.",
      }));
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void loadDashboard(), 0);
    const interval = window.setInterval(() => void loadDashboard(), 30_000);
    return () => {
      window.clearTimeout(initialLoad);
      window.clearInterval(interval);
    };
  }, [loadDashboard]);

  const connected = state.health?.status === "ok";
  const decisionCount = state.decisions.length;
  const performance = state.performance?.performance;
  const decisionPairs = useMemo(() => Array.from(new Set(state.decisions.map((decision) => typeof decision.payload.pair === "string" ? decision.payload.pair : null).filter((pair): pair is string => pair !== null))).sort(), [state.decisions]);
  const decisionTypes = useMemo(() => Array.from(new Set(state.decisions.map((decision) => decision.event_type))).sort(), [state.decisions]);
  const filteredDecisions = useMemo(() => state.decisions.filter((decision) => {
    const pair = typeof decision.payload.pair === "string" ? decision.payload.pair : null;
    return (decisionPair === "all" || pair === decisionPair) && (decisionType === "all" || decision.event_type === decisionType);
  }), [decisionPair, decisionType, state.decisions]);

  return (
    <main className="dashboard-shell">
      <section className="dashboard-header">
        <div>
          <p className="eyebrow">Trading Bot Control Center</p>
          <h1>Monitor dry-run secara jelas.</h1>
          <p className="subheading">Dashboard ini membaca kondisi bot dan jejak keputusan. Semua order pada fase ini tetap simulasi.</p>
        </div>
        <button className="refresh-button" onClick={() => void loadDashboard()} disabled={refreshing}>
          {refreshing ? "Memperbarui…" : "Perbarui data"}
        </button>
      </section>

      {state.error ? <p className="notice notice-error">{state.error}</p> : null}
      <p className="notice">
        Mode aktif: <strong>{state.operations?.environment ?? state.bot?.mode ?? "memuat"}</strong>. {state.operations?.environment === "live" ? "Periksa checklist rilis dan kill-switch sebelum melanjutkan." : "Order pada profil ini adalah simulasi."}
      </p>

      <section className="status-grid" aria-label="Ringkasan kondisi bot">
        <StatusCard label="Control API" value={connected ? "Terhubung" : "Memuat"} detail="PostgreSQL dan Redis diperiksa oleh health check." active={connected} />
        <StatusCard label="Freqtrade" value={botState(state.bot)} detail="Execution engine Binance Spot." active={state.operations?.freqtrade_reachable === true} />
        <StatusCard label="Binance market" value={state.binanceMarket?.reachable ? "Terhubung" : "Periksa"} detail={state.binanceMarket ? `BTC ${state.binanceMarket.pairs.BTCUSDT ?? "—"} · ETH ${state.binanceMarket.pairs.ETHUSDT ?? "—"} · Jam ${state.binanceMarket.clock_drift_seconds == null ? "—" : `${state.binanceMarket.clock_drift_seconds.toFixed(2)} dtk`}${state.binanceMarket.clock_synchronized === false ? " · perlu sinkronisasi sebelum rilis" : ""}` : "Memeriksa pair publik."} active={state.binanceMarket?.reachable === true && state.binanceMarket?.clock_synchronized !== false} />
        <StatusCard label="Pasangan awal" value="BTC / ETH" detail="BTC/USDT dan ETH/USDT, signal 1H dan regime 4H." />
        <StatusCard label="Kill-switch" value={state.operations?.kill_switch_enabled ? "Aktif" : "Siap"} detail={state.operations?.kill_switch_enabled ? "Entry baru diblokir oleh API." : "Tidak ada blokir entry aktif."} active={!state.operations?.kill_switch_enabled} />
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Release gate</p><h2>Kesiapan go-live</h2></div>
          <span className="event-count">{state.releaseReadiness?.ready ? "Siap" : "Belum siap"}</span>
        </div>
        <p className="subheading">Status ini hanya menjadi siap bila setiap bukti rilis telah terpenuhi. Paper mode dan container sehat saja belum cukup.</p>
        <ul className="check-list">
          {(state.releaseReadiness?.checks ?? []).map((check) => <li key={check.key} className={`release-check ${check.passed ? "passed" : "pending"}`}>{check.detail}</li>)}
        </ul>
        {state.binanceMarket?.clock_synchronized === false ? <p className="notice notice-error">Jam Windows berbeda {state.binanceMarket.clock_drift_seconds?.toFixed(2) ?? "—"} detik dari Binance. Sebelum rilis, buka pengaturan Waktu & bahasa Windows lalu sinkronkan waktu secara otomatis.</p> : null}        {state.releaseReadiness?.paper_run ? <p className="notice">Paper run: {state.releaseReadiness.paper_run.observations} heartbeat · {humanizeRunStatus(state.releaseReadiness.paper_run.status)} · bukti {((state.releaseReadiness.paper_run.progress_ratio ?? 0) * 100).toFixed(1)}% ({(state.releaseReadiness.paper_run.elapsed_days ?? 0).toFixed(1)} / {state.releaseReadiness.paper_run.required_days} hari){state.releaseReadiness.paper_run.coverage_ratio == null ? "" : ` · cadence ${(state.releaseReadiness.paper_run.coverage_ratio * 100).toFixed(1)}%`}{state.releaseReadiness.paper_run.estimated_ready_at ? ` · estimasi ${formatDate(state.releaseReadiness.paper_run.estimated_ready_at)}` : ""} · revisi {state.releaseReadiness.paper_run.revision ?? "belum tercatat"} · source {state.releaseReadiness.paper_run.source_sha256?.slice(0, 12) ?? "belum tercatat"}</p> : null}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Quant research</p><h2>Kandidat strategi</h2></div>
          <span className="event-count">{state.research?.experiments.length ?? 0} eksperimen</span>
        </div>
        <p className="subheading">Eksperimen di bawah ini terisolasi dari bot paper. Statusnya tidak dapat mempromosikan strategi atau mengubah order.</p>
        {(state.research?.experiments ?? []).map((experiment) => (
          <article className="research-card" key={experiment.label}>
            <div className="panel-heading"><div><h3>{experiment.strategy}</h3><p className="research-meta">{experiment.pairs.join(" · ")} · entry {experiment.timeframes.entry} · trend {experiment.timeframes.trend}</p></div><span className="event-count">{humanizeResearchStatus(experiment.status)}</span></div>
            <p>{experiment.hypothesis}</p>
            <ul className="check-list compact-list">{experiment.entry_summary.map((rule) => <li key={rule}>{rule}</li>)}</ul>
            <dl className="detail-list compact-list">
              <div><dt>Gate</dt><dd>{experiment.validation.gate_description ?? `PF ≥ ${experiment.validation.required_profit_factor} · expectancy positif · ≥ ${experiment.validation.required_trades_per_period} trade/periode · DD ≤ ${experiment.validation.maximum_drawdown_percent}%`}</dd></div>
              <div><dt>Validasi</dt><dd>{experiment.validation.periods.map(humanizeResearchTerm).join(" · ")} · {experiment.validation.integrity_checks.map(humanizeResearchTerm).join(" & ")}</dd></div>
              <div><dt>Paper jika lolos</dt><dd>{experiment.risk_profile.promotion}</dd></div>
              <div><dt>Context shadow</dt><dd>{experiment.context_policy}</dd></div>
              {experiment.validation.result ? <div><dt>Hasil</dt><dd>{experiment.validation.result.reason}</dd></div> : null}
            </dl>
            {experiment.validation.result ? <div className="research-results" aria-label={`Hasil ${experiment.strategy}`}>
              {(["development", "validation", "out_of_sample"] as const).map((period) => {
                const result = experiment.validation.result![period];
                return <div key={period}><strong>{humanizeResearchTerm(period)}</strong><span>{result.trades} trade · PF {result.profit_factor.toFixed(2)} · {result.return_percent.toFixed(2)}% · DD {result.maximum_drawdown_percent.toFixed(2)}%</span></div>;
              })}
            </div> : null}
          </article>
        ))}
      </section>

      <section className="content-grid">
        <article className="panel">
          <div className="panel-heading">
            <div><p className="eyebrow">Status operasi</p><h2>Bot saat ini</h2></div>
            <span className={connected ? "dot online" : "dot"} aria-label={connected ? "Terhubung" : "Tidak terhubung"} />
          </div>
          <dl className="detail-list">
            <div><dt>Mode</dt><dd>{state.bot?.mode ?? "—"}</dd></div>
            <div><dt>Execution</dt><dd>{botState(state.bot)}</dd></div>
            <div><dt>Audit keputusan</dt><dd>{decisionCount} event</dd></div>
            <div><dt>Trade tertutup</dt><dd>{performance?.closed_trade_count ?? "—"}</dd></div>
            <div><dt>Profit tertutup</dt><dd>{performance ? `${(performance.profit_closed_coin ?? 0).toFixed(2)} USDT` : "—"}</dd></div>
            <div><dt>Profit seluruh posisi</dt><dd>{performance ? `${(performance.profit_all_coin ?? 0).toFixed(2)} USDT` : "—"}</dd></div>
            <div><dt>Terakhir diperbarui</dt><dd>{state.updatedAt ? formatDate(state.updatedAt.toISOString()) : "—"}</dd></div>
          </dl>
          {state.bot?.detail ? <p className="notice notice-error">{state.bot.detail}</p> : null}
          {state.performance?.detail ? <p className="notice notice-error">Ringkasan performa belum tersedia.</p> : null}
        </article>

        <article className="panel">
          <p className="eyebrow">Batas fase saat ini</p><h2>Yang sedang diuji</h2>
          <ul className="check-list">
            <li>Market regime 4H dan signal quant 1H.</li>
            <li>ATR stop, partial take-profit, dan trailing stop.</li>
            <li>Daily drawdown serta cooldown setelah stop-loss beruntun.</li>
            <li>Belum ada AI, macro, atau news yang memengaruhi transaksi.</li>
          </ul>
        </article>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Research operations</p><h2>Status pengumpul data</h2></div>
          <span className="event-count">Shadow only</span>
        </div>
        <p className="subheading">Status ini memantau koleksi data riset. Tidak satu pun sumber dapat memengaruhi entry, ukuran posisi, stop, atau exit.</p>
        {state.collectionStatus ? (
          <dl className="detail-list">
            {Object.entries(state.collectionStatus.sources).map(([source, status]) => (
              <div key={source}>
                <dt>{source.replaceAll("_", " ")}</dt>
                <dd>{collectionStatusLabel(status.status)} · {status.enabled ? `setiap ${Math.max(Math.round(status.cadence_seconds / 60), 1)} menit` : "scheduler dimatikan"}{status.last_success_at ? ` · sukses ${formatDate(status.last_success_at)}` : ""}{status.last_failure_at ? ` · percobaan gagal ${formatDate(status.last_failure_at)}` : ""}</dd>
              </div>
            ))}
          </dl>
        ) : <div className="empty-state"><p>Memuat status pengumpul data.</p></div>}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Market context</p><h2>Global market shadow</h2></div>
          <span className="event-count">{state.globalContext?.status === "stale" ? "Data terlambat" : state.globalContext?.context?.regime ?? "Belum tersedia"}</span>
        </div>
        {state.globalContext && isCollected(state.globalContext) ? (
          <dl className="detail-list">
            <div><dt>Perubahan market cap 24 jam</dt><dd>{state.globalContext.context?.market_cap_change_24h?.toFixed(2) ?? "—"}%</dd></div>
            <div><dt>Dominasi BTC</dt><dd>{state.globalContext.context?.btc_dominance?.toFixed(2) ?? "—"}%</dd></div>
            <div><dt>Status data</dt><dd>{contextLabel(state.globalContext)} · {contextAge(state.globalContext)}</dd></div>
            <div><dt>Snapshot</dt><dd>{state.globalContext.observed_at ? formatDate(state.globalContext.observed_at) : "—"}</dd></div>
          </dl>
        ) : (
          <div className="empty-state"><p>Belum ada snapshot global market.</p><span>Data ini hanya dicatat dalam shadow mode dan belum dapat memengaruhi transaksi.</span></div>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Market microstructure</p><h2>Order book shadow</h2></div>
          <span className="event-count">{contextLabel(state.orderBookContext)}</span>
        </div>
        <p className="subheading">Imbalance dan spread dari sepuluh level teratas Binance publik. Metrik ini dicatat untuk riset dan tidak memengaruhi transaksi.</p>
        {state.orderBookContext && isCollected(state.orderBookContext) ? (
          <>
          <dl className="detail-list">
            {Object.entries(state.orderBookContext.context?.pairs ?? {}).map(([pair, metrics]) => (
              <div key={pair}><dt>{pair}</dt><dd>Mid: {metrics.mid_price == null ? "—" : metrics.mid_price.toFixed(2)} · Imbalance: {metrics.imbalance == null ? "—" : `${(metrics.imbalance * 100).toFixed(1)}%`} · Spread: {metrics.spread_bps == null ? "—" : `${metrics.spread_bps.toFixed(2)} bps`}</dd></div>
            ))}
            <div><dt>Status data</dt><dd>{contextLabel(state.orderBookContext)} · {contextAge(state.orderBookContext)}</dd></div>
            <div><dt>Snapshot</dt><dd>{state.orderBookContext.observed_at ? formatDate(state.orderBookContext.observed_at) : "—"}</dd></div>
            <div><dt>Kesiapan riset</dt><dd>{state.orderBookCoverage ? `${state.orderBookCoverage.observations} / ${state.orderBookCoverage.minimum_observations} snapshot · ${state.orderBookCoverage.status.replaceAll("_", " ")}${state.orderBookCoverage.coverage_ratio == null ? "" : ` · cadence ${(state.orderBookCoverage.coverage_ratio * 100).toFixed(1)}%`}` : "—"}</dd></div>
            <div><dt>Proyeksi koleksi</dt><dd>{orderBookReadyEstimate(state.orderBookCoverage)}</dd></div>
            <div><dt>Batas outage</dt><dd>{state.orderBookCoverage?.continuity_gap_seconds ? `${Math.floor(state.orderBookCoverage.continuity_gap_seconds / 60)} menit tanpa snapshot akan memulai segmen riset baru.` : "—"}</dd></div>
          </dl>
          {state.orderBookResearch?.status === "evaluated" ? <div className="research-results" aria-label="Hasil riset order book">
            {state.orderBookResearch.evaluations.map((evaluation) => <div key={`${evaluation.pair}-${evaluation.horizon_minutes}`}>
              <strong>{evaluation.pair} · {evaluation.horizon_minutes} menit</strong>
              <span>{Object.entries(evaluation.summary).map(([bucket, result]) => `${bucket.replaceAll("_", " ")}: ${result.samples} sampel · ${result.mean_return_bps == null ? "—" : `${result.mean_return_bps.toFixed(1)} bps`} · ${result.positive_rate == null ? "—" : `${(result.positive_rate * 100).toFixed(0)}% positif`}`).join(" | ")}</span>
            </div>)}
          </div> : <p className="notice">Riset forward-return hanya berjalan otomatis setelah data mencapai {state.orderBookResearch?.coverage.minimum_observations ?? state.orderBookCoverage?.minimum_observations ?? "—"} snapshot kontinu. Pair dan horizon sudah dikunci ke BTC/ETH serta 60/240 menit.</p>}
          </>
        ) : <div className="empty-state"><p>Belum ada snapshot order book.</p><span>Pengambilan data publik akan berjalan otomatis saat API aktif.</span></div>}
      </section>

      <section className="content-grid">
        <article className="panel">
          <div className="panel-heading">
            <div><p className="eyebrow">Macro context</p><h2>Macro shadow</h2></div>
            <span className="event-count">{contextLabel(state.macroContext)}</span>
          </div>
          {state.macroContext && isCollected(state.macroContext) ? (
            <dl className="detail-list">
              {Object.entries(state.macroContext.context?.series ?? {}).map(([name, observation]) => (
                <div key={name}><dt>{name.replaceAll("_", " ")}</dt><dd>{observation.value ?? "—"}{observation.date ? ` · ${observation.date}` : ""}</dd></div>
              ))}
              <div><dt>Status data</dt><dd>{contextLabel(state.macroContext)} · {contextAge(state.macroContext)}</dd></div>
            </dl>
          ) : <div className="empty-state"><p>{state.macroContext?.status === "configuration_invalid" ? "Format key FRED perlu diperbaiki." : state.macroContext?.status === "unavailable" ? "Macro belum dapat diperbarui." : "Belum ada snapshot macro."}</p><span>{state.macroContext?.detail ?? "Macro dicatat sebagai konteks dan belum memengaruhi transaksi."}</span>{state.macroContext?.last_attempt_at ? <span>Percobaan terakhir: {formatDate(state.macroContext.last_attempt_at)}</span> : null}</div>}
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div><p className="eyebrow">AI context</p><h2>AI shadow</h2></div>
            <span className="event-count">{state.aiShadow?.status === "stale" ? "Data terlambat" : state.aiShadow?.assessment?.market_bias ?? "Belum tersedia"}</span>
          </div>
          {state.aiShadow && isCollected(state.aiShadow) && state.aiShadow.assessment ? (
            <dl className="detail-list">
              <div><dt>Confidence</dt><dd>{(state.aiShadow.assessment.confidence * 100).toFixed(0)}%</dd></div>
              <div><dt>Risk level</dt><dd>{state.aiShadow.assessment.risk_level}</dd></div>
              <div><dt>Trade support</dt><dd>{state.aiShadow.assessment.trade_support ? "Ya" : "Tidak"}</dd></div>
              <div><dt>Status data</dt><dd>{contextLabel(state.aiShadow)} · {contextAge(state.aiShadow)}</dd></div>
              <div><dt>Ringkasan</dt><dd>{state.aiShadow.assessment.event_summary}</dd></div>
            </dl>
          ) : <div className="empty-state"><p>Belum ada assessment AI.</p><span>AI tetap tidak dapat menentukan atau mengirim order.</span></div>}
        </article>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Context fusion</p><h2>Rekomendasi risiko shadow</h2></div>
          <span className="event-count">{state.contextFusion?.recommendation.decision ?? "Memuat"}</span>
        </div>
        <p className="subheading">Rekomendasi ini belum terhubung ke posisi atau order.</p>
        {state.contextFusion ? (
          <dl className="detail-list">
            <div><dt>Risk multiplier</dt><dd>{(state.contextFusion.recommendation.risk_multiplier * 100).toFixed(0)}%</dd></div>
            <div><dt>Alasan</dt><dd>{state.contextFusion.recommendation.reasons.join(", ").replaceAll("_", " ")}</dd></div>
            <div><dt>Input tersedia</dt><dd>Global: {state.contextFusion.inputs_available.global_market ? "ya" : "tidak"} · Macro: {state.contextFusion.inputs_available.macro ? "ya" : "tidak"} · AI: {state.contextFusion.inputs_available.ai ? "ya" : "tidak"}</dd></div>
            {state.contextFusion.stale_inputs && Object.values(state.contextFusion.stale_inputs).some(Boolean) ? <div><dt>Data terlambat</dt><dd>{Object.entries(state.contextFusion.stale_inputs).filter(([, stale]) => stale).map(([name]) => name.replaceAll("_", " ")).join(", ")} tidak dipakai dalam rekomendasi.</dd></div> : null}
          </dl>
        ) : null}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div><p className="eyebrow">News context</p><h2>Headline shadow</h2></div>
          <span className="event-count">{state.news?.headlines.length ?? 0} headline</span>
        </div>
        {state.news?.headlines.length ? (
          <ol className="decision-list">
            {state.news.headlines.slice(0, 8).map((headline) => (
              <li key={headline.url}>
                <div><strong>{headline.title}</strong><span>{headline.source}{headline.published_at ? ` · ${formatDate(headline.published_at)}` : ""}</span></div>
              </li>
            ))}
          </ol>
        ) : (
          <div className="empty-state"><p>Belum ada headline tersimpan.</p><span>News tetap dalam shadow mode dan tidak dapat memengaruhi order.</span></div>
        )}
      </section>

      <section className="panel decisions-panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Entry explanation</p><h2>Mengapa bot belum membeli?</h2></div>
          <span className="event-count">{state.decisionSummary?.events_observed ?? 0} event dianalisis</span>
        </div>
        <p className="subheading">Ringkasan ini menganalisis hingga 200 event terbaru. Data shadow tidak menentukan hasil di bawah ini.</p>
        {state.decisionSummary?.hold_reasons.length ? <>
          <div className="reason-grid">
            {state.decisionSummary.hold_reasons.slice(0, 5).map((item) => <div key={item.reason}><strong>{humanizeReason(item.reason)}</strong><span>{item.count} kali</span></div>)}
          </div>
          <dl className="detail-list compact-list">
            {Object.entries(state.decisionSummary.latest_by_pair).map(([pair, item]) => <div key={pair}><dt>{pair}</dt><dd>{item.event_type.replaceAll("_", " ")} · {item.regime ?? "—"} · RSI {item.rsi?.toFixed(1) ?? "—"} · ADX 4H {item.adx_4h?.toFixed(1) ?? "—"}</dd></div>)}
          </dl>
        </> : <div className="empty-state"><p>Belum ada alasan HOLD yang tercatat.</p><span>Bot akan mengisi bagian ini setelah candle berikutnya dievaluasi.</span></div>}
      </section>

      <section className="panel decisions-panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Audit trail</p><h2>Keputusan terbaru</h2></div>
          <span className="event-count">{filteredDecisions.length} dari {decisionCount} event terbaru</span>
        </div>
        <div className="decision-filters" aria-label="Filter audit keputusan">
          <label>Pair<select value={decisionPair} onChange={(event) => setDecisionPair(event.target.value)}><option value="all">Semua pair</option>{decisionPairs.map((pair) => <option key={pair} value={pair}>{pair}</option>)}</select></label>
          <label>Jenis event<select value={decisionType} onChange={(event) => setDecisionType(event.target.value)}><option value="all">Semua event</option>{decisionTypes.map((eventType) => <option key={eventType} value={eventType}>{eventType.replaceAll("_", " ")}</option>)}</select></label>
        </div>
        {decisionCount === 0 ? (
          <div className="empty-state"><p>Belum ada event tersimpan.</p><span>Fase berikutnya menambahkan event dari kandidat signal, risk rejection, order, dan exit.</span></div>
        ) : filteredDecisions.length === 0 ? (
          <div className="empty-state"><p>Tidak ada event yang sesuai filter.</p><span>Ubah pair atau jenis event untuk melihat audit lain.</span></div>
        ) : (
          <ol className="decision-list">
            {filteredDecisions.map((decision) => (
              <li key={decision.id}>
                <div><strong>{decision.event_type.replaceAll("_", " ")}</strong><span>{formatDate(decision.created_at)}</span></div>
                <ul className="audit-summary">{auditSummary(decision).map((item, index) => <li key={`${decision.id}-${index}`}>{item}</li>)}</ul>
                <details className="audit-raw"><summary>Detail audit teknis</summary><code>{JSON.stringify(decision.payload, null, 2)}</code></details>
              </li>
            ))}
          </ol>
        )}
      </section>
    </main>
  );
}

function StatusCard({ label, value, detail, active = false }: { label: string; value: string; detail: string; active?: boolean }) {
  return (
    <article className="status-card">
      <p className="status-label">{label}</p>
      <p className={active ? "status-value success" : "status-value"}>{value}</p>
      <p className="status-meta">{detail}</p>
    </article>
  );
}
