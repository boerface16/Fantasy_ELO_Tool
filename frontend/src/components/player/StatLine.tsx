import type { PlayerStatLine } from '../../types/elo';

interface Props {
  data: PlayerStatLine;
  role: 'BATTING' | 'PITCHING';
}

function fmt(val: number | undefined | null, type: 'int' | 'pct' | 'woba' | 'dec2' | 'dec1'): string {
  if (val === undefined || val === null) return '—';
  switch (type) {
    case 'int':   return String(Math.round(val));
    case 'pct':   return `${(val * 100).toFixed(1)}%`;
    case 'woba':  return val.toFixed(3).replace(/^0/, '');   // .340 not 0.340
    case 'dec2':  return val.toFixed(2);
    case 'dec1':  return val.toFixed(1);
    default:      return String(val);
  }
}

function Pill({ label, value }: { label: string; value: string }) {
  const isDash = value === '—';
  return (
    <div className="flex flex-col items-center px-3 border-r border-border-line last:border-0 first:pl-0">
      <span className="text-[10px] uppercase tracking-wider text-text-tertiary leading-none mb-1">
        {label}
      </span>
      <span className={`text-sm font-bold leading-none ${isDash ? 'text-text-tertiary' : 'text-text-primary'}`}>
        {value}
      </span>
    </div>
  );
}

export default function StatLine({ data, role }: Props) {
  if (role === 'PITCHING') {
    return (
      <div className="flex flex-wrap items-center mt-3 gap-y-2">
        <Pill label="BF"    value={fmt(data.bf,       'int')} />
        <Pill label="K"     value={fmt(data.k,        'int')} />
        <Pill label="ER"    value={fmt(data.er,       'int')} />
        <Pill label="BB"    value={fmt(data.bb,       'int')} />
        <Pill label="K%"    value={fmt(data.k_pct,    'pct')} />
        <Pill label="BB%"   value={fmt(data.bb_pct,   'pct')} />
        <Pill label="K-BB%" value={fmt(data.k_bb_pct, 'pct')} />
        <Pill label="xWOBA" value={fmt(data.xwoba,    'woba')} />
        <Pill label="xFIP-" value={fmt(data.xfip_minus, 'dec1')} />
        <Pill label="SIERA" value={fmt(data.siera,    'dec2')} />
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center mt-3 gap-y-2">
      <Pill label="PA"    value={fmt(data.pa,       'int')} />
      <Pill label="K"     value={fmt(data.k,        'int')} />
      <Pill label="H"     value={fmt(data.h,        'int')} />
      <Pill label="HR"    value={fmt(data.hr,       'int')} />
      <Pill label="BB"    value={fmt(data.bb,       'int')} />
      <Pill label="K%"    value={fmt(data.k_pct,    'pct')} />
      <Pill label="BB%"   value={fmt(data.bb_pct,   'pct')} />
      <Pill label="xWOBA" value={fmt(data.xwoba,    'woba')} />
      <Pill label="WRC+"  value={fmt(data.wrc_plus, 'int')} />
      <Pill label="WAR"   value={fmt(data.war,      'dec1')} />
    </div>
  );
}
