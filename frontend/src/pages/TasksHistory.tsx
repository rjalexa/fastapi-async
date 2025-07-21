import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { fetchTaskSummaries, fetchTaskDetail, deleteTask } from '@/lib/tasks-api';
import { TaskSummary, TaskSummaryListResponse, TaskDetail, TaskState } from '@/lib/types';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { format } from 'date-fns';
import { ChevronDown, ChevronUp } from 'lucide-react';

const TasksHistory: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [tasksResponse, setTasksResponse] = useState<TaskSummaryListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [taskToDelete, setTaskToDelete] = useState<TaskSummary | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null);
  const [expandedTaskDetail, setExpandedTaskDetail] = useState<TaskDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

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
      const data = await fetchTaskSummaries(filterParams);
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

  const getTaskType = (task: TaskSummary): string => {
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

  const calculateDuration = (task: TaskSummary | TaskDetail): string => {
    if (task.completed_at) {
      const duration = (new Date(task.completed_at).getTime() - new Date(task.created_at).getTime()) / 1000;
      return `${duration}s`;
    }
    return 'N/A';
  };

  const handleDeleteClick = (task: TaskSummary) => {
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

  const toggleTaskDetails = async (taskId: string) => {
    if (expandedTaskId === taskId) {
      // Collapse
      setExpandedTaskId(null);
      setExpandedTaskDetail(null);
    } else {
      // Expand
      setExpandedTaskId(taskId);
      setLoadingDetail(true);
      try {
        const detail = await fetchTaskDetail(taskId);
        setExpandedTaskDetail(detail);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to fetch task details');
      } finally {
        setLoadingDetail(false);
      }
    }
  };

  const collapseTaskDetails = () => {
    setExpandedTaskId(null);
    setExpandedTaskDetail(null);
  };

  const renderTaskDetailsCard = (task: TaskSummary) => {
    if (expandedTaskId !== task.task_id) return null;

    return (
      <TableRow>
        <TableCell colSpan={5} className="p-0">
          <div className="bg-gray-50 border-t border-gray-200 p-6 space-y-6">
            {/* Header with Collapse Button */}
            <div className="flex justify-between items-center pb-4 border-b border-gray-200">
              <h4 className="font-semibold text-gray-700 text-lg">Task Details</h4>
              <Button 
                variant="outline" 
                size="sm"
                onClick={collapseTaskDetails}
                className="flex items-center space-x-1"
              >
                <ChevronUp className="h-4 w-4" />
                <span>Collapse</span>
              </Button>
            </div>

            {loadingDetail ? (
              <div className="text-center py-8">
                <p className="text-gray-500">Loading task details...</p>
              </div>
            ) : expandedTaskDetail ? (
              <>
                {/* Metadata Section */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pb-4 border-b border-gray-200">
                  <div>
                    <h5 className="font-semibold text-gray-700 mb-3">Timing Information</h5>
                    <div className="space-y-2 text-sm">
                      <div><span className="font-medium">Created:</span> {format(new Date(expandedTaskDetail.created_at), 'PPpp')}</div>
                      <div><span className="font-medium">Updated:</span> {format(new Date(expandedTaskDetail.updated_at), 'PPpp')}</div>
                      {expandedTaskDetail.completed_at && (
                        <div><span className="font-medium">Completed:</span> {format(new Date(expandedTaskDetail.completed_at), 'PPpp')}</div>
                      )}
                      <div><span className="font-medium">Duration:</span> {calculateDuration(expandedTaskDetail)}</div>
                    </div>
                  </div>
                  
                  <div>
                    <h5 className="font-semibold text-gray-700 mb-3">Retry Information</h5>
                    <div className="space-y-2 text-sm">
                      <div><span className="font-medium">Retry Count:</span> {expandedTaskDetail.retry_count} / {expandedTaskDetail.max_retries}</div>
                      {expandedTaskDetail.retry_after && (
                        <div><span className="font-medium">Retry After:</span> {format(new Date(expandedTaskDetail.retry_after), 'PPpp')}</div>
                      )}
                      {expandedTaskDetail.last_error && (
                        <div><span className="font-medium">Last Error:</span> <span className="text-red-600 text-xs">{expandedTaskDetail.last_error}</span></div>
                      )}
                      {expandedTaskDetail.error_type && (
                        <div><span className="font-medium">Error Type:</span> <span className="text-red-600 text-xs">{expandedTaskDetail.error_type}</span></div>
                      )}
                    </div>
                  </div>

                  <div>
                    <h5 className="font-semibold text-gray-700 mb-3">Content Information</h5>
                    <div className="space-y-2 text-sm">
                      <div><span className="font-medium">Content Length:</span> {expandedTaskDetail.content?.length || 0} characters</div>
                      <div><span className="font-medium">Has Result:</span> {expandedTaskDetail.result ? 'Yes' : 'No'}</div>
                      {expandedTaskDetail.result && (
                        <div><span className="font-medium">Result Length:</span> {expandedTaskDetail.result.length} characters</div>
                      )}
                    </div>
                  </div>
                </div>

                {/* State History */}
                <div>
                  <h5 className="font-semibold text-gray-700 mb-3">State Transition History</h5>
                  <div className="bg-white border border-gray-200 rounded-md p-4 max-h-48 overflow-y-auto">
                    <div className="space-y-2">
                      {expandedTaskDetail.state_history.map((entry, index) => (
                        <div key={index} className="flex items-center justify-between py-1 border-b border-gray-100 last:border-b-0">
                          <div className="flex items-center space-x-2">
                            {renderStateBadge(entry.state)}
                          </div>
                          <span className="text-sm text-gray-600">
                            {format(new Date(entry.timestamp), 'PPpp')}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Error History */}
                {expandedTaskDetail.error_history && expandedTaskDetail.error_history.length > 0 && (
                  <div>
                    <h5 className="font-semibold text-gray-700 mb-3">Error History</h5>
                    <div className="bg-white border border-gray-200 rounded-md p-4 max-h-48 overflow-y-auto">
                      <div className="space-y-3">
                        {expandedTaskDetail.error_history.map((error, index) => (
                          <div key={index} className="p-3 bg-red-50 border border-red-200 rounded-md">
                            <div className="text-sm">
                              <div className="font-medium text-red-800">Error #{index + 1}</div>
                              <pre className="text-xs text-red-700 mt-1 whitespace-pre-wrap">{JSON.stringify(error, null, 2)}</pre>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Result Section - Only for completed tasks */}
                {expandedTaskDetail.state === TaskState.COMPLETED && expandedTaskDetail.result && (
                  <div>
                    <h5 className="font-semibold text-gray-700 mb-3">Task Result</h5>
                    <div className="bg-white border border-gray-200 rounded-md p-4 max-h-64 overflow-y-auto">
                      <pre className="text-sm whitespace-pre-wrap text-gray-800">{expandedTaskDetail.result}</pre>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-8">
                <p className="text-red-500">Failed to load task details</p>
              </div>
            )}
          </div>
        </TableCell>
      </TableRow>
    );
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
              {tasksResponse.tasks.map((task: TaskSummary) => (
                <React.Fragment key={task.task_id}>
                  <TableRow className={expandedTaskId === task.task_id ? 'bg-blue-50' : ''}>
                    <TableCell className="font-mono text-xs">{task.task_id}</TableCell>
                    <TableCell>{renderStateBadge(task.state)}</TableCell>
                    <TableCell>{renderTaskTypeBadge(getTaskType(task))}</TableCell>
                    <TableCell>{format(new Date(task.created_at), 'PPpp')}</TableCell>
                    <TableCell>
                      <div className="flex space-x-2">
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => toggleTaskDetails(task.task_id)}
                          className="flex items-center space-x-1"
                        >
                          {expandedTaskId === task.task_id ? (
                            <>
                              <ChevronUp className="h-4 w-4" />
                              <span>Hide Details</span>
                            </>
                          ) : (
                            <>
                              <ChevronDown className="h-4 w-4" />
                              <span>View Details</span>
                            </>
                          )}
                        </Button>
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
                  {renderTaskDetailsCard(task)}
                </React.Fragment>
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
