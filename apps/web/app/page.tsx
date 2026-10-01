"use client";

import { useCallback, useEffect, useState } from "react";

type Health = { status: string; timestamp: string };
type BotStatus = { mode: string; freqtrade: unknown; detail?: string };
type Decision = { id: number; event_type: string; payload: Record<string, unknown>; created_at: string };
type DashboardState = {
  health: Health | null;
  bot: BotStatus | null;
  decisions: Decision[];
  error: string | null;
  updatedAt: Date | null;
};

const initialState: DashboardState = { health: null, bot: null, decisions: [], error: null, updatedAt: null };

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
      const [healthResponse, botResponse, decisionsResponse] = await Promise.all([
        fetch("/api/trading/health", { cache: "no-store" }),
        fetch("/api/trading/v1/bot/status", { cache: "no-store" }),
        fetch("/api/trading/v1/decisions", { cache: "no-store" }),
      ]);
      if (!healthResponse.ok || !botResponse.ok || !decisionsResponse.ok) {
        throw new Error("Dashboard belum dapat mengambil data dari control API.");
      }
      const [health, bot, decisions] = (await Promise.all([
        healthResponse.json(),
        botResponse.json(),
        decisionsResponse.json(),
      ])) as [Health, BotStatus, Decision[]];
      setState({ health, bot, decisions, error: null, updatedAt: new Date() });
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
      <p className="notice">Mode aktif: <strong>dry-run</strong>. Tidak ada order riil yang dikirim dari dashboard.</p>

      <section className="status-grid" aria-label="Ringkasan kondisi bot">
        <StatusCard label="Control API" value={connected ? "Terhubung" : "Memuat"} detail="PostgreSQL dan Redis diperiksa oleh health check." active={connected} />
        <StatusCard label="Freqtrade" value={botState(state.bot)} detail="Execution engine Binance Spot." active={botState(state.bot) === "Berjalan"} />
        <StatusCard label="Pasangan awal" value="BTC / ETH" detail="BTC/USDT dan ETH/USDT, signal 1H dan regime 4H." />
        <StatusCard label="Audit keputusan" value={String(decisionCount)} detail="Event terbaru yang tersimpan pada control API." />
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
            <div><dt>Terakhir diperbarui</dt><dd>{state.updatedAt ? formatDate(state.updatedAt.toISOString()) : "—"}</dd></div>
          </dl>
          {state.bot?.detail ? <p className="notice notice-error">{state.bot.detail}</p> : null}
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
