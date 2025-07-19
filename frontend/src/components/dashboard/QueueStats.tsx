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
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Queue Depths</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-orange-50 rounded-lg p-4 border border-orange-200 text-center">
          <p className="text-sm font-medium text-gray-600">Primary</p>
          <p className="text-2xl font-bold text-gray-900">
            {queueStatus ? formatNumber(queueStatus.queues.primary) : '-'}
          </p>
        </div>

        <div className="bg-yellow-50 rounded-lg p-4 border border-yellow-200 text-center">
          <p className="text-sm font-medium text-gray-600">Retry</p>
          <p className="text-2xl font-bold text-gray-900">
            {queueStatus ? formatNumber(queueStatus.queues.retry) : '-'}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Ratio: {queueStatus ? `${(queueStatus.retry_ratio * 100).toFixed(1)}%` : '-'}
          </p>
        </div>

        <div className="bg-purple-50 rounded-lg p-4 border border-purple-200 text-center">
          <p className="text-sm font-medium text-gray-600">Scheduled</p>
          <p className="text-2xl font-bold text-gray-900">
            {queueStatus ? formatNumber(queueStatus.queues.scheduled) : '-'}
          </p>
        </div>

        <div className="bg-red-50 rounded-lg p-4 border border-red-200 text-center">
          <p className="text-sm font-medium text-gray-600">DLQ</p>
          <p className="text-2xl font-bold text-gray-900">
            {queueStatus ? formatNumber(queueStatus.queues.dlq) : '-'}
          </p>
        </div>
      </div>
    </div>
  );
};

export default QueueStats;
