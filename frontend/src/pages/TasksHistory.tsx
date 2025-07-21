import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { fetchTasks, deleteTask } from '@/lib/tasks-api';
import { TaskDetail, TaskListResponse, TaskState } from '@/lib/types';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { format } from 'date-fns';

const TasksHistory: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [tasksResponse, setTasksResponse] = useState<TaskListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [taskToDelete, setTaskToDelete] = useState<TaskDetail | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [filters, setFilters] = useState({
    task_id: searchParams.get('task_id') || '',
    status: searchParams.get('status') || 'all',
    task_type: searchParams.get('task_type') || 'all',
    page: parseInt(searchParams.get('page') || '1', 10),
  });

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filterParams: Record<string, unknown> = { 
        ...filters, 
        page_size: 10,
        sort_by: 'created_at',
        sort_order: 'desc'
      };
      // Don't send status filter if "all" is selected
      if (filters.status === 'all' || filters.status === '') {
        filterParams.status = undefined;
      }
      // Don't send task_type filter if "all" is selected
      if (filters.task_type === 'all' || filters.task_type === '') {
        filterParams.task_type = undefined;
      }
      // Only send task_id if it has at least 1 character
      if (filters.task_id && filters.task_id.trim().length > 0) {
        filterParams.task_id = filters.task_id.trim();
      } else {
        filterParams.task_id = undefined;
      }
      const data = await fetchTasks(filterParams);
      setTasksResponse(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    loadTasks();
    setSearchParams(
      Object.fromEntries(
        Object.entries(filters).map(([key, value]) => [key, String(value)])
      )
    );
  }, [loadTasks, filters, setSearchParams]);

  const handleFilterChange = (key: string, value: string | number) => {
    setFilters((prev) => ({ ...prev, [key]: value, page: 1 }));
  };

  const handlePageChange = (newPage: number) => {
    setFilters((prev) => ({ ...prev, page: newPage }));
  };

  // Check if pagination should be shown
  const shouldShowPagination = useMemo(() => {
    return tasksResponse && tasksResponse.total_pages > 1;
  }, [tasksResponse]);

  const renderStateBadge = (state: TaskState) => {
    const colorMap: { [key in TaskState]: string } = {
      [TaskState.PENDING]: 'bg-yellow-500 border-yellow-600',
      [TaskState.ACTIVE]: 'bg-green-500 border-green-600',
      [TaskState.COMPLETED]: 'bg-green-500 border-green-600',
      [TaskState.FAILED]: 'bg-yellow-500 border-yellow-600',
      [TaskState.SCHEDULED]: 'bg-yellow-500 border-yellow-600',
      [TaskState.DLQ]: 'bg-red-500 border-red-600',
    };
    return <Badge className={`${colorMap[state]} text-white border`}>{state}</Badge>;
  };

  const getTaskType = (task: TaskDetail): string => {
    // Return the task_type from the backend, which should handle the fallback logic
    return task.task_type || 'summarize';
  };

  const renderTaskTypeBadge = (taskType: string) => {
    const colorMap: { [key: string]: string } = {
      'summarize': 'bg-blue-500 border-blue-600',
      'pdfxtract': 'bg-purple-500 border-purple-600',
    };
    return <Badge className={`${colorMap[taskType] || 'bg-gray-500 border-gray-600'} text-white border`}>{taskType}</Badge>;
  };

  const calculateDuration = (task: TaskDetail): string => {
    if (task.completed_at) {
      const duration = (new Date(task.completed_at).getTime() - new Date(task.created_at).getTime()) / 1000;
      return `${duration}s`;
    }
    return 'N/A';
  };

  const handleDeleteClick = (task: TaskDetail) => {
    setTaskToDelete(task);
    setDeleteModalOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!taskToDelete) return;

    setDeleting(true);
    try {
      await deleteTask(taskToDelete.task_id);
      setDeleteModalOpen(false);
      setTaskToDelete(null);
      // Reload tasks to reflect the deletion
      await loadTasks();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete task');
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteModalOpen(false);
    setTaskToDelete(null);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Tasks History</h1>
      <div className="flex items-center space-x-4">
        <Input
          placeholder="Search by Task ID..."
          value={filters.task_id}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleFilterChange('task_id', e.target.value)}
          className="max-w-sm"
        />
        <Select
          value={filters.status}
          onValueChange={(value: string) => handleFilterChange('status', value)}
        >
          <SelectTrigger className="w-[180px] bg-white border border-gray-300">
            <SelectValue placeholder="Filter by Status" />
          </SelectTrigger>
          <SelectContent className="bg-white border border-gray-300 shadow-lg">
            <SelectItem value="all">All Statuses</SelectItem>
            {Object.values(TaskState).map((state) => (
              <SelectItem key={state} value={state}>
                {state}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={filters.task_type}
          onValueChange={(value: string) => handleFilterChange('task_type', value)}
        >
          <SelectTrigger className="w-[180px] bg-white border border-gray-300">
            <SelectValue placeholder="Filter by Type" />
          </SelectTrigger>
          <SelectContent className="bg-white border border-gray-300 shadow-lg">
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="summarize">Summarize</SelectItem>
            <SelectItem value="pdfxtract">PDF Extract</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading && <p>Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}

      {tasksResponse && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Task ID</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Task Type</TableHead>
                <TableHead>Created At</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tasksResponse.tasks.map((task: TaskDetail) => (
                <TableRow key={task.task_id}>
                  <TableCell className="font-mono text-xs">{task.task_id}</TableCell>
                  <TableCell>{renderStateBadge(task.state)}</TableCell>
                  <TableCell>{renderTaskTypeBadge(getTaskType(task))}</TableCell>
                  <TableCell>{format(new Date(task.created_at), 'PPpp')}</TableCell>
                  <TableCell>
                    <div className="flex space-x-2">
                      <Sheet>
                        <SheetTrigger asChild>
                          <Button variant="outline" size="sm">View Details</Button>
                        </SheetTrigger>
                        <SheetContent className="w-[600px] sm:w-[800px] max-w-[90vw] overflow-y-auto">
                          <SheetHeader>
                            <SheetTitle>Task Details: {task.task_id}</SheetTitle>
                          </SheetHeader>
                          <div className="py-4 space-y-4">
                            <div><strong>Task Type:</strong> {renderTaskTypeBadge(getTaskType(task))}</div>
                            <div><strong>Duration:</strong> {calculateDuration(task)}</div>
                            <div><strong>Content:</strong><pre className="prose bg-gray-100 p-2 rounded-md whitespace-pre-wrap">{task.content}</pre></div>
                            <div><strong>Result:</strong><pre className="prose bg-gray-100 p-2 rounded-md whitespace-pre-wrap">{task.result || 'N/A'}</pre></div>
                            <h3 className="font-bold mt-4">State History</h3>
                            <Table>
                              <TableHeader>
                                <TableRow>
                                  <TableHead>State</TableHead>
                                  <TableHead>Timestamp</TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {task.state_history.map((entry, index) => (
                                  <TableRow key={index}>
                                    <TableCell>{renderStateBadge(entry.state)}</TableCell>
                                    <TableCell>{format(new Date(entry.timestamp), 'PPpp')}</TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </div>
                        </SheetContent>
                      </Sheet>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={() => handleDeleteClick(task)}
                        className="text-red-600 hover:text-red-700 hover:bg-red-50 border-red-300 hover:border-red-400"
                      >
                        Delete
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              {(() => {
                const totalTasks = tasksResponse.total_items;
                const actualTasksOnPage = tasksResponse.tasks.length;
                const currentPage = tasksResponse.page;
                const pageSize = tasksResponse.page_size;
                
                if (totalTasks === 0) {
                  return "No tasks found";
                }
                
                // Calculate the actual start position for this page
                // The backend handles pagination correctly, so we can trust the page info
                const startLine = ((currentPage - 1) * pageSize) + 1;
                const endLine = startLine + actualTasksOnPage - 1;
                
                if (actualTasksOnPage === 1) {
                  return `Showing task ${startLine} of ${totalTasks}`;
                }
                
                return `Showing tasks ${startLine}-${endLine} of ${totalTasks}`;
              })()}
            </p>
            {shouldShowPagination && (
              <div className="flex items-center space-x-2">
                <Button
                  onClick={() => handlePageChange(filters.page - 1)}
                  disabled={filters.page <= 1}
                >
                  Previous
                </Button>
                <Button
                  onClick={() => handlePageChange(filters.page + 1)}
                  disabled={filters.page >= tasksResponse.total_pages}
                >
                  Next
                </Button>
              </div>
            )}
          </div>
        </>
      )}

      {/* Delete Confirmation Modal */}
      <Dialog open={deleteModalOpen} onOpenChange={setDeleteModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Task</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete task <span className="font-mono text-sm">{taskToDelete?.task_id}</span>?
              <br />
              <br />
              This will permanently remove the task from all Redis queues, states, and statistics. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={handleDeleteCancel}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button 
              onClick={handleDeleteConfirm}
              disabled={deleting}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {deleting ? 'Deleting...' : 'Delete Task'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default TasksHistory;
