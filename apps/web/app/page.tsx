"use client";

import { useCallback, useEffect, useState } from "react";

type Health = { status: string; timestamp: string };
type BotStatus = { mode: string; freqtrade: unknown; detail?: string };
type OperationalState = { environment: string; kill_switch_enabled: boolean; freqtrade_reachable: boolean };
type BotPerformance = { status: string; mode: string; detail?: string; performance?: { profit_closed_coin?: number; profit_closed_percent?: number; profit_all_coin?: number; profit_all_percent?: number; trade_count?: number; closed_trade_count?: number } };
type GlobalContext = { status: string; observed_at?: string; context?: { regime?: string; market_cap_change_24h?: number | null; btc_dominance?: number | null } };
type OrderBookContext = { status: string; observed_at?: string; context?: { pairs?: Record<string, { mid_price?: number | null; imbalance?: number | null; spread_bps?: number | null; bid_levels?: number; ask_levels?: number }> } };
type OrderBookCoverage = { status: string; observations: number; minimum_observations: number; coverage_ratio?: number | null; first_observed_at?: string | null; last_observed_at?: string | null };
type NewsHeadlines = { mode: string; headlines: Array<{ title: string; source: string; url: string; published_at?: string | null }> };
type BinanceMarket = { reachable: boolean; pairs: Record<string, string>; observed_at: string; detail?: string };
type MacroContext = { status: string; observed_at?: string; context?: { series?: Record<string, { value?: number | null; date?: string | null }> } };
type AiShadow = { status: string; observed_at?: string; assessment?: { market_bias: string; confidence: number; risk_level: string; trade_support: boolean; event_summary: string; provider: string; model: string; input_source?: string } };
type ContextFusion = { recommendation: { decision: string; risk_multiplier: number; reasons: string[]; mode: string }; inputs_available: { global_market: boolean; macro: boolean; ai: boolean } };
type Decision = { id: number; event_type: string; payload: Record<string, unknown>; created_at: string };
type DashboardState = {
  health: Health | null;
  bot: BotStatus | null;
  operations: OperationalState | null;
  performance: BotPerformance | null;
  news: NewsHeadlines | null;
  binanceMarket: BinanceMarket | null;
  globalContext: GlobalContext | null;
  orderBookContext: OrderBookContext | null;
  orderBookCoverage: OrderBookCoverage | null;
  macroContext: MacroContext | null;
  aiShadow: AiShadow | null;
  contextFusion: ContextFusion | null;
  decisions: Decision[];
  error: string | null;
  updatedAt: Date | null;
};

const initialState: DashboardState = { health: null, bot: null, operations: null, performance: null, news: null, binanceMarket: null, globalContext: null, orderBookContext: null, orderBookCoverage: null, macroContext: null, aiShadow: null, contextFusion: null, decisions: [], error: null, updatedAt: null };

function formatDate(value: string) {
  return new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "medium" }).format(new Date(value));
}

function botState(bot: BotStatus | null) {
  if (!bot) return "Memuat";
  if (bot.freqtrade === "unavailable") return "Tidak terhubung";
  return "Berjalan";
}

