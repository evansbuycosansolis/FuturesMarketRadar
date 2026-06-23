"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

type SessionArc = {
  label: string;
  startHour: number;
  endHour: number;
  radius: number;
  width: number;
  color: string;
};

type CityArc = {
  label: string;
  startHour: number;
  endHour: number;
  radius: number;
};

const sessions: SessionArc[] = [
  { label: "Asia", startHour: 23, endHour: 7, radius: 146, width: 18, color: "#2eb79a" },
  { label: "London", startHour: 7, endHour: 15, radius: 125, width: 18, color: "#d89b32" },
  { label: "New York", startHour: 13, endHour: 21, radius: 104, width: 18, color: "#f06a24" },
];

const cityArcs: CityArc[] = [
  { label: "WELLINGTON", startHour: 21, endHour: 5, radius: 81 },
  { label: "SYDNEY", startHour: 22, endHour: 6, radius: 70 },
  { label: "TOKYO", startHour: 0, endHour: 8, radius: 59 },
  { label: "SINGAPORE", startHour: 1, endHour: 9, radius: 48 },
  { label: "LONDON", startHour: 7, endHour: 15, radius: 37 },
  { label: "NEW YORK", startHour: 13, endHour: 21, radius: 26 },
];

const cityLegend = [
  "WELLINGTON",
  "SYDNEY",
  "TOKYO",
  "SINGAPORE",
  "HONG KONG",
  "SHANGHAI",
  "MUMBAI",
  "DUBAI",
  "JOHANNESBURG",
  "MOSCOW",
  "RIYADH",
  "LONDON",
  "ZURICH",
  "FRANKFURT",
  "SAO PAULO",
  "NEW YORK",
  "TORONTO",
  "CHICAGO",
];

const MONTREAL_TIME_ZONE = "America/Toronto";
const MONTREAL_TIME_PARTS_FORMATTER = new Intl.DateTimeFormat("en-US", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
  timeZone: MONTREAL_TIME_ZONE,
});

function polarToCartesian(cx: number, cy: number, radius: number, angleDegrees: number) {
  const angleRadians = ((angleDegrees - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(angleRadians),
    y: cy + radius * Math.sin(angleRadians),
  };
}

function hourToAngle(hour: number): number {
  return (hour / 24) * 360;
}

function describeArc(cx: number, cy: number, radius: number, startHour: number, endHour: number): string {
  const normalizedEnd = endHour <= startHour ? endHour + 24 : endHour;
  const startAngle = hourToAngle(startHour);
  const endAngle = hourToAngle(normalizedEnd);
  const start = polarToCartesian(cx, cy, radius, endAngle);
  const end = polarToCartesian(cx, cy, radius, startAngle);
  const largeArcFlag = normalizedEnd - startHour <= 12 ? "0" : "1";

  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
}

function currentSession(date: Date): string {
  const day = date.getUTCDay();
  const hour = date.getUTCHours();
  if (day === 0 || (day === 6 && hour >= 21)) {
    return "Weekend liquidity watch";
  }
  if (hour >= 23 || hour < 7) {
    return "Asian Session";
  }
  if (hour >= 7 && hour < 15) {
    return "London Session";
  }
  return "New York Session";
}

function utcTimeLabel(date: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "UTC",
  }).format(date);
}

function montrealTimeLabel(date: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: MONTREAL_TIME_ZONE,
  }).format(date);
}

function montrealTimeParts(date: Date): { hour: number; minute: number; second: number } {
  const parts = MONTREAL_TIME_PARTS_FORMATTER.formatToParts(date);
  const value = (type: string) => Number(parts.find((part) => part.type === type)?.value ?? 0);

  return {
    hour: value("hour"),
    minute: value("minute"),
    second: value("second"),
  };
}

function montrealHourForUtcHour(date: Date, utcHour: number): number {
  const reference = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), utcHour));
  return montrealTimeParts(reference).hour;
}

function isSessionActive(date: Date, session: SessionArc): boolean {
  const hour = date.getUTCHours() + date.getUTCMinutes() / 60 + date.getUTCSeconds() / 3600;

  if (session.endHour <= session.startHour) {
    return hour >= session.startHour || hour < session.endHour;
  }

  return hour >= session.startHour && hour < session.endHour;
}

type MarketTradingClockProps = {
  children?: ReactNode;
};

