// frontend/src/pages/TasksHistory.tsx
import React from 'react';
import { Clock, Search, Filter } from 'lucide-react';

const TasksHistory: React.FC = () => {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tasks History</h1>
          <p className="text-sm text-gray-600">
            View and analyze historical task execution data
          </p>
        </div>
      </div>

      {/* Placeholder Content */}
      <div className="bg-white rounded-lg shadow p-8">
        <div className="text-center">
          <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-gray-100">
            <Clock className="h-6 w-6 text-gray-400" />
          </div>
          <h3 className="mt-4 text-lg font-medium text-gray-900">Tasks History</h3>
          <p className="mt-2 text-sm text-gray-500 max-w-sm mx-auto">
            This page will display historical task data including execution times, 
            success rates, and detailed task logs for analysis and debugging.
          </p>
          
          {/* Feature Preview */}
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mx-auto">
            <div className="bg-gray-50 rounded-lg p-4">
              <Search className="h-5 w-5 text-gray-400 mx-auto mb-2" />
              <h4 className="text-sm font-medium text-gray-900">Search & Filter</h4>
              <p className="text-xs text-gray-500 mt-1">
                Find tasks by ID, status, date range, or error type
              </p>
            </div>
            
            <div className="bg-gray-50 rounded-lg p-4">
              <Filter className="h-5 w-5 text-gray-400 mx-auto mb-2" />
              <h4 className="text-sm font-medium text-gray-900">Advanced Filtering</h4>
              <p className="text-xs text-gray-500 mt-1">
                Filter by execution time, retry count, or worker node
              </p>
            </div>
            
            <div className="bg-gray-50 rounded-lg p-4">
              <Clock className="h-5 w-5 text-gray-400 mx-auto mb-2" />
              <h4 className="text-sm font-medium text-gray-900">Timeline View</h4>
              <p className="text-xs text-gray-500 mt-1">
                Visualize task execution patterns over time
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

export default TasksHistory;
