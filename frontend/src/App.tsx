import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/common/Layout';
import Dashboard from './pages/Dashboard';
import Leaderboard from './pages/Leaderboard';
import PlayerProfile from './pages/PlayerProfile';
import Guide from './pages/Guide';
import TalentLeaderboard from './pages/TalentLeaderboard';
import Matchup from './pages/Matchup';
import FantasyDashboard from './pages/FantasyDashboard';
import BatterMatchups from './pages/BatterMatchups';
import PitcherMatchups from './pages/PitcherMatchups';
import FantasyMatchupDetail from './pages/FantasyMatchupDetail';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/leaderboard" element={<Leaderboard />} />
            <Route path="/talent-leaderboard" element={<TalentLeaderboard />} />
            <Route path="/player/:playerId" element={<PlayerProfile />} />
            <Route path="/matchup" element={<Matchup />} />
            <Route path="/fantasy" element={<FantasyDashboard />} />
            <Route path="/fantasy/batters" element={<BatterMatchups />} />
            <Route path="/fantasy/pitchers" element={<PitcherMatchups />} />
            <Route path="/fantasy/matchup/:batterId/:pitcherId" element={<FantasyMatchupDetail />} />
            <Route path="/guide" element={<Guide />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
