import type { NextConfig } from "next";

const tradingApiOrigin = process.env.TRADING_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/trading/:path*", destination: `${tradingApiOrigin}/:path*` }];
  },
};

export default nextConfig;
