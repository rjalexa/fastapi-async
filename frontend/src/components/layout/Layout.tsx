// frontend/src/components/layout/Layout.tsx
import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Activity, Clock, Trash2 } from 'lucide-react';

const Layout: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">AsyncTaskFlow</h1>
              <p className="text-sm text-gray-600">Real-time Task Processing Dashboard</p>
            </div>
          </div>
        </div>
      </header>

      <nav className="bg-white border-b">
        <div className="container mx-auto px-4">
          <div className="flex space-x-8">
            <NavLink
              to="/"
              className={({ isActive }) =>
                `flex items-center space-x-2 py-4 px-2 border-b-2 font-medium text-sm ${
                  isActive
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`
              }
            >
              <Activity className="w-4 h-4" />
              <span>Dashboard</span>
            </NavLink>

            <NavLink
              to="/tasks-history"
              className={({ isActive }) =>
                `flex items-center space-x-2 py-4 px-2 border-b-2 font-medium text-sm ${
                  isActive
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`
              }
            >
              <Clock className="w-4 h-4" />
              <span>Tasks History</span>
            </NavLink>

            <NavLink
              to="/tasks-cleanup"
              className={({ isActive }) =>
                `flex items-center space-x-2 py-4 px-2 border-b-2 font-medium text-sm ${
                  isActive
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`
              }
            >
              <Trash2 className="w-4 h-4" />
              <span>Tasks Cleanup</span>
            </NavLink>
          </div>
        </div>
      </nav>

      <main className="container mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
