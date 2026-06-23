"use client";

import { useMemo, useState } from "react";

import { formatCompactNumber, formatPrice } from "@/lib/formatters";
import { pionexFuturesUrl } from "@/lib/links";
import type { ScoreEntry } from "@/lib/types";

type MarketsTableProps = {
  items: ScoreEntry[];
};

const categoryTabs = ["All", "Top", "New Listing", "AI", "Layer 1", "Layer 2", "DeFi", "GameFi", "NFT", "Meme", "PoW", "Storage"];

function assetName(symbol: string): string {
  return symbol.replace("_USDT_PERP", "");
}

function pairName(symbol: string): string {
  return symbol.replace("_USDT_PERP", "/USDT Perp");
}

function friendlyName(symbol: string): string {
  const names: Record<string, string> = {
    BTC_USDT_PERP: "Bitcoin",
    ETH_USDT_PERP: "Ethereum",
    XRP_USDT_PERP: "XRP",
    SOL_USDT_PERP: "Solana",
    DOGE_USDT_PERP: "Dogecoin",
    BNB_USDT_PERP: "BNB",
    LINK_USDT_PERP: "Chainlink",
    ADA_USDT_PERP: "Cardano",
    AVAX_USDT_PERP: "Avalanche",
    SUI_USDT_PERP: "Sui",
  };
  return names[symbol] ?? assetName(symbol);
}

function changeClass(value: number): string {
  if (value > 0) {
    return "text-emerald-300";
  }
  if (value < 0) {
    return "text-rose-300";
  }
  return "text-[var(--radar-muted)]";
}

