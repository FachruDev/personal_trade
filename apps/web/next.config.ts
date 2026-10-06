import path from "node:path";
import type { NextConfig } from "next";

const tradingApiOrigin = process.env.TRADING_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  turbopack: {
    root: path.resolve(__dirname, "../.."),
  },
  async rewrites() {
    return [{ source: "/api/trading/:path*", destination: `${tradingApiOrigin}/:path*` }];
  },
};

export default nextConfig;