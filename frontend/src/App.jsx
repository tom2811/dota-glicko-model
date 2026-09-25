export default function App() {
  return (
    <div className="min-h-screen bg-[#0F1218] text-gray-200 font-sans p-8">
      <div className="max-w-4xl mx-auto">
        <header className="mb-12">
          <h1 className="text-3xl tracking-tight font-medium text-white mb-2">Dota 2 Predictor</h1>
          <p className="text-gray-400 text-sm">Glicko-based match forecasting</p>
        </header>

        <main>
          <div className="border border-gray-800 bg-[#161A22] rounded p-6">
            <h2 className="text-sm font-medium text-gray-400 mb-4 uppercase tracking-wider">Upcoming Matches</h2>
            <div className="text-center py-12 text-gray-500">
              <p>Prediction interface coming soon...</p>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
