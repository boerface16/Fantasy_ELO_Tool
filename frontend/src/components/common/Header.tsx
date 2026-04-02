import { Link, useLocation } from 'react-router-dom';
import { Search } from 'lucide-react';
import PlayerSearch from './PlayerSearch';

export default function Header() {
  const location = useLocation();

  return (
    <header className="sticky top-0 z-50 bg-bg-card border-b border-border-line px-4 md:px-10 py-3 shadow-sm">
      <div className="max-w-[1200px] mx-auto flex items-center justify-between gap-4">
        {/* Logo */}
        <Link to="/" className="text-xl font-bold leading-tight tracking-tight text-primary">
          Beers Fantasy Tool
        </Link>

        {/* Navigation */}
        <nav className="flex items-center gap-1">
          <Link
            to="/"
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
              location.pathname === '/'
                ? 'bg-primary text-white'
                : 'text-gray-400 hover:bg-white/10'
            }`}
          >
            Daily
          </Link>
          <Link
            to="/leaderboard"
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
              location.pathname === '/leaderboard'
                ? 'bg-primary text-white'
                : 'text-gray-400 hover:bg-white/10'
            }`}
          >
            Leaderboard
          </Link>
          <Link
            to="/talent-leaderboard"
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
              location.pathname === '/talent-leaderboard'
                ? 'bg-primary text-white'
                : 'text-gray-400 hover:bg-white/10'
            }`}
          >
            Talent
          </Link>
          <Link
            to="/matchup"
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
              location.pathname === '/matchup'
                ? 'bg-primary text-white'
                : 'text-gray-400 hover:bg-white/10'
            }`}
          >
            Matchup
          </Link>
          <Link
            to="/fantasy"
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
              location.pathname.startsWith('/fantasy')
                ? 'bg-primary text-white'
                : 'text-gray-400 hover:bg-white/10'
            }`}
          >
            Fantasy
          </Link>
          <Link
            to="/guide"
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
              location.pathname === '/guide'
                ? 'bg-primary text-white'
                : 'text-gray-400 hover:bg-white/10'
            }`}
          >
            Guide
          </Link>
        </nav>

        {/* Search */}
        <div className="hidden sm:block">
          <PlayerSearch />
        </div>
        <button className="sm:hidden flex h-10 w-10 items-center justify-center rounded-lg bg-white/10 text-gray-300">
          <Search className="w-5 h-5" />
        </button>
      </div>
    </header>
  );
}
