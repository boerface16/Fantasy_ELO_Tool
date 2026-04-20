import { useEffect, useRef } from 'react';
import { createChart, LineSeries } from 'lightweight-charts';
import type { IChartApi, LineData, Time } from 'lightweight-charts';
import type { DailyOhlc } from '../../types/elo';

export interface CompareSeries {
  playerId: string;
  name: string;
  team: string;
  color: string;
  data: DailyOhlc[];
}

interface EloCompareChartProps {
  series: CompareSeries[];
  height?: number;
}

function forwardFillClose(data: DailyOhlc[]): LineData<Time>[] {
  if (data.length === 0) return [];
  const dataMap = new Map<string, number>();
  data.forEach(d => dataMap.set(d.game_date, d.close));

  const start = new Date(data[0].game_date + 'T12:00:00');
  const end = new Date(data[data.length - 1].game_date + 'T12:00:00');
  const result: LineData<Time>[] = [];
  let lastClose = data[0].close;
  const cur = new Date(start);

  while (cur <= end) {
    const month = cur.getMonth(); // 0-indexed; Mar=2, Sep=8
    if (month >= 2 && month <= 8) {
      const dateStr = cur.toISOString().split('T')[0];
      if (dataMap.has(dateStr)) lastClose = dataMap.get(dateStr)!;
      result.push({ time: dateStr as Time, value: lastClose });
    }
    cur.setDate(cur.getDate() + 1);
  }
  return result;
}

export default function EloCompareChart({ series, height = 400 }: EloCompareChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const activeSeries = series.filter(s => s.data.length > 0);
    if (activeSeries.length === 0) return;

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

      for (const s of activeSeries) {
        const line = chart.addSeries(LineSeries, {
          color: s.color,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        line.setData(forwardFillClose(s.data));
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
      {/* Legend */}
      <div className="flex flex-wrap gap-4 mb-4">
        {series.map(s => (
          <div key={s.playerId} className="flex items-center gap-2">
            <span className="inline-block w-6 h-0.5 rounded" style={{ backgroundColor: s.color }} />
            <span className="text-sm font-semibold text-text-primary">{s.name}</span>
            <span className="text-xs text-text-secondary">{s.team}</span>
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
