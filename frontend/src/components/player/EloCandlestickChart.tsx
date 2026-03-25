import { useEffect, useRef, useState, useMemo } from 'react';
import { createChart, CandlestickSeries, LineSeries } from 'lightweight-charts';
import type { IChartApi, CandlestickData, LineData, Time } from 'lightweight-charts';
import type { DailyOhlc } from '../../types/elo';

interface EloCandlestickChartProps {
  data: DailyOhlc[];
  height?: number;
}

function forwardFillData(sparseData: DailyOhlc[]): { date: string; close: number }[] {
  if (sparseData.length === 0) return [];

  const result: { date: string; close: number }[] = [];
  const dataMap = new Map<string, number>();
  sparseData.forEach(d => dataMap.set(d.game_date, d.close));

  const startDate = new Date(sparseData[0].game_date + 'T12:00:00');
  const endDate = new Date(sparseData[sparseData.length - 1].game_date + 'T12:00:00');

  let lastClose = sparseData[0].close;
  const currentDate = new Date(startDate);

  while (currentDate <= endDate) {
    const dateStr = currentDate.toISOString().split('T')[0];
    if (dataMap.has(dateStr)) {
      lastClose = dataMap.get(dateStr)!;
    }
    result.push({ date: dateStr, close: lastClose });
    currentDate.setDate(currentDate.getDate() + 1);
  }

  return result;
}

function calculateMA(data: DailyOhlc[], period: number): LineData<Time>[] {
  if (data.length === 0) return [];

  const filled = forwardFillData(data);
  const originalDates = new Set(data.map(d => d.game_date));
  const result: LineData<Time>[] = [];

  for (let i = period - 1; i < filled.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += filled[i - j].close;
    }
    if (originalDates.has(filled[i].date)) {
      result.push({
        time: filled[i].date as Time,
        value: sum / period,
      });
    }
  }

  return result;
}

export default function EloCandlestickChart({ data, height = 400 }: EloCandlestickChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const [showOHLC, setShowOHLC] = useState(true);
  const [showMA5, setShowMA5] = useState(true);
  const [showMA15, setShowMA15] = useState(true);

  const ma5Data = useMemo(() => calculateMA(data, 5), [data]);
  const ma15Data = useMemo(() => calculateMA(data, 15), [data]);

  useEffect(() => {
    if (!chartContainerRef.current || data.length === 0) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const rafId = requestAnimationFrame(() => {
      if (!chartContainerRef.current) return;

      const chart = createChart(chartContainerRef.current, {
        width: chartContainerRef.current.clientWidth || 600,
        height,
        layout: {
          background: { color: '#FFFFFF' },
          textColor: '#6B7280',
        },
        grid: {
          vertLines: { color: '#E5E7EB' },
          horzLines: { color: '#E5E7EB' },
        },
        timeScale: {
          borderColor: '#E5E7EB',
        },
        rightPriceScale: {
          borderColor: '#E5E7EB',
        },
      });

      chartRef.current = chart;

      if (showOHLC) {
        const candlestickSeries = chart.addSeries(CandlestickSeries, {
          upColor: '#16A34A',
          downColor: '#DC2626',
          borderUpColor: '#16A34A',
          borderDownColor: '#DC2626',
          wickUpColor: '#16A34A',
          wickDownColor: '#DC2626',
        });

        const chartData: CandlestickData<Time>[] = data.map(d => ({
          time: d.game_date as Time,
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
        }));

        candlestickSeries.setData(chartData);
      }

      if (showMA5 && ma5Data.length > 0) {
        const ma5Series = chart.addSeries(LineSeries, {
          color: '#F97316',
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        ma5Series.setData(ma5Data);
      }

      if (showMA15 && ma15Data.length > 0) {
        const ma15Series = chart.addSeries(LineSeries, {
          color: '#3B82F6',
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        ma15Series.setData(ma15Data);
      }

      chart.timeScale().fitContent();
    });

    return () => {
      cancelAnimationFrame(rafId);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [data, height, showOHLC, showMA5, showMA15, ma5Data, ma15Data]);

  useEffect(() => {
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  if (data.length === 0) {
    return (
      <div className="h-[400px] flex items-center justify-center text-gray-500">
        No data available
      </div>
    );
  }

  return (
    <div>
      {/* Chart Toggles */}
      <div className="flex flex-wrap items-center justify-end gap-3 mb-4">
        <button
          onClick={() => setShowOHLC(!showOHLC)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
            showOHLC
              ? 'bg-green-100 text-green-700 ring-1 ring-green-300'
              : 'bg-gray-100 text-gray-500'
          }`}
        >
          <span className="w-3 h-3 border-2 border-green-500 rounded-sm"></span>
          OHLC
        </button>
        <button
          onClick={() => setShowMA5(!showMA5)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
            showMA5
              ? 'bg-orange-100 text-orange-700 ring-1 ring-orange-300'
              : 'bg-gray-100 text-gray-500'
          }`}
        >
          <span className="w-3 h-0.5 bg-orange-500 rounded"></span>
          MA5
        </button>
        <button
          onClick={() => setShowMA15(!showMA15)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
            showMA15
              ? 'bg-blue-100 text-blue-700 ring-1 ring-blue-300'
              : 'bg-gray-100 text-gray-500'
          }`}
        >
          <span className="w-3 h-0.5 bg-blue-500 rounded"></span>
          MA15
        </button>
      </div>

      {/* Chart */}
      <div ref={chartContainerRef} />
    </div>
  );
}
