"use client";

import { useCallback, useEffect, useState } from "react";

type Candle = { opened_at: number; close: number };
type Decision = {
  id: number;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
};
type PaperRun = {
  status?: string;
  strategy?: string | null;
  revision?: string | null;
  first_observed_at?: string | null;
  last_observed_at?: string | null;
  estimated_ready_at?: string | null;
  observations?: number;
  expected_observations?: number;
  coverage_ratio?: number | null;
  progress_ratio?: number;
  elapsed_days?: number;
  remaining_days?: number;
  required_days: number;
};
type Data = {
  health: { status: string } | null;
  operations: {
    kill_switch_enabled: boolean;
    freqtrade_reachable: boolean;
  } | null;
  performance: {
    performance?: {
      profit_all_coin?: number;
      profit_all_percent?: number;
      trade_count?: number;
      closed_trade_count?: number;
    };
  } | null;
  candles: { observed_at: string; candles: Candle[] } | null;
  market: { pairs: Record<string, string> } | null;
  summary: {
    events_observed: number;
    hold_reasons: Array<{ reason: string; count: number }>;
    latest_by_pair: Record<
      string,
      {
        event_type: string;
        regime?: string;
        rsi?: number;
        trend_score?: number | null;
        vol_scale?: number | null;
        exposure?: number | null;
      }
    >;
    // Newest daily-trend target per pair, independent of how many other events arrived since.
    latest_trend_by_pair?: Record<
      string,
      {
        created_at?: string;
        trend_score?: number | null;
        vol_scale?: number | null;
        exposure?: number | null;
      }
    >;
  } | null;
  readiness: {
    ready: boolean;
    paper_run?: PaperRun;
  } | null;
  decisions: Decision[];
  error: string | null;
};
const initial: Data = {
  health: null,
  operations: null,
  performance: null,
  candles: null,
  market: null,
  summary: null,
  readiness: null,
  decisions: [],
  error: null,
};
// Daily candles match the daily trend strategy; the chart is context only.
const chart = { interval: "1d", limit: 90, span: "90 hari", caption: "candle harian" };
// Operator tools stay local: Freqtrade serves its own UI and API on 127.0.0.1:8080.
const freqtradeUiUrl = "http://localhost:8080";
const eventLabels: Record<string, string> = {
  hold: "Menunggu signal",
  quant_candidate: "Signal terdeteksi",
  trend_target: "Target eksposur diperbarui",
  trend_rebalance_requested: "Penyesuaian ukuran posisi",
  risk_approved: "Risiko disetujui",
  risk_rejected: "Risiko ditolak",
  entry_created: "Order masuk",
  entry_filled: "Order terisi",
  exit_filled: "Posisi ditutup",
};
const reasonLabels: Record<string, string> = {
  regime_sideways: "Pasar sideways",
  regime_bear: "Regime bearish",
  volume_below_average: "Volume rendah",
  macd_not_bullish: "MACD belum bullish",
  no_trend_exposure: "Tren belum mendukung",
  below_minimum_stake: "Di bawah ukuran minimum order",
  kill_switch_enabled: "Kill-switch aktif",
  kill_switch_state_unavailable: "Status kill-switch tidak tersedia",
};
const paperStatusLabels: Record<string, string> = {
  ready_for_release_evidence: "Bukti lengkap",
  collecting: "Mengumpulkan bukti",
  interrupted: "Terputus",
  not_started: "Belum mulai",
};

const money = (n?: number) =>
  n === undefined
    ? "—"
    : new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(n);
const when = (value: string) =>
  new Intl.DateTimeFormat("id-ID", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));

