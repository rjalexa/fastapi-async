// frontend/src/pages/Dashboard.tsx
import React, { useState, useEffect } from 'react';
import { QueueStatus, SSEMessage, apiService } from '../lib/api';
import TaskFlowGraph from '../components/dashboard/TaskFlowGraph';
import QueueStats from '../components/dashboard/QueueStats';
import WorkerStats from '../components/dashboard/WorkerStats';

const Dashboard: React.FC = () => {
  const [queueStatus, setQueueStatus] = useState<QueueStatus | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  useEffect(() => {
    let eventSource: EventSource | null = null;

    const connectSSE = () => {
      try {
        eventSource = apiService.createSSEConnection(
          (data: SSEMessage) => {
            setLastUpdate(new Date());
            
            switch (data.type) {
              case 'initial_status':
                if (data.queue_depths && data.state_counts && data.retry_ratio !== undefined) {
                  setQueueStatus({
                    queues: data.queue_depths,
                    states: data.state_counts,
                    retry_ratio: data.retry_ratio
                  });
                }
                setIsConnected(true);
                break;
                
              case 'queue_update':
                if (data.queue_depths && data.state_counts && data.retry_ratio !== undefined) {
                  setQueueStatus({
                    queues: data.queue_depths,
                    states: data.state_counts,
                    retry_ratio: data.retry_ratio
                  });
                }
                setIsConnected(true);
                break;
                
              case 'heartbeat':
                setLastUpdate(new Date());
                setIsConnected(true);
                break;
                
              case 'error':
                console.error('SSE Error:', data.message);
                break;
                
              case 'fatal_error':
                console.error('SSE Fatal Error:', data.message);
                setIsConnected(false);
                break;
            }
          },
          (error) => {
            console.error('SSE Connection Error:', error);
            setIsConnected(false);
            
            // Attempt to reconnect after 5 seconds
            setTimeout(() => {
              if (eventSource?.readyState === EventSource.CLOSED) {
                connectSSE();
              }
            }, 5000);
          }
        );

        // Handle connection open
        eventSource.onopen = () => {
          setIsConnected(true);
        };

      } catch (error) {
        console.error('Failed to establish SSE connection:', error);
        setIsConnected(false);
      }
    };

    // Initial connection
    connectSSE();

    // Cleanup on unmount
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, []);

  const getConnectionStatus = () => {
    if (isConnected) return { text: 'Connected', color: 'bg-green-500' };
    if (lastUpdate) return { text: 'Trying...', color: 'bg-yellow-500' };
    return { text: 'Disconnected', color: 'bg-red-500' };
  };

  const connectionStatus = getConnectionStatus();

  return (
    <div className="space-y-6">
      {/* Header with compact status pill */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <div className="flex items-center space-x-2 px-3 py-1 rounded-full bg-gray-100">
            <div className={`w-2 h-2 rounded-full ${connectionStatus.color}`}></div>
            <span className="text-sm font-medium text-gray-700">
              {connectionStatus.text}
            </span>
          </div>
        </div>
        {lastUpdate && (
          <div className="text-right">
            <p className="text-xs text-gray-500">Last updated</p>
            <p className="text-sm font-medium text-gray-700">
              {lastUpdate.toLocaleTimeString()}
            </p>
          </div>
        )}
      </div>

      {/* Task Flow Graph - moved to top */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Task State Flow Overview
        </h3>
        <TaskFlowGraph queueStatus={queueStatus} />
      </div>

      {/* Queue Stats - moved below */}
      <QueueStats queueStatus={queueStatus} isConnected={isConnected} />

      {/* Worker Stats */}
      <WorkerStats isConnected={isConnected} />

      {/* Connection status warning */}
      {!isConnected && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-yellow-800">
                Connection Lost
              </h3>
              <div className="mt-2 text-sm text-yellow-700">
                <p>
                  Real-time updates are currently unavailable. The system will attempt to reconnect automatically.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
