import { ChevronLeft, ChevronRight } from 'lucide-react';

interface Props {
  weekStart: string; // ISO date
  weekEnd: string;   // ISO date
  onPrev: () => void;
  onNext: () => void;
}

function formatDate(iso: string): string {
  const d = new Date(iso + 'T12:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

export default function WeekSelector({ weekStart, weekEnd, onPrev, onNext }: Props) {
  return (
    <div className="flex items-center gap-3">
      <button
        onClick={onPrev}
        className="p-2 rounded-lg hover:bg-white/10 transition-colors"
        aria-label="Previous week"
      >
        <ChevronLeft className="w-5 h-5 text-gray-400" />
      </button>
      <span className="text-sm font-semibold text-gray-300 min-w-[220px] text-center">
        {formatDate(weekStart)} — {formatDate(weekEnd)}
      </span>
      <button
        onClick={onNext}
        className="p-2 rounded-lg hover:bg-white/10 transition-colors"
        aria-label="Next week"
      >
        <ChevronRight className="w-5 h-5 text-gray-400" />
      </button>
    </div>
  );
}
