import path from "node:path";
import type { NextConfig } from "next";

const tradingApiOrigin = process.env.TRADING_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  turbopack: {
    root: path.resolve(__dirname, "../.."),
  },
  async rewrites() {
    // Only the read-only endpoints the dashboard uses are proxied. Everything else, notably the
    // unauthenticated /internal/* webhook and the token-protected control endpoints, is unreachable
    // through the web port and returns 404, so publishing this port cannot expose or modify them.
    const readOnlyPaths = [
      "/health",
      "/v1/operational-state",
      "/v1/bot/performance",
      "/v1/market/binance/candles",
      "/v1/market/binance/status",
      "/v1/decisions",
      "/v1/decisions/summary",
      "/v1/release/readiness",
      "/v1/paper-run",
    ];
    return readOnlyPaths.map((path) => ({
      source: `/api/trading${path}`,
      destination: `${tradingApiOrigin}${path}`,
    }));
  },
};

export default nextConfig;