export default function Home() {
  const [data, setData] = useState<Data>(initial);
  const [pair, setPair] = useState("BTCUSDT");
  const [section, setSection] = useState<"dashboard" | "activity" | "research">(
    "dashboard",
  );
  const [refreshing, setRefreshing] = useState(false);
  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const paths = [
        "/health",
        "/v1/operational-state",
        "/v1/bot/performance",
        `/v1/market/binance/candles?pair=${pair}&interval=${chart.interval}&limit=${chart.limit}`,
        "/v1/market/binance/status",
        "/v1/decisions?limit=12",
        "/v1/decisions/summary",
        "/v1/release/readiness",
      ];
      const result = await Promise.all(
        paths.map((path) =>
          fetch(`/api/trading${path}`, { cache: "no-store" }),
        ),
      );
      if (result.some((response) => !response.ok))
        throw new Error("API tidak tersedia");
      const [
        health,
        operations,
        performance,
        candles,
        market,
        decisions,
        summary,
        readiness,
      ] = await Promise.all(result.map((response) => response.json()));
      setData({
        health,
        operations,
        performance,
        candles,
        market,
        decisions,
        summary,
        readiness,
        error: null,
      });
    } catch {
      setData((previous) => ({
        ...previous,
        error:
          "Control API belum aktif. Jalankan Docker agar data dashboard tersedia.",
      }));
    } finally {
      setRefreshing(false);
    }
  }, [pair]);
  useEffect(() => {
    const initialLoad = window.setTimeout(() => void refresh(), 0);
    const interval = setInterval(() => void refresh(), 30_000);
    return () => {
      window.clearTimeout(initialLoad);
      clearInterval(interval);
    };
  }, [refresh]);
  const progress =
    Math.min(Math.max(data.readiness?.paper_run?.progress_ratio ?? 0, 0), 1) *
    100;
  const nav = (key: typeof section, label: string, icon: string) => (
    <button
      onClick={() => setSection(key)}
      className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-medium transition ${section === key ? "bg-indigo-500 text-white shadow-lg shadow-indigo-950/20" : "text-slate-400 hover:bg-slate-800 hover:text-white"}`}
    >
      <Icon name={icon} />
      {label}
      {key === "activity" && (
        <span className="ml-auto rounded-full bg-white/10 px-2 py-0.5 text-[10px]">
          {data.decisions.length}
        </span>
      )}
    </button>
  );
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 flex-col bg-slate-950 px-4 py-7 lg:flex">
        <div className="flex items-center gap-3 px-3 text-lg font-bold tracking-tight text-white">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-indigo-500 text-sm">
            T
          </span>
          Tradeboard
        </div>
        <p className="mt-12 px-3 text-[10px] font-bold tracking-[.16em] text-slate-600">
          PERSONAL WORKSPACE
        </p>
        <nav className="mt-3 space-y-1">
          {nav("dashboard", "Dashboard", "grid")}
          {nav("activity", "Aktivitas", "pulse")}
          {nav("research", "Riset", "flask")}
        </nav>
        <div className="mt-auto rounded-xl border border-slate-800 bg-slate-900 p-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            Paper trading
          </div>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            Mode simulasi aktif.
            <br />
            Tidak ada order riil.
          </p>
          <a
            href={freqtradeUiUrl}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-block text-xs font-semibold text-indigo-300 hover:text-white"
          >
            Detail trade: Freqtrade UI ↗
          </a>
        </div>
      </aside>
      <main className="pb-24 lg:ml-64 lg:pb-10">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-5 lg:px-10">
          <div>
            <p className="text-[10px] font-bold tracking-[.16em] text-slate-400">
              PERSONAL TRADING DESK
            </p>
            <h1 className="mt-1 text-xl font-bold tracking-tight lg:text-2xl">
              {section === "dashboard"
                ? "Dashboard"
                : section === "activity"
                  ? "Aktivitas bot"
                  : "Riset & kesiapan"}
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`hidden items-center gap-2 text-xs font-medium sm:flex ${data.health?.status === "ok" ? "text-emerald-600" : "text-slate-400"}`}
            >
              <i
                className={`h-2 w-2 rounded-full ${data.health?.status === "ok" ? "bg-emerald-500" : "bg-slate-300"}`}
              />
              {data.health?.status === "ok" ? "Terhubung" : "Memuat"}
            </span>
            <button
              onClick={() => void refresh()}
              disabled={refreshing}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 transition hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-50"
            >
              <Icon name="refresh" />
              {refreshing ? "Memuat" : "Perbarui"}
            </button>
            <span className="grid h-8 w-8 place-items-center rounded-full bg-amber-400 text-xs font-bold text-white">
              F
            </span>
          </div>
        </header>
        <div className="mx-auto max-w-7xl px-5 py-7 lg:px-10">
          {data.readiness?.paper_run?.status === "interrupted" && (
            <div
              role="alert"
              className="mb-5 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700"
            >
              <Icon name="info" />
              Bukti paper run terputus: heartbeat bot berhenti lebih dari batas
              kontinuitas. Periksa apakah Docker dan layanan bot berjalan.
            </div>
          )}
          {data.error && (
            <div className="mb-5 flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-700">
              <Icon name="info" />
              {data.error}
            </div>
          )}
          {section === "dashboard" && (
            <Dashboard
              data={data}
              pair={pair}
              setPair={setPair}
              progress={progress}
            />
          )}
          {section === "activity" && <Activity decisions={data.decisions} />}
          {section === "research" && (
            <Research data={data} progress={progress} />
          )}
        </div>
      </main>
      <nav className="fixed inset-x-0 bottom-0 z-30 flex justify-around border-t border-slate-200 bg-white px-3 py-2 lg:hidden">
        {(
          [
            ["dashboard", "Dashboard", "grid"],
            ["activity", "Aktivitas", "pulse"],
            ["research", "Riset", "flask"],
          ] as const
        ).map(([key, label, icon]) => (
          <button
            key={key}
            onClick={() => setSection(key)}
            className={`flex min-w-20 flex-col items-center gap-1 rounded-lg px-3 py-1.5 text-[10px] font-semibold ${section === key ? "text-indigo-600" : "text-slate-400"}`}
          >
            <Icon name={icon} />
            {label}
          </button>
        ))}
      </nav>
    </div>
  );
}

function Dashboard({
  data,
  pair,
  setPair,
  progress,
}: {
  data: Data;
  pair: string;
  setPair: (pair: string) => void;
  progress: number;
}) {
  const p = data.performance?.performance;
  const price = data.candles?.candles.at(-1)?.close;
  const change = percent(data.candles?.candles);
  return (
    <>
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Paper P&L"
          value={`${(p?.profit_all_coin ?? 0) >= 0 ? "+" : ""}${money(p?.profit_all_coin)} USDT`}
          sub={`${p?.profit_all_percent?.toFixed(2) ?? "—"}% keseluruhan`}
          icon="wallet"
          good={(p?.profit_all_coin ?? 0) >= 0}
        />
        <Stat
          label="Trade selesai"
          value={String(p?.closed_trade_count ?? "—")}
          sub={`${p?.trade_count ?? 0} posisi tercatat`}
          icon="chart"
        />
        <Stat
          label="Status bot"
          value={data.operations?.freqtrade_reachable ? "Berjalan" : "Offline"}
          sub={
            data.operations?.kill_switch_enabled
              ? "Entry diblokir"
              : "Kill-switch siap"
          }
          icon="bot"
          good={data.operations?.freqtrade_reachable}
        />
        <Stat
          label="Paper run"
          value={`${progress.toFixed(0)}%`}
          sub={`${data.readiness?.paper_run?.elapsed_days?.toFixed(1) ?? 0} / ${data.readiness?.paper_run?.required_days ?? 56} hari`}
          icon="shield"
        />
      </section>
      <section className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.65fr)_360px]">
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[10px] font-bold tracking-[.14em] text-slate-400">
                MARKET OVERVIEW
              </p>
              <h2 className="mt-1 text-lg font-bold">
                {pair.replace("USDT", "/USDT")}
              </h2>
            </div>
            <div className="flex rounded-lg bg-slate-100 p-1">
              {["BTCUSDT", "ETHUSDT"].map((item) => (
                <button
                  key={item}
                  onClick={() => setPair(item)}
                  className={`rounded-md px-3 py-1.5 text-xs font-semibold ${pair === item ? "bg-white text-indigo-600 shadow-sm" : "text-slate-400"}`}
                >
                  {item.slice(0, 3)}
                </button>
              ))}
            </div>
          </div>
          <div className="mt-7 flex items-baseline gap-3">
            <strong className="text-3xl tracking-tight">${money(price)}</strong>
            <span
              className={`text-xs font-bold ${change >= 0 ? "text-emerald-600" : "text-rose-500"}`}
            >
              {change >= 0 ? "+" : ""}
              {change.toFixed(2)}%{" "}
              <small className="font-normal text-slate-400">{chart.span}</small>
            </span>
          </div>
          <Chart candles={data.candles?.candles ?? []} />
          <div className="mt-2 flex justify-between text-[10px] text-slate-400">
            <span>{chart.span}</span>
            <span>Data publik Binance · {chart.caption}</span>
            <span>
              {data.candles
                ? `Update ${when(data.candles.observed_at)}`
                : "Menunggu data"}
            </span>
          </div>
        </article>
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-[10px] font-bold tracking-[.14em] text-slate-400">
            ACCOUNT STATUS
          </p>
          <h2 className="mt-1 text-lg font-bold">Paper account</h2>
          <div className="mt-6 flex items-center justify-center gap-5">
            <div
              className="relative grid h-28 w-28 place-items-center rounded-full"
              style={{
                background: `conic-gradient(#4f46e5 ${progress * 3.6}deg, #eef2ff 0deg)`,
              }}
            >
              <div className="grid h-[86px] w-[86px] place-items-center rounded-full bg-white">
                <strong className="text-xl">{progress.toFixed(0)}%</strong>
              </div>
            </div>
            <div className="text-xs text-slate-500">
              <strong className="block text-sm text-slate-800">
                Bukti terkumpul
              </strong>
              <span>
                Target {data.readiness?.paper_run?.required_days ?? 56} hari
              </span>
            </div>
          </div>
          <div className="mt-7 space-y-3 border-t border-slate-100 pt-4 text-xs">
            <Line
              label="Paper run"
              value={`${progress.toFixed(0)}%`}
              color="bg-indigo-500"
            />
            <Line
              label="Strategi aktif"
              value={data.readiness?.paper_run?.strategy ?? "—"}
              color="bg-sky-500"
            />
            <Line
              label="Status bukti"
              value={
                paperStatusLabels[data.readiness?.paper_run?.status ?? ""] ??
                "—"
              }
              color={
                data.readiness?.paper_run?.status === "interrupted"
                  ? "bg-rose-500"
                  : "bg-violet-400"
              }
            />
            <Line
              label="Heartbeat terakhir"
              value={agoLabel(minutesSince(data.readiness?.paper_run?.last_observed_at))}
              color={
                (minutesSince(data.readiness?.paper_run?.last_observed_at) ?? 0) >
                CONTINUITY_GAP_MINUTES
                  ? "bg-rose-500"
                  : "bg-emerald-500"
              }
            />
            <Line
              label="Bot connection"
              value={data.operations?.freqtrade_reachable ? "Aktif" : "Offline"}
              color="bg-emerald-500"
            />
            <Line
              label="Kesiapan live"
              value={data.readiness?.ready ? "Siap" : "Belum siap"}
              color="bg-amber-400"
            />
          </div>
        </article>
      </section>
      <section className="mt-5 grid gap-5 lg:grid-cols-2">
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <Header
            kicker="MARKET WATCH"
            title="Watchlist"
            right="2 pair dipantau"
          />
          <div className="mt-3 divide-y divide-slate-100">
            {["BTCUSDT", "ETHUSDT"].map((symbol) => (
              <div className="flex items-center gap-3 py-3" key={symbol}>
                <span
                  className={`grid h-9 w-9 place-items-center rounded-full text-lg text-white ${symbol.startsWith("BTC") ? "bg-amber-400" : "bg-slate-500"}`}
                >
                  {symbol.startsWith("BTC") ? "₿" : "Ξ"}
                </span>
                <div className="flex-1">
                  <strong className="block text-sm">
                    {symbol.replace("USDT", "/USDT")}
                  </strong>
                  <span className="text-[11px] text-slate-400">
                    Binance Spot
                  </span>
                </div>
                <div className="text-right">
                  <span
                    className={`block text-xs font-semibold ${data.market?.pairs[symbol] === "TRADING" ? "text-emerald-600" : "text-slate-400"}`}
                  >
                    {data.market?.pairs[symbol] === "TRADING"
                      ? "Aktif"
                      : (data.market?.pairs[symbol] ?? "Memeriksa")}
                  </span>
                  {typeof data.summary?.latest_trend_by_pair?.[
                    symbol.replace("USDT", "/USDT")
                  ]?.exposure === "number" && (
                    <span className="text-[11px] text-slate-400">
                      Eksposur{" "}
                      {pct(
                        data.summary.latest_trend_by_pair[
                          symbol.replace("USDT", "/USDT")
                        ].exposure as number,
                      )}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </article>
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <Header
            kicker="LATEST DECISION"
            title="Signal terakhir"
            right={`${data.summary?.events_observed ?? 0} event`}
          />
          <Signal summary={data.summary} />
        </article>
      </section>
      <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <Header
          kicker="RECENT ACTIVITY"
          title="Aktivitas terbaru"
          right="Audit trail"
        />
        <ActivityRows decisions={data.decisions.slice(0, 5)} />
      </section>
    </>
  );
}
function Activity({ decisions }: { decisions: Decision[] }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <Header
        kicker="AUDIT TRAIL"
        title="Semua aktivitas terbaru"
        right={`${decisions.length} event`}
      />
      <ActivityRows decisions={decisions} expanded />
    </section>
  );
}
function Research({ data, progress }: { data: Data; progress: number }) {
  return (
    <section className="grid gap-5 lg:grid-cols-[1.3fr_.7fr]">
      <article className="rounded-2xl bg-gradient-to-br from-indigo-600 to-indigo-900 p-7 text-white shadow-lg">
        <p className="text-[10px] font-bold tracking-[.14em] text-indigo-200">
          RELEASE READINESS
        </p>
        <h2 className="mt-2 max-w-md text-2xl font-bold tracking-tight">
          Strategi belum siap untuk live trading.
        </h2>
        <p className="mt-3 max-w-lg text-sm leading-6 text-indigo-100">
          Paper trading dan riset tetap dipisahkan dari eksekusi order riil.
        </p>
        <div className="mt-7 h-2 overflow-hidden rounded-full bg-white/20">
          <span
            className="block h-full rounded-full bg-white"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="mt-2 text-xs font-semibold">
          {progress.toFixed(1)}% bukti paper run terkumpul
        </p>
      </article>
      <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <Header kicker="CURRENT CHECKS" title="Yang harus dipenuhi" />
        <ul className="mt-5 space-y-4 text-sm text-slate-500">
          <Check done={data.operations?.freqtrade_reachable ?? false}>
            Koneksi engine paper trading
          </Check>
          <Check done={progress >= 100}>Kontinuitas paper run</Check>
          <Check done={data.readiness?.ready ?? false}>
            Seluruh gate rilis disetujui
          </Check>
        </ul>
      </article>
      <Continuity run={data.readiness?.paper_run} className="lg:col-span-2" />
    </section>
  );
}
function Continuity({
  run,
  className = "",
}: {
  run?: PaperRun;
  className?: string;
}) {
  const minutes = minutesSince(run?.last_observed_at);
  const stale = minutes !== undefined && minutes > CONTINUITY_GAP_MINUTES;
  const coverage = run?.coverage_ratio;
  const rows: Array<{ label: string; value: string; bad?: boolean }> = [
    { label: "Segmen dimulai", value: utcDateTime(run?.first_observed_at) },
    { label: "Heartbeat terakhir", value: agoLabel(minutes), bad: stale },
    {
      label: "Observasi",
      value:
        run?.observations !== undefined
          ? `${run.observations} / ${run.expected_observations ?? "—"}`
          : "—",
    },
    {
      label: "Kelengkapan heartbeat",
      value: typeof coverage === "number" ? `${(coverage * 100).toFixed(1)}%` : "—",
    },
    { label: "Estimasi selesai", value: utcDateTime(run?.estimated_ready_at) },
    {
      label: "Sisa waktu",
      value:
        typeof run?.remaining_days === "number" ? `${run.remaining_days.toFixed(1)} hari` : "—",
    },
  ];
  return (
    <article
      className={`rounded-2xl border bg-white p-6 shadow-sm ${stale || run?.status === "interrupted" ? "border-rose-200" : "border-slate-200"} ${className}`}
    >
      <Header
        kicker="EVIDENCE CONTINUITY"
        title="Kontinuitas bukti"
        right={paperStatusLabels[run?.status ?? ""] ?? "—"}
      />
      <dl className="mt-5 grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
        {rows.map((row) => (
          <div key={row.label}>
            <dt className="text-xs text-slate-400">{row.label}</dt>
            <dd
              className={`mt-0.5 font-semibold ${row.bad ? "text-rose-600" : "text-slate-800"}`}
            >
              {row.value}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-5 text-xs leading-5 text-slate-400">
        Bukti sehat bila awal segmen tidak bergeser dan jumlah observasi terus naik (satu per
        15 menit). Jeda heartbeat lebih dari {CONTINUITY_GAP_MINUTES} menit memulai segmen
        baru dan menghitung ulang dari nol. Waktu ditampilkan dalam UTC.
      </p>
    </article>
  );
}
function Header({
  kicker,
  title,
  right,
}: {
  kicker: string;
  title: string;
  right?: string;
}) {
  return (
    <div className="flex items-start justify-between">
      <div>
        <p className="text-[10px] font-bold tracking-[.14em] text-slate-400">
          {kicker}
        </p>
        <h2 className="mt-1 text-lg font-bold">{title}</h2>
      </div>
      {right && (
        <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-[10px] font-semibold text-indigo-500">
          {right}
        </span>
      )}
    </div>
  );
}
function Stat({
  label,
  value,
  sub,
  icon,
  good,
}: {
  label: string;
  value: string;
  sub: string;
  icon: string;
  good?: boolean;
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <span
        className={`grid h-9 w-9 place-items-center rounded-lg ${good ? "bg-emerald-50 text-emerald-600" : "bg-indigo-50 text-indigo-500"}`}
      >
        <Icon name={icon} />
      </span>
      <p className="mt-4 text-xs text-slate-400">{label}</p>
      <strong className="mt-1 block text-xl tracking-tight">{value}</strong>
      <span
        className={`mt-1 block text-[11px] ${good ? "text-emerald-600" : "text-slate-400"}`}
      >
        {good ? "↗ " : ""}
        {sub}
      </span>
    </article>
  );
}
function Line({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-500">
        <i className={`mr-2 inline-block h-2 w-2 rounded-full ${color}`} />
        {label}
      </span>
      <strong>{value}</strong>
    </div>
  );
}
function Check({
  children,
  done,
}: {
  children: React.ReactNode;
  done: boolean;
}) {
  return (
    <li className={done ? "text-emerald-700" : ""}>
      <span
        className={`mr-3 inline-grid h-5 w-5 place-items-center rounded-full text-xs ${done ? "bg-emerald-100 text-emerald-600" : "bg-slate-100 text-slate-400"}`}
      >
        {done ? "✓" : "○"}
      </span>
      {children}
    </li>
  );
}
function Signal({ summary }: { summary: Data["summary"] }) {
  const row = Object.entries(summary?.latest_by_pair ?? {})[0];
  const trends = Object.entries(summary?.latest_trend_by_pair ?? {});
  const reason = summary?.hold_reasons[0];
  return (
    <div className="mt-7 flex gap-3">
      <span className="grid h-10 w-10 place-items-center rounded-xl bg-indigo-50 text-indigo-500">
        <Icon name="pulse" />
      </span>
      <div>
        <strong className="text-sm">
          {row
            ? (eventLabels[row[1].event_type] ?? row[1].event_type)
            : "Menunggu data"}
        </strong>
        {trends.length > 0 ? (
          <ul className="mt-1 space-y-1 text-xs leading-5 text-slate-400">
            {trends.map(([pair, target]) => (
              <li key={pair}>
                {pair} · eksposur target {pct(target.exposure ?? 0)} · kekuatan tren{" "}
                {pct(target.trend_score ?? 0)} · skala volatilitas{" "}
                {typeof target.vol_scale === "number" ? target.vol_scale.toFixed(2) : "—"}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-xs leading-5 text-slate-400">
            {row
              ? describeSignal(row[0], row[1])
              : "Bot akan mengisi ringkasan setelah candle dievaluasi."}
          </p>
        )}
        {reason && (
          <p className="mt-2 text-[11px] text-amber-600">
            Alasan utama: {reasonLabels[reason.reason] ?? reason.reason}
          </p>
        )}
      </div>
    </div>
  );
}
function ActivityRows({
  decisions,
  expanded = false,
}: {
  decisions: Decision[];
  expanded?: boolean;
}) {
  if (!decisions.length)
    return (
      <div className="grid min-h-48 place-items-center text-center text-slate-400">
        <div>
          <span className="mx-auto grid h-10 w-10 place-items-center rounded-xl bg-slate-100">
            <Icon name="pulse" />
          </span>
          <p className="mt-3 text-sm font-medium text-slate-500">
            Belum ada aktivitas tersimpan
          </p>
          <p className="mt-1 text-xs">
            Event bot akan muncul di sini saat layanan berjalan.
          </p>
        </div>
      </div>
    );
  return (
    <div className="mt-3 divide-y divide-slate-100">
      {decisions.map((item) => (
        <div
          className="grid grid-cols-[36px_1fr_auto] gap-3 py-3"
          key={item.id}
        >
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-indigo-50 text-indigo-500">
            <Icon name={item.event_type === "hold" ? "clock" : "pulse"} />
          </span>
          <div>
            <strong className="text-xs">
              {eventLabels[item.event_type] ??
                item.event_type.replaceAll("_", " ")}
            </strong>
            <p className="mt-0.5 text-[11px] text-slate-400">
              {typeof item.payload.pair === "string"
                ? item.payload.pair
                : "SYSTEM"}
              {typeof item.payload.reason === "string"
                ? ` · ${reasonLabels[item.payload.reason] ?? item.payload.reason}`
                : ""}
            </p>
            {expanded && (
              <code className="mt-2 block overflow-auto rounded bg-slate-50 p-2 text-[10px] text-slate-500">
                {JSON.stringify(item.payload)}
              </code>
            )}
          </div>
          <time className="text-[10px] text-slate-400">
            {when(item.created_at)}
          </time>
        </div>
      ))}
    </div>
  );
}
// The API starts a new evidence segment when the heartbeat gap exceeds this (PAPER_RUN_CONTINUITY_GAP_SECONDS).
const CONTINUITY_GAP_MINUTES = 30;
function minutesSince(iso?: string | null) {
  if (!iso) return undefined;
  const time = Date.parse(iso);
  return Number.isNaN(time) ? undefined : Math.max(0, Math.round((Date.now() - time) / 60000));
}
function agoLabel(minutes?: number) {
  if (minutes === undefined) return "—";
  if (minutes < 1) return "baru saja";
  if (minutes < 90) return `${minutes} menit lalu`;
  if (minutes < 60 * 48) return `${(minutes / 60).toFixed(1)} jam lalu`;
  return `${Math.round(minutes / 1440)} hari lalu`;
}
const utcDateTime = (iso?: string | null) =>
  iso
    ? new Intl.DateTimeFormat("id-ID", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "UTC",
      }).format(new Date(iso)) + " UTC"
    : "—";
type LatestSignal = NonNullable<Data["summary"]>["latest_by_pair"][string];
const pct = (value: number) => `${(value * 100).toFixed(0)}%`;
function describeSignal(pair: string, signal: LatestSignal) {
  // The daily trend strategy reports an exposure target; older 1H events report regime and RSI.
  if (typeof signal.exposure === "number") {
    const trend =
      typeof signal.trend_score === "number" ? ` · kekuatan tren ${pct(signal.trend_score)}` : "";
    const vol =
      typeof signal.vol_scale === "number" ? ` · skala volatilitas ${signal.vol_scale.toFixed(2)}` : "";
    return `${pair} · eksposur target ${pct(signal.exposure)}${trend}${vol}`;
  }
  return `${pair} · ${signal.regime ?? "regime belum tersedia"} · RSI ${signal.rsi?.toFixed(1) ?? "—"}`;
}
function percent(candles?: Candle[]) {
  return candles && candles.length > 1
    ? ((candles.at(-1)!.close - candles[0].close) / candles[0].close) * 100
    : 0;
}
function Chart({ candles }: { candles: Candle[] }) {
  if (candles.length < 2)
    return (
      <div className="mt-4 grid h-60 place-items-center rounded-xl bg-slate-50 text-xs text-slate-400">
        Memuat data harga…
      </div>
    );
  const prices = candles.map((c) => c.close);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = Math.max(max - min, max * 0.002);
  const points = prices
    .map(
      (v, i) =>
        `${((i / (prices.length - 1)) * 100).toFixed(2)},${(88 - ((v - min) / range) * 68).toFixed(2)}`,
    )
    .join(" ");
  const positive = percent(candles) >= 0;
  return (
    <div
      className={`relative mt-3 h-60 ${positive ? "text-emerald-500" : "text-rose-400"}`}
    >
      <svg
        className="h-full w-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        role="img"
        aria-label={`Grafik harga ${chart.span}`}
      >
        <defs>
          <linearGradient id="chart-fill" x1="0" y1="0" x2="0" y2="1">
            <stop stopColor="currentColor" stopOpacity=".22" />
            <stop offset="1" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          d={`M 0,88 L ${points.split(" ").join(" L ")} L 100,88 Z`}
          fill="url(#chart-fill)"
        />
        <polyline
          points={points}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.3"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <span className="absolute right-0 top-1 text-[10px] text-slate-400">
        ${money(max)}
      </span>
      <span className="absolute bottom-3 right-0 text-[10px] text-slate-400">
        ${money(min)}
      </span>
    </div>
  );
}
function Icon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    grid: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
    pulse: "M3 12h4l2-6 4 12 2-6h6",
    flask: "M9 3h6M10 3v6l-5 8a3 3 0 003 4h8a3 3 0 003-4l-5-8V3",
    refresh: "M20 11a8 8 0 10-2 5M20 4v7h-7",
    wallet: "M4 7a3 3 0 013-3h11v16H7a3 3 0 010-6h13v-7zM15 11h5",
    chart: "M4 19V5M4 19h16M8 16l3-4 3 2 5-7",
    bot: "M12 3v3M7 8H5v8h2M17 8h2v8h-2M7 7h10v11H7zM10 12h.01M14 12h.01",
    shield: "M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z",
    clock: "M12 7v5l3 2",
    info: "M12 8h.01M11 12h1v4h1",
  };
  return (
    <svg
      className="h-[17px] w-[17px]"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={paths[name] ?? paths.info} />
    </svg>
  );
}
