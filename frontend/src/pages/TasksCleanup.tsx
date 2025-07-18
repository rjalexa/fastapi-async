// frontend/src/pages/TasksCleanup.tsx
import React from 'react';
import { Trash2, AlertTriangle, Database } from 'lucide-react';

const TasksCleanup: React.FC = () => {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tasks Cleanup</h1>
          <p className="text-sm text-gray-600">
            Manage and clean up old task data and failed tasks
          </p>
        </div>
      </div>

      {/* Placeholder Content */}
      <div className="bg-white rounded-lg shadow p-8">
        <div className="text-center">
          <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-gray-100">
            <Trash2 className="h-6 w-6 text-gray-400" />
          </div>
          <h3 className="mt-4 text-lg font-medium text-gray-900">Tasks Cleanup</h3>
          <p className="mt-2 text-sm text-gray-500 max-w-sm mx-auto">
            This page will provide tools for cleaning up old task data, 
            managing the dead letter queue, and maintaining system performance.
          </p>
          
          {/* Feature Preview */}
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mx-auto">
            <div className="bg-gray-50 rounded-lg p-4">
              <Database className="h-5 w-5 text-gray-400 mx-auto mb-2" />
              <h4 className="text-sm font-medium text-gray-900">Data Cleanup</h4>
              <p className="text-xs text-gray-500 mt-1">
                Remove old completed tasks and optimize storage
              </p>
            </div>
            
            <div className="bg-gray-50 rounded-lg p-4">
              <AlertTriangle className="h-5 w-5 text-gray-400 mx-auto mb-2" />
              <h4 className="text-sm font-medium text-gray-900">DLQ Management</h4>
              <p className="text-xs text-gray-500 mt-1">
                Review and manage tasks in the dead letter queue
              </p>
            </div>
            
            <div className="bg-gray-50 rounded-lg p-4">
              <Trash2 className="h-5 w-5 text-gray-400 mx-auto mb-2" />
              <h4 className="text-sm font-medium text-gray-900">Bulk Operations</h4>
              <p className="text-xs text-gray-500 mt-1">
                Perform bulk cleanup operations with safety checks
              </p>
            </div>
          </div>
          
          <div className="mt-6">
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
              Coming Soon
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TasksCleanup;
