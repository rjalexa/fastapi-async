// frontend/src/App.tsx
import { useState } from 'react'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <header className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            AsyncTaskFlow
          </h1>
          <p className="text-lg text-gray-600">
            Production-ready distributed task processing system
          </p>
        </header>

        <main className="max-w-4xl mx-auto">
          <div className="bg-white rounded-lg shadow-md p-6 mb-6">
            <h2 className="text-2xl font-semibold mb-4">Welcome to AsyncTaskFlow</h2>
            <p className="text-gray-700 mb-4">
              This is a placeholder frontend for the AsyncTaskFlow system. 
              The complete implementation will include:
            </p>
            <ul className="list-disc list-inside text-gray-700 space-y-2">
              <li>Task submission and monitoring interface</li>
              <li>Queue status dashboard</li>
              <li>Real-time task progress tracking</li>
              <li>Dead letter queue management</li>
              <li>System health monitoring</li>
            </ul>
          </div>

          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-xl font-semibold mb-4">Quick Test</h3>
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setCount((count) => count + 1)}
                className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
              >
                Count: {count}
              </button>
              <p className="text-gray-600">
                Click to test React functionality
              </p>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

export default App
