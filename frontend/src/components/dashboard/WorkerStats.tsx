// frontend/src/components/dashboard/WorkerStats.tsx
import React, { useState, useEffect } from 'react';
import { WorkerStatus, apiService } from '../../lib/api';

interface WorkerStatsProps {
  isConnected: boolean;
}

const WorkerStats: React.FC<WorkerStatsProps> = () => {
  const [workerStatus, setWorkerStatus] = useState<WorkerStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchWorkerStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      const status = await apiService.getWorkerStatus();
      setWorkerStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch worker status');
      console.error('Failed to fetch worker status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkerStatus();
    
    // Refresh worker status every 30 seconds
    const interval = setInterval(fetchWorkerStatus, 30000);
    
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'bg-green-50 border-green-200 text-green-800';
      case 'stale':
        return 'bg-yellow-50 border-yellow-200 text-yellow-800';
      case 'no_heartbeat':
      case 'error':
        return 'bg-red-50 border-red-200 text-red-800';
      default:
        return 'bg-gray-50 border-gray-200 text-gray-800';
    }
  };

  const getCircuitBreakerColor = (state: string) => {
    switch (state) {
      case 'closed':
        return 'bg-green-100 text-green-800';
      case 'open':
        return 'bg-red-100 text-red-800';
      case 'half-open':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleTimeString();
  };

  const formatAge = (seconds: number) => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Worker Status</h3>
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-gray-600">Loading worker status...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Worker Status</h3>
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <svg className="h-5 w-5 text-red-400 mr-2" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <span className="text-red-800 font-medium">Error loading worker status</span>
          </div>
          <p className="text-red-700 text-sm mt-1">{error}</p>
          <button
            onClick={fetchWorkerStatus}
            className="mt-2 px-3 py-1 bg-red-100 hover:bg-red-200 text-red-800 text-sm rounded transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!workerStatus) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Worker Status</h3>
        <p className="text-gray-500">No worker status available</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Worker Status</h3>
        <button
          onClick={fetchWorkerStatus}
          className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
          disabled={loading}
        >
          Refresh
        </button>
      </div>

      {/* Overall Status */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-50 rounded-lg p-3 text-center">
          <p className="text-xs font-medium text-gray-600">Total Workers</p>
          <p className="text-lg font-bold text-gray-900">{workerStatus.total_workers}</p>
        </div>
        
        <div className="bg-green-50 rounded-lg p-3 text-center">
          <p className="text-xs font-medium text-gray-600">Healthy</p>
          <p className="text-lg font-bold text-gray-900">{workerStatus.healthy_workers}</p>
        </div>
        
        <div className="bg-yellow-50 rounded-lg p-3 text-center">
          <p className="text-xs font-medium text-gray-600">Stale</p>
          <p className="text-lg font-bold text-gray-900">{workerStatus.stale_workers}</p>
        </div>
        
        <div className={`rounded-lg p-3 text-center ${
          workerStatus.overall_status === 'healthy' 
            ? 'bg-green-50 border border-green-200' 
            : 'bg-yellow-50 border border-yellow-200'
        }`}>
          <p className="text-xs font-medium text-gray-600">Overall</p>
          <p className={`text-sm font-bold capitalize ${
            workerStatus.overall_status === 'healthy' ? 'text-green-800' : 'text-yellow-800'
          }`}>
            {workerStatus.overall_status}
          </p>
        </div>
      </div>

      {/* Circuit Breaker Summary */}
      <div className="mb-6">
        <h4 className="text-sm font-semibold text-gray-700 mb-2">Circuit Breaker States</h4>
        <div className="flex flex-wrap gap-2">
          {Object.entries(workerStatus.circuit_breaker_states).map(([state, count]) => (
            <span
              key={state}
              className={`px-2 py-1 rounded-full text-xs font-medium ${getCircuitBreakerColor(state)}`}
            >
              {state}: {count}
            </span>
          ))}
        </div>
      </div>

      {/* Worker Details */}
      <div>
        <h4 className="text-sm font-semibold text-gray-700 mb-3">Worker Details</h4>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {workerStatus.worker_details.map((worker) => (
            <div
              key={worker.worker_id}
              className={`rounded-lg p-3 border ${getStatusColor(worker.status)}`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-sm truncate" title={worker.worker_id}>
                  {worker.worker_id.split('-').slice(-2).join('-')}
                </span>
                <div className="flex items-center space-x-2">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${getCircuitBreakerColor(worker.circuit_breaker.state)}`}>
                    CB: {worker.circuit_breaker.state}
                  </span>
                  <span className="text-xs font-medium capitalize">
                    {worker.status}
                  </span>
                </div>
              </div>
              
              <div className="text-xs text-gray-600 space-y-1">
                {worker.last_heartbeat && (
                  <div className="flex justify-between">
                    <span>Last heartbeat:</span>
                    <span>{formatTimestamp(worker.last_heartbeat)}</span>
                  </div>
                )}
                {worker.heartbeat_age_seconds !== null && (
                  <div className="flex justify-between">
                    <span>Age:</span>
                    <span>{formatAge(worker.heartbeat_age_seconds)}</span>
                  </div>
                )}
                {worker.error && (
                  <div className="text-red-600 text-xs mt-1">
                    Error: {worker.error}
                  </div>
                )}
                {worker.circuit_breaker.note && (
                  <div className="text-gray-500 text-xs mt-1">
                    {worker.circuit_breaker.note}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Last Updated */}
      <div className="mt-4 pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-500">
          Last updated: {new Date(workerStatus.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
};

export default WorkerStats;
