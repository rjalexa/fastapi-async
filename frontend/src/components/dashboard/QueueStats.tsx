// frontend/src/components/dashboard/QueueStats.tsx
import React from 'react';
import { QueueStatus } from '../../lib/api';

interface QueueStatsProps {
  queueStatus: QueueStatus | null;
  isConnected: boolean;
}

const QueueStats: React.FC<QueueStatsProps> = ({ queueStatus }) => {
  const formatNumber = (num: number) => {
    return num.toLocaleString();
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Queue Depths */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-3">Queue Depths</h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-orange-50 rounded-lg p-3 border border-orange-200 text-center">
            <p className="text-xs font-medium text-gray-600">Primary</p>
            <p className="text-lg font-bold text-gray-900">
              {queueStatus ? formatNumber(queueStatus.queues.primary) : '-'}
            </p>
          </div>

          <div className="bg-yellow-50 rounded-lg p-3 border border-yellow-200 text-center">
            <p className="text-xs font-medium text-gray-600">Retry</p>
            <p className="text-lg font-bold text-gray-900">
              {queueStatus ? formatNumber(queueStatus.queues.retry) : '-'}
            </p>
          </div>

          <div className="bg-purple-50 rounded-lg p-3 border border-purple-200 text-center">
            <p className="text-xs font-medium text-gray-600">Scheduled</p>
            <p className="text-lg font-bold text-gray-900">
              {queueStatus ? formatNumber(queueStatus.queues.scheduled) : '-'}
            </p>
          </div>

          <div className="bg-red-50 rounded-lg p-3 border border-red-200 text-center">
            <p className="text-xs font-medium text-gray-600">DLQ</p>
            <p className="text-lg font-bold text-gray-900">
              {queueStatus ? formatNumber(queueStatus.queues.dlq) : '-'}
            </p>
          </div>
        </div>
      </div>

      {/* Task States */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-3">Task States</h3>
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-blue-50 rounded-lg p-2 border border-blue-200 text-center">
            <p className="text-xs font-medium text-gray-600">Pending</p>
            <p className="text-sm font-bold text-gray-900">
              {queueStatus ? formatNumber(queueStatus.states.PENDING) : '-'}
            </p>
          </div>

          <div className="bg-green-50 rounded-lg p-2 border border-green-200 text-center">
            <p className="text-xs font-medium text-gray-600">Active</p>
            <p className="text-sm font-bold text-gray-900">
              {queueStatus ? formatNumber(queueStatus.states.ACTIVE) : '-'}
            </p>
          </div>

          <div className="bg-emerald-50 rounded-lg p-2 border border-emerald-200 text-center">
            <p className="text-xs font-medium text-gray-600">Completed</p>
            <p className="text-sm font-bold text-gray-900">
              {queueStatus ? formatNumber(queueStatus.states.COMPLETED) : '-'}
            </p>
          </div>

          <div className="bg-red-50 rounded-lg p-2 border border-red-200 text-center">
            <p className="text-xs font-medium text-gray-600">Failed</p>
            <p className="text-sm font-bold text-gray-900">
              {queueStatus ? formatNumber(queueStatus.states.FAILED) : '-'}
            </p>
          </div>

          <div className="bg-amber-50 rounded-lg p-2 border border-amber-200 text-center">
            <p className="text-xs font-medium text-gray-600">Scheduled</p>
            <p className="text-sm font-bold text-gray-900">
              {queueStatus ? formatNumber(queueStatus.states.SCHEDULED) : '-'}
            </p>
          </div>

          <div className="bg-purple-50 rounded-lg p-2 border border-purple-200 text-center">
            <p className="text-xs font-medium text-gray-600">DLQ</p>
            <p className="text-sm font-bold text-gray-900">
              {queueStatus ? formatNumber(queueStatus.states.DLQ) : '-'}
            </p>
          </div>

          <div className="bg-gray-50 rounded-lg p-2 border border-gray-200 text-center">
            <p className="text-xs font-medium text-gray-600">Retry Ratio</p>
            <p className="text-sm font-bold text-gray-900">
              {queueStatus ? `${(queueStatus.retry_ratio * 100).toFixed(1)}%` : '-'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default QueueStats;
