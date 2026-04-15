import { TEAM_COLORS } from '../../utils/teamColors';

interface Props {
  code: string;
}

export default function TeamBadge({ code }: Props) {
  const color = TEAM_COLORS[code];
  return (
    <div className="flex items-center gap-1.5">
      <span
        className="w-2.5 h-2.5 rounded-full shrink-0"
        style={{ backgroundColor: color?.primary ?? '#6B7280' }}
      />
      <span className="font-mono text-text-secondary">{code}</span>
    </div>
  );
}
