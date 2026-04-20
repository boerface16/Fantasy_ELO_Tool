import { useEffect, useRef } from 'react';
import { createChart, LineSeries } from 'lightweight-charts';
import type { IChartApi, LineData, Time } from 'lightweight-charts';
import type { TeamEloTrendEntry } from '../../types/fantasy';

export interface TeamCompareSeries {
  teamCode: string;
  color: string;
  data: TeamEloTrendEntry[];
}

interface TeamCompareChartProps {
  series: TeamCompareSeries[];
  height?: number;
}

function dedupeAndFill(data: TeamEloTrendEntry[]): LineData<Time>[] {
  if (data.length === 0) return [];
  const byDate = new Map<string, number>();
  for (const h of data) byDate.set(h.date, h.eloAfter);
  const sorted = Array.from(byDate.entries()).sort(([a], [b]) => a.localeCompare(b));
  if (sorted.length === 0) return [];

  const result: LineData<Time>[] = [];
  const start = new Date(sorted[0][0] + 'T12:00:00');
  const end = new Date(sorted[sorted.length - 1][0] + 'T12:00:00');
  const dateValueMap = new Map(sorted);
  let lastValue = sorted[0][1];
  const cur = new Date(start);

  while (cur <= end) {
    const month = cur.getMonth(); // 0-indexed; Mar=2, Sep=8
    if (month >= 2 && month <= 8) {
      const dateStr = cur.toISOString().split('T')[0];
      if (dateValueMap.has(dateStr)) lastValue = dateValueMap.get(dateStr)!;
      result.push({ time: dateStr as Time, value: lastValue });
    }
    cur.setDate(cur.getDate() + 1);
  }
  return result;
}

export default function TeamCompareChart({ series, height = 400 }: TeamCompareChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const active = series.filter(s => s.data.length > 0);
    if (active.length === 0) return;

    if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; }

    const rafId = requestAnimationFrame(() => {
      if (!containerRef.current) return;
      const chart = createChart(containerRef.current, {
        width: containerRef.current.clientWidth || 600,
        height,
        layout: { background: { color: '#16161e' }, textColor: '#8a8d98' },
        grid: { vertLines: { color: '#242430' }, horzLines: { color: '#242430' } },
        timeScale: { borderColor: '#242430' },
        rightPriceScale: { borderColor: '#242430' },
      });
      chartRef.current = chart;

      for (const s of active) {
        const line = chart.addSeries(LineSeries, {
          color: s.color,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        line.setData(dedupeAndFill(s.data));
      }

      chart.timeScale().fitContent();
    });

    return () => {
      cancelAnimationFrame(rafId);
      if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; }
    };
  }, [series, height]);

  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const hasData = series.some(s => s.data.length > 0);

  return (
    <div>
      <div className="flex flex-wrap gap-4 mb-4">
        {series.map(s => (
          <div key={s.teamCode} className="flex items-center gap-2">
            <span className="inline-block w-6 h-0.5 rounded" style={{ backgroundColor: s.color }} />
            <span className="text-sm font-semibold text-text-primary">{s.teamCode}</span>
          </div>
        ))}
      </div>
      {!hasData ? (
        <div className="flex items-center justify-center text-text-secondary" style={{ height }}>
          No data available
        </div>
      ) : (
        <div ref={containerRef} />
      )}
    </div>
  );
}
