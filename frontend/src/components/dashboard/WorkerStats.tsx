// frontend/src/components/dashboard/WorkerStats.tsx
import React, { useState, useEffect, useRef } from 'react';
import { apiService, WorkerStatus, WorkerDetail } from '../../lib/api';

interface WorkerStatsProps {
  isConnected: boolean;
}

const WorkerStats: React.FC<WorkerStatsProps> = ({ isConnected }) => {
  const [workerStatus, setWorkerStatus] = useState<WorkerStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const initialLoadRef = useRef<boolean>(true);

  useEffect(() => {
    const fetchWorkerStats = async () => {
      if (!isConnected) {
        if (initialLoadRef.current) {
          setLoading(false);
        }
        return;
      }

      try {
        // Only show loading spinner on initial load, not on updates
        if (initialLoadRef.current) {
          setLoading(true);
        } else {
          setIsUpdating(true);
        }
        setError(null);
        
        const response = await apiService.getWorkerStatus();
        setWorkerStatus(response);
        
        if (initialLoadRef.current) {
          initialLoadRef.current = false;
        }
      } catch (err) {
        console.error('Failed to fetch worker stats:', err);
        setError('Failed to load worker statistics');
        setWorkerStatus(null);
      } finally {
        setLoading(false);
        setIsUpdating(false);
      }
    };

    fetchWorkerStats();
    
    // Refresh worker stats every 30 seconds if connected
    const interval = isConnected ? setInterval(fetchWorkerStats, 30000) : null;
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isConnected]);

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy':
        return 'bg-green-100 text-green-800';
      case 'stale':
        return 'bg-yellow-100 text-yellow-800';
      case 'no_heartbeat':
      case 'error':
      case 'unhealthy':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatLastHeartbeat = (worker: WorkerDetail) => {
    // Handle both timestamp (from broadcast) and last_heartbeat (from fallback)
    const heartbeat = worker.last_heartbeat || worker.timestamp;
    if (!heartbeat) return 'Never';
    try {
      // Try parsing as number first (Unix timestamp), then as ISO string
      const timestamp = isNaN(Number(heartbeat)) ? heartbeat : Number(heartbeat) * 1000;
      const date = new Date(timestamp);
      return date.toLocaleTimeString();
    } catch {
      return 'Unknown';
    }
  };


  const getCircuitBreakerColor = (state: string) => {
    switch (state.toLowerCase()) {
      case 'closed':
        return 'bg-green-100 text-green-800';
      case 'half-open':
        return 'bg-yellow-100 text-yellow-800';
      case 'open':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (!isConnected) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Worker Statistics
        </h3>
        <div className="text-center py-8">
          <div className="text-gray-500">
            <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 12h6m-6-4h6m2 5.291A7.962 7.962 0 0112 15c-2.34 0-4.47-.881-6.08-2.33" />
            </svg>
            <p className="text-sm">Connection required to display worker statistics</p>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Worker Statistics
        </h3>
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="text-sm text-gray-500 mt-2">Loading worker statistics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Worker Statistics
        </h3>
        <div className="text-center py-8">
          <div className="text-red-500">
            <svg className="mx-auto h-12 w-12 text-red-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          Worker Statistics
        </h3>
        {isUpdating && (
          <div className="flex items-center space-x-2 text-sm text-gray-500">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
            <span>Updating...</span>
          </div>
        )}
      </div>
      
      {/* Overall Status Summary */}
      {workerStatus && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {workerStatus.total_workers}
              </div>
              <div className="text-sm text-gray-500">Total Workers</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {workerStatus.healthy_workers}
              </div>
              <div className="text-sm text-gray-500">Healthy</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-600">
                {workerStatus.stale_workers}
              </div>
              <div className="text-sm text-gray-500">Stale</div>
            </div>
            <div className="text-center">
              <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                workerStatus.overall_status === 'healthy' 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-yellow-100 text-yellow-800'
              }`}>
                {workerStatus.overall_status}
              </span>
            </div>
          </div>
        </div>
      )}
      
      {!workerStatus || !workerStatus.worker_details || workerStatus.worker_details.length === 0 ? (
        <div className="text-center py-8">
          <div className="text-gray-500">
            <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            <p className="text-sm">No workers currently active</p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {workerStatus.worker_details.map((worker: WorkerDetail) => (
            <div key={worker.worker_id} className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-3">
                  <h4 className="font-medium text-gray-900 truncate">
                    {worker.worker_name || worker.worker_id}
                  </h4>
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(worker.status)}`}>
                    {worker.status}
                  </span>
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getCircuitBreakerColor(worker.circuit_breaker.state)}`}>
                    CB: {worker.circuit_breaker.state}
                  </span>
                </div>
                <div className="text-sm text-gray-500">
                  Last seen: {formatLastHeartbeat(worker)}
                </div>
              </div>
              
              {worker.error && (
                <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                  {worker.error}
                </div>
              )}
              
              <div className="grid grid-cols-2 gap-6 mt-3">
                <div className="text-center">
                  <div className="text-lg font-bold text-green-600">
                    {worker.circuit_breaker.success_count || 0}
                  </div>
                  <div className="text-sm text-gray-500">Success Count</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-bold text-red-600">
                    {worker.circuit_breaker.fail_count || 0}
                  </div>
                  <div className="text-sm text-gray-500">Fail Count</div>
                </div>
              </div>
              
              {worker.circuit_breaker.note && (
                <div className="mt-3 p-2 bg-blue-50 border border-blue-200 rounded text-sm text-blue-700">
                  <strong>Note:</strong> {worker.circuit_breaker.note}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default WorkerStats;