export function MarketTradingClock({ children }: MarketTradingClockProps) {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const initialTick = window.setTimeout(() => setNow(new Date()), 0);
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => {
      window.clearTimeout(initialTick);
      window.clearInterval(timer);
    };
  }, []);

  const clock = useMemo(() => {
    if (!now) {
      return null;
    }
    const montreal = montrealTimeParts(now);
    const hour = montreal.hour + montreal.minute / 60 + montreal.second / 3600;
    const minute = montreal.minute + montreal.second / 60;
    return {
      hourAngle: hourToAngle(hour),
      minuteAngle: (minute / 60) * 360,
      secondAngle: (montreal.second / 60) * 360,
      session: currentSession(now),
      utcLabel: utcTimeLabel(now),
      montrealLabel: montrealTimeLabel(now),
      activeSessions: new Set(sessions.filter((session) => isSessionActive(now, session)).map((session) => session.label)),
    };
  }, [now]);

  const cx = 180;
  const cy = 180;

  return (
    <section className="radar-card overflow-hidden p-5 sm:p-6">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="radar-chip">Market Trading Clock</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--radar-ink)]">Global session wheel</h2>
        </div>
        <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] px-4 py-3 text-sm text-[var(--radar-muted)]">
          <div className="font-semibold text-[var(--radar-ink)]">{clock?.session ?? "Syncing UTC clock"}</div>
          <div>Montréal {clock?.montrealLabel ?? "--:--:--"}</div>
          <div className="text-xs">UTC {clock?.utcLabel ?? "--:--:--"}</div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(320px,440px)_1fr] lg:items-center">
        <div className="mx-auto aspect-square w-full max-w-[440px] rounded-[24px] border border-[color:var(--radar-line)] bg-black p-3">
          {!clock ? (
            <div className="grid h-full w-full place-items-center rounded-[18px] bg-[#050807] text-center">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--radar-muted)]">
                  Market Clock
                </div>
                <div className="mt-2 text-sm font-semibold text-[var(--radar-ink)]">Syncing Montréal time</div>
              </div>
            </div>
          ) : (
          <svg aria-label="UTC market trading session clock" className="h-full w-full" viewBox="0 0 360 360" role="img">
            <circle cx={cx} cy={cy} fill="#050807" r="174" />
            <circle cx={cx} cy={cy} fill="none" r="166" stroke="#13231f" strokeWidth="12" />

            {sessions.map((session) => (
              <path
                d={describeArc(
                  cx,
                  cy,
                  session.radius,
                  now ? montrealHourForUtcHour(now, session.startHour) : session.startHour,
                  now ? montrealHourForUtcHour(now, session.endHour) : session.endHour,
                )}
                fill="none"
                key={session.label}
                stroke={session.color}
                strokeLinecap="butt"
                strokeWidth={session.width}
              />
            ))}

            {cityArcs.map((city) => (
              <path
                d={describeArc(
                  cx,
                  cy,
                  city.radius,
                  now ? montrealHourForUtcHour(now, city.startHour) : city.startHour,
                  now ? montrealHourForUtcHour(now, city.endHour) : city.endHour,
                )}
                fill="none"
                key={city.label}
                opacity="0.52"
                stroke="#a8aaa5"
                strokeLinecap="butt"
                strokeWidth="8"
              />
            ))}

            {Array.from({ length: 144 }).map((_, index) => {
              const isHour = index % 6 === 0;
              const angle = (index / 144) * 360;
              const outer = polarToCartesian(cx, cy, 164, angle);
              const inner = polarToCartesian(cx, cy, isHour ? 150 : 156, angle);
              return (
                <line
                  key={index}
                  stroke={isHour ? "#dbe8e2" : "#5d6a65"}
                  strokeLinecap="round"
                  strokeWidth={isHour ? 1.5 : 0.7}
                  x1={outer.x}
                  x2={inner.x}
                  y1={outer.y}
                  y2={inner.y}
                />
              );
            })}

            {Array.from({ length: 24 }).map((_, hour) => {
              const point = polarToCartesian(cx, cy, 139, hourToAngle(hour));
              return (
                <text
                  dominantBaseline="middle"
                  fill="#d8e7df"
                  fontSize="9"
                  key={hour}
                  textAnchor="middle"
                  x={point.x}
                  y={point.y}
                >
                  {hour === 0 ? "24" : String(hour).padStart(2, "0")}
                </text>
              );
            })}

            {cityArcs.map((city) => {
              const localStart = now ? montrealHourForUtcHour(now, city.startHour) : city.startHour;
              const localEnd = now ? montrealHourForUtcHour(now, city.endHour) : city.endHour;
              const midHour = localEnd <= localStart ? (localStart + localEnd + 24) / 2 : (localStart + localEnd) / 2;
              const point = polarToCartesian(cx, cy, city.radius, hourToAngle(midHour));
              return (
                <text
                  dominantBaseline="middle"
                  fill="#050807"
                  fontSize="6"
                  fontWeight="700"
                  key={`${city.label}-text`}
                  textAnchor="middle"
                  transform={`rotate(${hourToAngle(midHour) - 90} ${point.x} ${point.y})`}
                  x={point.x}
                  y={point.y}
                >
                  {city.label}
                </text>
              );
            })}

            <circle cx={cx} cy={cy} fill="#07100d" r="39" stroke="#43514c" strokeWidth="1" />
            <text dominantBaseline="middle" fill="#dce9e3" fontSize="11" fontWeight="700" textAnchor="middle" x={cx} y={cy - 10}>
              MTL
            </text>
            <text dominantBaseline="middle" fill="#94a39d" fontSize="8" textAnchor="middle" x={cx} y={cy + 8}>
              {clock?.montrealLabel ?? "--:--:--"}
            </text>

            {clock ? (
              <>
                <line
                  stroke="#e7f2ed"
                  strokeLinecap="round"
                  strokeWidth="3"
                  transform={`rotate(${clock.hourAngle} ${cx} ${cy})`}
                  x1={cx}
                  x2={cx}
                  y1={cy + 10}
                  y2={cy - 118}
                />
                <line
                  stroke="#2eb79a"
                  strokeLinecap="round"
                  strokeWidth="2"
                  transform={`rotate(${clock.minuteAngle} ${cx} ${cy})`}
                  x1={cx}
                  x2={cx}
                  y1={cy + 12}
                  y2={cy - 148}
                />
                <line
                  opacity="0.75"
                  stroke="#f04d68"
                  strokeLinecap="round"
                  strokeWidth="1"
                  transform={`rotate(${clock.secondAngle} ${cx} ${cy})`}
                  x1={cx}
                  x2={cx}
                  y1={cy + 16}
                  y2={cy - 154}
                />
              </>
            ) : null}
            <circle cx={cx} cy={cy} fill="#e7f2ed" r="5" />
          </svg>
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          {sessions.map((session) => {
            const isActive = clock?.activeSessions.has(session.label) ?? false;
            const localStart = now ? montrealHourForUtcHour(now, session.startHour) : session.startHour;
            const localEnd = now ? montrealHourForUtcHour(now, session.endHour) : session.endHour;
            return (
            <div
              className={`rounded-[18px] border p-4 transition ${
                isActive
                  ? "border-[color:rgba(46,183,154,0.45)] bg-[color:rgba(46,183,154,0.1)]"
                  : "border-[color:var(--radar-line)] bg-[var(--radar-panel-soft)] hover:border-[color:rgba(255,255,255,0.34)]"
              }`}
              key={session.label}
            >
              <div className="flex items-center gap-2">
                <span className={`h-3 w-3 rounded-full ${isActive ? "bg-[var(--radar-sea)]" : "bg-white"}`} />
                <div className="font-semibold text-[var(--radar-ink)]">{session.label}</div>
              </div>
              <div className="mt-2 text-sm text-[var(--radar-muted)]">
                {String(localStart).padStart(2, "0")}:00-{String(localEnd).padStart(2, "0")}:00 Montréal
              </div>
              <div className="mt-1 text-xs text-[var(--radar-muted)]">
                {String(session.startHour).padStart(2, "0")}:00-{String(session.endHour).padStart(2, "0")}:00 UTC
              </div>
            </div>
            );
          })}
          <div className="rounded-[18px] border border-[color:var(--radar-line)] bg-black/15 p-4 sm:col-span-3">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--radar-muted)]">City Rings</div>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-sm font-semibold text-[var(--radar-muted)]">
              {cityLegend.map((city) => (
                <span className={city === "NEW YORK" || city === "TORONTO" || city === "CHICAGO" ? "text-[var(--radar-sun)]" : ""} key={city}>
                  {city}
                </span>
              ))}
            </div>
          </div>
          {children ? <div className="sm:col-span-3">{children}</div> : null}
        </div>
      </div>
    </section>
  );
}
