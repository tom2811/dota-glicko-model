import { useState, useEffect } from 'react';

type Match = {
  id: string;
  radiant_name: string;
  dire_name: string;
  radiant_account_ids: number[];
  dire_account_ids: number[];
};

export default function App() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/upcoming')
      .then(res => res.json())
      .then(data => setMatches(data.matches))
      .catch(err => setError("Failed to load upcoming matches"));
  }, []);

  async function handlePredict(match: Match) {
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
    <div className="min-h-screen bg-[#0F1218] text-gray-200 font-sans p-8">
      <div className="max-w-4xl mx-auto">
        <header className="mb-12 border-b border-gray-800 pb-4">
          <h1 className="text-3xl tracking-tight font-medium text-white mb-2">Dota 2 Predictor</h1>
          <p className="text-gray-400 text-sm">Glicko-based match forecasting</p>
        </header>

        <main>
          <div className="mb-8">
            <h2 className="text-sm font-medium text-gray-400 mb-4 uppercase tracking-wider">Upcoming Pro Matches</h2>
            
            {matches.length === 0 && !error && <p className="text-gray-500">Loading matches...</p>}
            
            <div className="grid gap-4">
              {matches.map(m => (
                <div key={m.id} className="border border-gray-800 bg-[#161A22] p-6 flex justify-between items-center hover:border-gray-600 transition-colors">
                  <div>
                    <div className="flex items-center gap-4 text-lg">
                      <span className="font-medium text-green-500">{m.radiant_name}</span>
                      <span className="text-gray-600 text-sm">vs</span>
                      <span className="font-medium text-red-500">{m.dire_name}</span>
                    </div>
                  </div>
                  <button 
                    onClick={() => handlePredict(m)}
                    disabled={loading}
                    className="bg-white text-black font-medium text-sm py-2 px-6 hover:bg-gray-200 transition-colors disabled:opacity-50"
                  >
                    Predict
                  </button>
                </div>
              ))}
            </div>
          </div>

          {error && (
            <div className="border border-red-900 bg-red-900/20 text-red-400 p-4 mb-8 text-sm">
              {error}
            </div>
          )}

          {result && (
            <div className="border border-gray-800 bg-[#161A22] p-8 text-center">
              <h2 className="text-xs font-medium text-gray-400 uppercase tracking-widest mb-2">Prediction Result</h2>
              <div className="text-3xl font-light text-white tracking-tight">{result}</div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
