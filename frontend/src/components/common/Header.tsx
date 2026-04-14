import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import PlayerSearch from './PlayerSearch';

const NAV_LINKS = [
  { to: '/', label: 'Daily', exact: true },
  { to: '/leaderboard', label: 'Leaderboard', exact: true },
  { to: '/talent-leaderboard', label: 'Talent', exact: true },
  { to: '/team-elo', label: 'Team ELO', exact: false },
  { to: '/matchup', label: 'Matchup', exact: true },
  { to: '/fantasy', label: 'Fantasy', exact: false },
  { to: '/guide', label: 'Guide', exact: true },
];

export default function Header() {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  function isActive(to: string, exact: boolean) {
    return exact ? location.pathname === to : location.pathname.startsWith(to);
  }

  function linkClass(to: string, exact: boolean) {
    return `px-4 py-2 rounded-full text-sm font-semibold transition-all ${
      isActive(to, exact) ? 'bg-primary text-text-primary' : 'text-text-secondary hover:bg-bg-elevated'
    }`;
  }

  return (
    <header className="sticky top-0 z-50 bg-bg-card/80 backdrop-blur-md border-b border-border-line shadow-sm">
      <div className="max-w-[1200px] mx-auto px-4 md:px-10 py-3 flex items-center justify-between gap-4">
        {/* Logo */}
        <Link to="/" className="text-xl font-semibold leading-tight tracking-tight text-primary shrink-0">
          Beer's Fantasy Baseball Tool
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center gap-1">
          {NAV_LINKS.map(({ to, label, exact }) => (
            <Link key={to} to={to} className={linkClass(to, exact)}>
              {label}
            </Link>
          ))}
        </nav>

        {/* Desktop Search */}
        <div className="hidden md:block">
          <PlayerSearch />
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden flex h-10 w-10 items-center justify-center rounded-lg bg-bg-elevated text-text-secondary"
          onClick={() => setMenuOpen((o) => !o)}
          aria-label="Toggle menu"
        >
          {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div className="md:hidden border-t border-border-line bg-bg-card/95 backdrop-blur-md px-4 py-3 flex flex-col gap-1">
          {NAV_LINKS.map(({ to, label, exact }) => (
            <Link
              key={to}
              to={to}
              className={linkClass(to, exact)}
              onClick={() => setMenuOpen(false)}
            >
              {label}
            </Link>
          ))}
          <div className="pt-2">
            <PlayerSearch />
          </div>
        </div>
      )}
    </header>
  );
}
