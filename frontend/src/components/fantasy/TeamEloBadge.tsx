import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface Props {
  teamCode: string;
  elo: number;
}

export default function TeamEloBadge({ teamCode, elo }: Props) {
  const isHot = elo > 1530;
  const isCold = elo < 1470;

  const colorClass = isHot
    ? 'bg-green-900/30 text-green-400 border-green-800'
    : isCold
      ? 'bg-red-900/30 text-red-400 border-red-800'
      : 'bg-bg-elevated/50 text-text-secondary border-border-line';

  const Icon = isHot ? TrendingUp : isCold ? TrendingDown : Minus;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${colorClass}`}>
      <Icon className="w-3 h-3" />
      <span>{teamCode}</span>
      <span className="tabular-nums">{Math.round(elo)}</span>
    </span>
  );
}
