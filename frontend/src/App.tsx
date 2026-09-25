import { useState, useEffect } from 'react';

type UpcomingMatch = {
  id: string;
  radiant_name: string;
  dire_name: string;
  radiant_account_ids: number[];
  dire_account_ids: number[];
};

type HistoryMatch = {
  match_id: number;
  date: string;
  radiant_name: string;
  dire_name: string;
  radiant_win: boolean;
  duration: number;
  league_name: string;
};

type Player = {
  account_id: number;
  name: string;
  fantasy_role: number | null;
  glicko_rating: number;
  glicko_rd: number;
};

type MatchDetail = {
  match_id: number;
  date: string;
  radiant_name: string;
  dire_name: string;
  radiant_win: boolean;
  duration: number;
  league_name: string;
  radiant_roster: Player[];
  dire_roster: Player[];
};

function useHash() {
  const [hash, setHash] = useState(window.location.hash.slice(1) || '');
  useEffect(() => {
    const onHashChange = () => setHash(window.location.hash.slice(1) || '');
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);
  return hash;
}

function NavBar({ current }: { current: string }) {
  const links = [
    { hash: '', label: 'Predict' },
    { hash: 'matches', label: 'Match History' }
  ];
  return (
    <nav className="flex gap-6 border-b border-gray-800 mb-8">
      {links.map(link => (
        <a
          key={link.hash}
          href={`#${link.hash}`}
          className={`pb-3 text-sm transition-colors ${
            current === link.hash
              ? 'border-b-2 border-white text-white'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          {link.label}
        </a>
      ))}
    </nav>
  );
}

function PredictView() {
  const [matches, setMatches] = useState<UpcomingMatch[]>([]);
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/upcoming')
      .then(res => res.json())
      .then(data => setMatches(data.matches))
      .catch(() => setError("Failed to load upcoming matches"));
  }, []);

  async function handlePredict(match: UpcomingMatch) {
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const res = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          radiant_account_ids: match.radiant_account_ids, 
          dire_account_ids: match.dire_account_ids 
        }),
      });
      
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error: ${res.status}`);
      }
      
      const data = await res.json();
      setResult(`${match.radiant_name} vs ${match.dire_name}: ${(data.radiant_win_prob * 100).toFixed(1)}% Radiant Win`);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {matches.length === 0 && !error && <p className="text-gray-500">Loading matches...</p>}
      
      <div className="space-y-3">
        {matches.map(m => (
          <div key={m.id} className="border-b border-gray-800 py-4 flex justify-between items-center hover:bg-gray-900/20 px-2">
            <div className="flex items-center gap-4">
              <span className="text-[#4ADE80] w-40 text-right">{m.radiant_name}</span>
              <span className="text-gray-600 text-sm">vs</span>
              <span className="text-[#F87171] w-40">{m.dire_name}</span>
            </div>
            <button 
              onClick={() => handlePredict(m)}
              disabled={loading}
              className="bg-white text-black text-sm py-1.5 px-5 hover:bg-gray-200 disabled:opacity-50"
            >
              Predict
            </button>
          </div>
        ))}
      </div>

      {error && (
        <div className="border border-red-900/50 bg-red-900/10 text-red-400 p-4 mt-6 text-sm">
          {error}
        </div>
      )}

      {result && (
        <div className="border-t border-gray-800 mt-8 pt-6">
          <div className="text-2xl text-white">{result}</div>
        </div>
      )}
    </>
  );
}

function MatchHistoryView() {
  const [matches, setMatches] = useState<HistoryMatch[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [detail, setDetail] = useState<MatchDetail | null>(null);

  useEffect(() => {
    fetch(`/api/matches?page=${page}&per_page=20`)
      .then(res => res.json())
      .then(data => {
        setMatches(data.matches);
        setTotal(data.total);
      });
  }, [page]);

  async function toggleExpand(matchId: number) {
    if (expanded === matchId) {
      setExpanded(null);
      setDetail(null);
    } else {
      setExpanded(matchId);
      const res = await fetch(`/api/matches/${matchId}`);
      const data = await res.json();
      setDetail(data);
    }
  }

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const roleLabels: Record<number, string> = { 
    0: 'Carry', 
    1: 'Mid', 
    2: 'Offlane', 
    3: 'Soft Support',
    4: 'Hard Support'
  };

  return (
    <>
      <div className="space-y-0">
        {matches.map(m => (
          <div key={m.match_id}>
            <div 
              onClick={() => toggleExpand(m.match_id)}
              className="border-b border-gray-800 py-4 px-2 hover:bg-gray-900/20 cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4 flex-1">
                  <span className={`w-40 text-right ${m.radiant_win ? 'text-[#4ADE80]' : 'text-gray-500'}`}>
                    {m.radiant_name}
                  </span>
                  <span className="text-gray-600 text-sm">vs</span>
                  <span className={`w-40 ${!m.radiant_win ? 'text-[#F87171]' : 'text-gray-500'}`}>
                    {m.dire_name}
                  </span>
                </div>
                <div className="flex items-center gap-6 text-sm text-gray-500">
                  <span>{formatDuration(m.duration)}</span>
                  <span className="w-48 truncate">{m.league_name}</span>
                  <span>{new Date(m.date).toLocaleDateString()}</span>
                </div>
              </div>
            </div>
            
            {expanded === m.match_id && detail && (
              <div className="bg-gray-900/30 px-6 py-6 border-b border-gray-800">
                <div className="grid grid-cols-2 gap-8">
                  <div>
                    <h3 className="text-sm text-gray-400 mb-3">{detail.radiant_name} (Radiant)</h3>
                    <div className="space-y-2">
                      {detail.radiant_roster.map(p => (
                        <div key={p.account_id} className="flex justify-between text-sm">
                          <span className="text-gray-300">{p.name}</span>
                          <div className="flex gap-4 text-gray-500">
                            <span>{p.fantasy_role !== null ? roleLabels[p.fantasy_role] || 'Unknown' : 'Unknown'}</span>
                            <span>{Math.round(p.glicko_rating)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h3 className="text-sm text-gray-400 mb-3">{detail.dire_name} (Dire)</h3>
                    <div className="space-y-2">
                      {detail.dire_roster.map(p => (
                        <div key={p.account_id} className="flex justify-between text-sm">
                          <span className="text-gray-300">{p.name}</span>
                          <div className="flex gap-4 text-gray-500">
                            <span>{p.fantasy_role !== null ? roleLabels[p.fantasy_role] || 'Unknown' : 'Unknown'}</span>
                            <span>{Math.round(p.glicko_rating)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {total > 20 && (
        <div className="mt-6 flex gap-2 justify-center">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-1.5 bg-gray-800 text-sm disabled:opacity-30 hover:bg-gray-700"
          >
            Previous
          </button>
          <span className="px-4 py-1.5 text-sm text-gray-400">
            Page {page} of {Math.ceil(total / 20)}
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={page >= Math.ceil(total / 20)}
            className="px-4 py-1.5 bg-gray-800 text-sm disabled:opacity-30 hover:bg-gray-700"
          >
            Next
          </button>
        </div>
      )}
    </>
  );
}

export default function App() {
  const hash = useHash();

  return (
    <div className="min-h-screen bg-[#0F1218] text-gray-200 p-8">
      <div className="max-w-5xl mx-auto">
        <header className="mb-8">
          <h1 className="text-2xl tracking-tight text-white mb-6">Dota 2 Match Predictor</h1>
          <NavBar current={hash} />
        </header>

        <main>
          {hash === 'matches' ? <MatchHistoryView /> : <PredictView />}
        </main>
      </div>
    </div>
  );
}