export default function Home() {
  const [state, setState] = useState<DashboardState>(initialState);
  const [refreshing, setRefreshing] = useState(false);

  const loadDashboard = useCallback(async () => {
    setRefreshing(true);
    try {
      const [healthResponse, botResponse, operationsResponse, performanceResponse, newsResponse, binanceMarketResponse, contextResponse, orderBookResponse, orderBookCoverageResponse, macroResponse, aiShadowResponse, fusionResponse, decisionsResponse] = await Promise.all([
        fetch("/api/trading/health", { cache: "no-store" }),
        fetch("/api/trading/v1/bot/status", { cache: "no-store" }),
        fetch("/api/trading/v1/operational-state", { cache: "no-store" }),
        fetch("/api/trading/v1/bot/performance", { cache: "no-store" }),
        fetch("/api/trading/v1/news/headlines", { cache: "no-store" }),
        fetch("/api/trading/v1/market/binance/status", { cache: "no-store" }),
        fetch("/api/trading/v1/context/global", { cache: "no-store" }),
        fetch("/api/trading/v1/context/orderbook", { cache: "no-store" }),
        fetch("/api/trading/v1/context/orderbook/coverage", { cache: "no-store" }),
        fetch("/api/trading/v1/context/macro", { cache: "no-store" }),
        fetch("/api/trading/v1/ai/shadow/latest", { cache: "no-store" }),
        fetch("/api/trading/v1/context/fusion", { cache: "no-store" }),
        fetch("/api/trading/v1/decisions", { cache: "no-store" }),
      ]);
      if (!healthResponse.ok || !botResponse.ok || !operationsResponse.ok || !performanceResponse.ok || !newsResponse.ok || !binanceMarketResponse.ok || !contextResponse.ok || !orderBookResponse.ok || !orderBookCoverageResponse.ok || !macroResponse.ok || !aiShadowResponse.ok || !fusionResponse.ok || !decisionsResponse.ok) {
        throw new Error("Dashboard belum dapat mengambil data dari control API.");
      }
      const [health, bot, operations, performance, news, binanceMarket, globalContext, orderBookContext, orderBookCoverage, macroContext, aiShadow, contextFusion, decisions] = (await Promise.all([
        healthResponse.json(),
        botResponse.json(),
        operationsResponse.json(),
        performanceResponse.json(),
        newsResponse.json(),
        binanceMarketResponse.json(),
        contextResponse.json(),
        orderBookResponse.json(),
        orderBookCoverageResponse.json(),
        macroResponse.json(),
        aiShadowResponse.json(),
        fusionResponse.json(),
        decisionsResponse.json(),
      ])) as [Health, BotStatus, OperationalState, BotPerformance, NewsHeadlines, BinanceMarket, GlobalContext, OrderBookContext, OrderBookCoverage, MacroContext, AiShadow, ContextFusion, Decision[]];
      setState({ health, bot, operations, performance, news, binanceMarket, globalContext, orderBookContext, orderBookCoverage, macroContext, aiShadow, contextFusion, decisions, error: null, updatedAt: new Date() });
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
        <StatusCard label="Binance market" value={state.binanceMarket?.reachable ? "Terhubung" : "Periksa"} detail={state.binanceMarket ? `BTC ${state.binanceMarket.pairs.BTCUSDT ?? "—"} · ETH ${state.binanceMarket.pairs.ETHUSDT ?? "—"}` : "Memeriksa pair publik."} active={state.binanceMarket?.reachable === true} />
        <StatusCard label="Pasangan awal" value="BTC / ETH" detail="BTC/USDT dan ETH/USDT, signal 1H dan regime 4H." />
        <StatusCard label="Kill-switch" value={state.operations?.kill_switch_enabled ? "Aktif" : "Siap"} detail={state.operations?.kill_switch_enabled ? "Entry baru diblokir oleh API." : "Tidak ada blokir entry aktif."} active={!state.operations?.kill_switch_enabled} />
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
          <div><p className="eyebrow">Market context</p><h2>Global market shadow</h2></div>
          <span className="event-count">{state.globalContext?.context?.regime ?? "Belum tersedia"}</span>
        </div>
        {state.globalContext?.status === "available" ? (
          <dl className="detail-list">
            <div><dt>Perubahan market cap 24 jam</dt><dd>{state.globalContext.context?.market_cap_change_24h?.toFixed(2) ?? "—"}%</dd></div>
            <div><dt>Dominasi BTC</dt><dd>{state.globalContext.context?.btc_dominance?.toFixed(2) ?? "—"}%</dd></div>
            <div><dt>Snapshot</dt><dd>{state.globalContext.observed_at ? formatDate(state.globalContext.observed_at) : "—"}</dd></div>
          </dl>
        ) : (
          <div className="empty-state"><p>Belum ada snapshot global market.</p><span>Data ini hanya dicatat dalam shadow mode dan belum dapat memengaruhi transaksi.</span></div>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Market microstructure</p><h2>Order book shadow</h2></div>
          <span className="event-count">{state.orderBookContext?.status === "available" ? "Tersedia" : "Belum tersedia"}</span>
        </div>
        <p className="subheading">Imbalance dan spread dari sepuluh level teratas Binance publik. Metrik ini dicatat untuk riset dan tidak memengaruhi transaksi.</p>
        {state.orderBookContext?.status === "available" ? (
          <dl className="detail-list">
            {Object.entries(state.orderBookContext.context?.pairs ?? {}).map(([pair, metrics]) => (
              <div key={pair}><dt>{pair}</dt><dd>Mid: {metrics.mid_price == null ? "—" : metrics.mid_price.toFixed(2)} · Imbalance: {metrics.imbalance == null ? "—" : `${(metrics.imbalance * 100).toFixed(1)}%`} · Spread: {metrics.spread_bps == null ? "—" : `${metrics.spread_bps.toFixed(2)} bps`}</dd></div>
            ))}
            <div><dt>Snapshot</dt><dd>{state.orderBookContext.observed_at ? formatDate(state.orderBookContext.observed_at) : "—"}</dd></div>
            <div><dt>Kesiapan riset</dt><dd>{state.orderBookCoverage ? `${state.orderBookCoverage.observations} / ${state.orderBookCoverage.minimum_observations} snapshot · ${state.orderBookCoverage.status.replaceAll("_", " ")}${state.orderBookCoverage.coverage_ratio == null ? "" : ` · ${(state.orderBookCoverage.coverage_ratio * 100).toFixed(1)}% lengkap`}` : "—"}</dd></div>
          </dl>
        ) : <div className="empty-state"><p>Belum ada snapshot order book.</p><span>Pengambilan data publik akan berjalan otomatis saat API aktif.</span></div>}
      </section>

      <section className="content-grid">
        <article className="panel">
          <div className="panel-heading">
            <div><p className="eyebrow">Macro context</p><h2>Macro shadow</h2></div>
            <span className="event-count">{state.macroContext?.status === "available" ? "Tersedia" : "Belum tersedia"}</span>
          </div>
          {state.macroContext?.status === "available" ? (
            <dl className="detail-list">
              {Object.entries(state.macroContext.context?.series ?? {}).map(([name, observation]) => (
                <div key={name}><dt>{name.replaceAll("_", " ")}</dt><dd>{observation.value ?? "—"}{observation.date ? ` · ${observation.date}` : ""}</dd></div>
              ))}
            </dl>
          ) : <div className="empty-state"><p>Belum ada snapshot macro.</p><span>Macro dicatat sebagai konteks dan belum memengaruhi transaksi.</span></div>}
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div><p className="eyebrow">AI context</p><h2>AI shadow</h2></div>
            <span className="event-count">{state.aiShadow?.assessment?.market_bias ?? "Belum tersedia"}</span>
          </div>
          {state.aiShadow?.status === "available" && state.aiShadow.assessment ? (
            <dl className="detail-list">
              <div><dt>Confidence</dt><dd>{(state.aiShadow.assessment.confidence * 100).toFixed(0)}%</dd></div>
              <div><dt>Risk level</dt><dd>{state.aiShadow.assessment.risk_level}</dd></div>
              <div><dt>Trade support</dt><dd>{state.aiShadow.assessment.trade_support ? "Ya" : "Tidak"}</dd></div>
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
          <div><p className="eyebrow">Audit trail</p><h2>Keputusan terbaru</h2></div>
          <span className="event-count">{decisionCount} event</span>
        </div>
        {decisionCount === 0 ? (
          <div className="empty-state"><p>Belum ada event tersimpan.</p><span>Fase berikutnya menambahkan event dari kandidat signal, risk rejection, order, dan exit.</span></div>
        ) : (
          <ol className="decision-list">
            {state.decisions.map((decision) => (
              <li key={decision.id}>
                <div><strong>{decision.event_type.replaceAll("_", " ")}</strong><span>{formatDate(decision.created_at)}</span></div>
                <code>{JSON.stringify(decision.payload)}</code>
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
