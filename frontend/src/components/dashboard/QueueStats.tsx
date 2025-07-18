// frontend/src/components/dashboard/QueueStats.tsx
import React from 'react';
import { QueueStatus } from '../../lib/api';
import { 
  Clock, 
  CheckCircle, 
  XCircle, 
  RefreshCw, 
  AlertTriangle,
  Activity,
  Layers,
  Calendar
} from 'lucide-react';

interface QueueStatsProps {
  queueStatus: QueueStatus | null;
  isConnected: boolean;
}

const QueueStats: React.FC<QueueStatsProps> = ({ queueStatus, isConnected }) => {
  const formatNumber = (num: number) => {
    return num.toLocaleString();
  };

  const getStatusColor = (isConnected: boolean) => {
    return isConnected ? 'text-green-600' : 'text-red-600';
  };

  const getStatusBg = (isConnected: boolean) => {
    return isConnected ? 'bg-green-100' : 'bg-red-100';
  };

  return (
    <div className="space-y-6">
      {/* Connection Status */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">System Status</h3>
          <div className={`flex items-center space-x-2 px-3 py-1 rounded-full ${getStatusBg(isConnected)}`}>
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-600' : 'bg-red-600'}`}></div>
            <span className={`text-sm font-medium ${getStatusColor(isConnected)}`}>
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>

      {/* Queue Depths */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Queue Depths</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-orange-50 rounded-lg p-4 border border-orange-200">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-orange-100 rounded-lg">
                <Layers className="w-5 h-5 text-orange-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Primary</p>
                <p className="text-2xl font-bold text-gray-900">
                  {queueStatus ? formatNumber(queueStatus.queues.primary) : '-'}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-yellow-50 rounded-lg p-4 border border-yellow-200">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-yellow-100 rounded-lg">
                <RefreshCw className="w-5 h-5 text-yellow-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Retry</p>
                <p className="text-2xl font-bold text-gray-900">
                  {queueStatus ? formatNumber(queueStatus.queues.retry) : '-'}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-purple-50 rounded-lg p-4 border border-purple-200">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Calendar className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Scheduled</p>
                <p className="text-2xl font-bold text-gray-900">
                  {queueStatus ? formatNumber(queueStatus.queues.scheduled) : '-'}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-red-50 rounded-lg p-4 border border-red-200">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-red-100 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">DLQ</p>
                <p className="text-2xl font-bold text-gray-900">
                  {queueStatus ? formatNumber(queueStatus.queues.dlq) : '-'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Task States */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Task States</h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Clock className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Pending</p>
                <p className="text-2xl font-bold text-gray-900">
                  {queueStatus ? formatNumber(queueStatus.states.pending) : '-'}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-green-50 rounded-lg p-4 border border-green-200">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <Activity className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Processing</p>
                <p className="text-2xl font-bold text-gray-900">
                  {queueStatus ? formatNumber(queueStatus.states.processing) : '-'}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-emerald-50 rounded-lg p-4 border border-emerald-200">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-emerald-100 rounded-lg">
                <CheckCircle className="w-5 h-5 text-emerald-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Completed</p>
                <p className="text-2xl font-bold text-gray-900">
                  {queueStatus ? formatNumber(queueStatus.states.completed) : '-'}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-red-50 rounded-lg p-4 border border-red-200">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-red-100 rounded-lg">
                <XCircle className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Failed</p>
                <p className="text-2xl font-bold text-gray-900">
                  {queueStatus ? formatNumber(queueStatus.states.failed) : '-'}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-amber-50 rounded-lg p-4 border border-amber-200">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-amber-100 rounded-lg">
                <RefreshCw className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Retrying</p>
                <p className="text-2xl font-bold text-gray-900">
                  {queueStatus ? formatNumber(queueStatus.states.retrying) : '-'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Retry Ratio */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">System Metrics</h3>
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-600">Adaptive Retry Ratio</span>
            <span className="text-lg font-bold text-gray-900">
              {queueStatus ? `${(queueStatus.retry_ratio * 100).toFixed(1)}%` : '-'}
            </span>
          </div>
          <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${queueStatus ? queueStatus.retry_ratio * 100 : 0}%` }}
            ></div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default QueueStats;
