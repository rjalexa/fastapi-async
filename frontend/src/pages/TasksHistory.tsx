import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { fetchTasks } from '@/lib/tasks-api';
import { TaskDetail, TaskListResponse, TaskState, QueueName } from '@/lib/types';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { format } from 'date-fns';

const TasksHistory: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [tasksResponse, setTasksResponse] = useState<TaskListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filters, setFilters] = useState({
    task_id: searchParams.get('task_id') || '',
    status: searchParams.get('status') || 'all',
    queue: (searchParams.get('queue') as QueueName) || '',
    page: parseInt(searchParams.get('page') || '1', 10),
  });

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filterParams: Record<string, unknown> = { ...filters, page_size: 10 };
      // Don't send status filter if "all" is selected
      if (filters.status === 'all' || filters.status === '') {
        filterParams.status = undefined;
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
      [TaskState.PENDING]: 'bg-yellow-400',
      [TaskState.ACTIVE]: 'bg-blue-500',
      [TaskState.COMPLETED]: 'bg-green-500',
      [TaskState.FAILED]: 'bg-red-500',
      [TaskState.SCHEDULED]: 'bg-purple-500',
      [TaskState.DLQ]: 'bg-gray-700',
    };
    return <Badge className={`${colorMap[state]} text-white`}>{state}</Badge>;
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
                <TableHead>Created At</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tasksResponse.tasks.map((task: TaskDetail) => (
                <TableRow key={task.task_id}>
                  <TableCell className="font-mono text-xs">{task.task_id}</TableCell>
                  <TableCell>{renderStateBadge(task.state)}</TableCell>
                  <TableCell>{format(new Date(task.created_at), 'PPpp')}</TableCell>
                  <TableCell>
                    {task.completed_at
                      ? `${(new Date(task.completed_at).getTime() - new Date(task.created_at).getTime()) / 1000}s`
                      : 'N/A'}
                  </TableCell>
                  <TableCell>
                    <Sheet>
                      <SheetTrigger asChild>
                        <Button variant="outline" size="sm">View Details</Button>
                      </SheetTrigger>
                      <SheetContent className="w-[600px] sm:w-[800px] max-w-[90vw] overflow-y-auto">
                        <SheetHeader>
                          <SheetTitle>Task Details: {task.task_id}</SheetTitle>
                        </SheetHeader>
                        <div className="py-4 space-y-4">
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
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Showing page {tasksResponse.page} of {tasksResponse.total_pages}
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
    </div>
  );
};

export default TasksHistory;
