import { Trophy, Swords, Shield } from 'lucide-react';

interface Props {
  totalPoints: number;
  batterPoints: number;
  pitcherPoints: number;
  optimalTotalPoints?: number;
  optimalBatterPoints?: number;
  optimalPitcherPoints?: number;
  weekLabel?: string;
}

function StatCard({ label, value, subValue, subLabel, icon: Icon, color }: {
  label: string;
  value: number;
  subValue?: number;
  subLabel?: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}) {
  return (
    <div className="bg-bg-card rounded-xl p-4 border border-border-line shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`w-4 h-4 ${color}`} />
        <span className="text-xs font-semibold text-gray-400 uppercase">{label}</span>
      </div>
      <div className="text-2xl font-bold tabular-nums">{value.toFixed(1)}</div>
      {subValue !== undefined && (
        <div className="text-xs text-gray-500 mt-0.5 tabular-nums">
          {subLabel}: {subValue.toFixed(1)}
        </div>
      )}
    </div>
  );
}

export default function FantasyPointsPanel({
  totalPoints, batterPoints, pitcherPoints,
  optimalTotalPoints, optimalBatterPoints, optimalPitcherPoints,
  weekLabel,
}: Props) {
  const hasOptimal = optimalTotalPoints !== undefined;

  return (
    <div>
      {weekLabel && (
        <h3 className="text-sm font-semibold text-gray-400 mb-3">{weekLabel}</h3>
      )}
      <div className="grid grid-cols-3 gap-4">
        <StatCard
          label={hasOptimal ? 'Optimal Lineup' : 'Total'}
          value={hasOptimal ? optimalTotalPoints! : totalPoints}
          subValue={hasOptimal ? totalPoints : undefined}
          subLabel="Full roster"
          icon={Trophy}
          color="text-amber-500"
        />
        <StatCard
          label="Batters"
          value={hasOptimal ? optimalBatterPoints! : batterPoints}
          subValue={hasOptimal ? batterPoints : undefined}
          subLabel="Full roster"
          icon={Swords}
          color="text-blue-500"
        />
        <StatCard
          label="Pitchers"
          value={hasOptimal ? optimalPitcherPoints! : pitcherPoints}
          subValue={hasOptimal ? pitcherPoints : undefined}
          subLabel="Full roster"
          icon={Shield}
          color="text-purple-500"
        />
      </div>
    </div>
  );
}
