import mlbLogo from '../../assets/mlb_logo.png';

interface TeamLogoProps {
  size?: number;
  className?: string;
}

/**
 * Displays the MLB logo in a circular frame.
 */
export default function TeamLogo({ size = 40, className = '' }: TeamLogoProps) {
  return (
    <img
      src={mlbLogo}
      alt="MLB"
      width={size}
      height={size}
      className={`rounded-full object-cover ${className}`}
    />
  );
}