function formatChange(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function tokenHue(symbol: string): string {
  const hues = ["bg-cyan-500", "bg-emerald-500", "bg-orange-500", "bg-violet-500", "bg-rose-500", "bg-sky-500", "bg-lime-500"];
  const index = assetName(symbol).split("").reduce((total, letter) => total + letter.charCodeAt(0), 0) % hues.length;
  return hues[index];
}

function matchesCategory(item: ScoreEntry, category: string): boolean {
  if (category === "All") {
    return true;
  }
  if (category === "Top") {
    return item.activity_score >= 65 || item.quote_volume_24h >= 1_000_000;
  }
  if (category === "New Listing") {
    return item.quote_volume_24h < 150_000 && Math.abs(item.price_change_24h) >= 2;
  }
  if (category === "AI") {
    return /AI|FET|TAO|AGIX|NFP|WLD|ARKM|NEAR/i.test(item.symbol);
  }
  if (category === "Layer 1") {
    return /BTC|ETH|SOL|BNB|ADA|AVAX|SUI|APT|SEI|TON|DOT|ATOM|NEAR/i.test(item.symbol);
  }
  if (category === "Layer 2") {
    return /ARB|OP|MANTA|STRK|ZK|ZKSYNC|POL|MATIC/i.test(item.symbol);
  }
  if (category === "DeFi") {
    return /UNI|AAVE|COMP|CRV|MKR|LDO|JUP|CAKE|DYDX|PENDLE/i.test(item.symbol);
  }
  if (category === "GameFi") {
    return /AXS|SAND|MANA|GALA|PIXEL|GMT|YGG|RONIN/i.test(item.symbol);
  }
  if (category === "NFT") {
    return /APE|BLUR|LOOKS|MAGIC|NFT/i.test(item.symbol);
  }
  if (category === "Meme") {
    return /DOGE|SHIB|PEPE|BONK|FLOKI|WIF|MEME|BOME|TURBO/i.test(item.symbol);
  }
  if (category === "PoW") {
    return /BTC|LTC|BCH|ETC|KAS|DOGE|DASH|ZEC/i.test(item.symbol);
  }
  if (category === "Storage") {
    return /FIL|AR|STORJ|SC/i.test(item.symbol);
  }
  return true;
}

export function MarketsTable({ items }: MarketsTableProps) {
  const [category, setCategory] = useState("All");
  const [query, setQuery] = useState("");
  const [favorites, setFavorites] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return items
      .filter((item) => matchesCategory(item, category))
      .filter((item) => {
        if (!normalized) {
          return true;
        }
        return `${item.symbol} ${friendlyName(item.symbol)}`.toLowerCase().includes(normalized);
      });
  }, [category, items, query]);

  function toggleFavorite(symbol: string) {
    setFavorites((current) => {
      const next = new Set(current);
      if (next.has(symbol)) {
        next.delete(symbol);
      } else {
        next.add(symbol);
      }
      return next;
    });
  }

  return (
    <div>
      <div className="flex flex-col gap-4 border-b border-[color:var(--radar-line)] pb-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="mr-2 text-[var(--radar-muted)]">Quote currency</span>
          <button className="rounded-full border border-[color:var(--radar-line-strong)] bg-[var(--radar-panel)] px-3 py-2 font-semibold text-[var(--radar-ink)] transition hover:border-[color:var(--radar-sea)]">
            USDT ▾
          </button>
          {categoryTabs.map((tab) => (
            <button
              className={`rounded-full px-3 py-2 font-semibold transition ${category === tab ? "bg-[var(--radar-panel)] text-[var(--radar-ink)]" : "text-[var(--radar-muted)] hover:bg-[var(--radar-panel-soft)] hover:text-[var(--radar-ink)]"}`}
              key={tab}
              onClick={() => setCategory(tab)}
              type="button"
            >
              {tab}
            </button>
          ))}
        </div>
        <label className="flex min-w-0 items-center rounded-[18px] border border-[color:var(--radar-line)] bg-[rgba(6,14,12,0.48)] px-4 py-3 transition focus-within:border-[color:var(--radar-sea)] hover:border-[color:var(--radar-line-strong)] xl:w-72">
          <span className="mr-2 text-[var(--radar-muted)]">⌕</span>
          <input
            className="min-w-0 flex-1 bg-transparent text-sm text-[var(--radar-ink)] outline-none placeholder:text-[var(--radar-muted)]"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search coin name"
            value={query}
          />
        </label>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-[color:var(--radar-line)] text-left text-xs text-[var(--radar-muted)]">
              <th className="w-10 px-3 py-4 font-medium" />
              <th className="px-3 py-4 font-medium">Pair ↕</th>
              <th className="px-3 py-4 font-medium">Price ↕</th>
              <th className="px-3 py-4 font-medium">Fiat price(USD) ↕</th>
              <th className="px-3 py-4 font-medium">24H Volume ↕</th>
              <th className="px-3 py-4 font-medium">24H Change ↕</th>
              <th className="px-3 py-4 font-medium">Activity</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((item) => {
              const favorite = favorites.has(item.symbol);
              return (
                <tr
                  className="group border-b border-[color:var(--radar-line)] transition hover:bg-[var(--radar-panel-soft)]"
                  key={item.symbol}
                >
                  <td className="px-3 py-4">
                    <button
                      aria-label={`Favorite ${item.symbol}`}
                      className={`text-lg transition hover:scale-110 ${favorite ? "text-[var(--radar-sun)]" : "text-slate-600 group-hover:text-[var(--radar-muted)]"}`}
                      onClick={() => toggleFavorite(item.symbol)}
                      type="button"
                    >
                      ★
                    </button>
                  </td>
                  <td className="px-3 py-4">
                    <a
                      className="flex items-center gap-3 rounded-md underline-offset-4 transition hover:text-[var(--radar-sea)] hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--radar-sea)]"
                      href={pionexFuturesUrl(item.symbol)}
                      rel="noreferrer"
                      target="_blank"
                      title={`Open ${pairName(item.symbol)} on Pionex`}
                    >
                      <span className={`grid h-9 w-9 place-items-center rounded-full ${tokenHue(item.symbol)} text-sm font-bold text-white shadow-[0_12px_30px_-18px_rgba(255,255,255,0.8)]`}>
                        {assetName(item.symbol).slice(0, 1)}
                      </span>
                      <div className="min-w-0">
                        <div className="font-semibold text-[var(--radar-ink)]">{pairName(item.symbol)}</div>
                        <div className="text-xs text-[var(--radar-muted)]">{friendlyName(item.symbol)}</div>
                      </div>
                    </a>
                  </td>
                  <td className="px-3 py-4 font-semibold text-[var(--radar-ink)]">{formatPrice(item.price)}</td>
                  <td className="px-3 py-4 font-semibold text-[var(--radar-ink)]">${formatPrice(item.price)}</td>
                  <td className="px-3 py-4 font-semibold text-[var(--radar-ink)]">{formatCompactNumber(item.quote_volume_24h)}</td>
                  <td className={`px-3 py-4 font-semibold ${changeClass(item.price_change_24h)}`}>{formatChange(item.price_change_24h)}</td>
                  <td className="px-3 py-4">
                    <div className="h-2 w-28 overflow-hidden rounded-full bg-[rgba(238,248,244,0.1)]">
                      <div
                        className="h-full rounded-full bg-[var(--radar-sea)] transition-all"
                        style={{ width: `${Math.min(100, Math.max(4, item.activity_score))}%` }}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {filtered.length === 0 ? (
        <div className="py-10 text-center text-sm text-[var(--radar-muted)]">No futures matched your current filter.</div>
      ) : null}
    </div>
  );
}
