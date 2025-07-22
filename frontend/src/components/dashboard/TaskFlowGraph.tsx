// frontend/src/components/dashboard/TaskFlowGraph.tsx
import React, { useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ReactFlow,
  Node,
  Edge,
  addEdge,
  Connection,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { QueueStatus } from '../../lib/api';
import { nodeTypes } from './nodeTypes';

interface TaskFlowGraphProps {
  queueStatus: QueueStatus | null;
}

const TaskFlowGraph: React.FC<TaskFlowGraphProps> = ({ queueStatus }) => {
  const navigate = useNavigate();

  // Function to get filter parameters for navigation
  const getFilterParams = (nodeId: string): string => {
    const filterMap: Record<string, string> = {
      completed: 'status=COMPLETED',
      failed: 'status=FAILED',
      active: 'status=ACTIVE',
      primaryQueue: 'queue=primary',
      scheduledQueue: 'queue=scheduled',
      retryQueue: 'queue=retry',
      deadLetter: 'status=DLQ',
    };
    return filterMap[nodeId] || '';
  };

  // Function to get node count for determining if clickable
  const getNodeCount = useCallback((nodeId: string): number => {
    if (!queueStatus) return 0;

    const countMap: Record<string, number> = {
      completed: queueStatus.states.COMPLETED || 0,
      failed: queueStatus.states.FAILED || 0,
      active: queueStatus.states.ACTIVE || 0,
      primaryQueue: queueStatus.queues.primary || 0,
      scheduledQueue: queueStatus.queues.scheduled || 0,
      retryQueue: queueStatus.queues.retry || 0,
      deadLetter: queueStatus.queues.dlq || 0,
    };
    return countMap[nodeId] || 0;
  }, [queueStatus]);

  // Handle node click for navigation
  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    const count = getNodeCount(node.id);
    if (count > 0) {
      const filterParams = getFilterParams(node.id);
      if (filterParams) {
        navigate(`/tasks-history?${filterParams}`);
      }
    }
  }, [navigate, getNodeCount]);

  // Define the initial nodes based on the task flow - updated layout with custom nodes
  const initialNodes: Node[] = useMemo(() => {
    const nodes: Node[] = [
      {
        id: 'submit',
        type: 'input',
        position: { x: 330, y: 50 },
        data: {
          label: (
            <div className="text-center text-gray-800">
              <div className="font-semibold">Task Submit</div>
            </div>
          ),
        },
        className: 'bg-blue-100 border-2 border-blue-600 rounded-lg p-3 w-[140px] h-[80px] flex flex-col justify-center text-center text-gray-900',
      },
      {
        id: 'primaryQueue',
        type: 'primaryQueue',
        position: { x: 330, y: 150 },
        data: {
          label: 'Primary',
          count: queueStatus?.queues.primary || 0,
        },
      },
      {
        id: 'active',
        type: 'active',
        position: { x: 330, y: 250 },
        data: {
          label: 'Active',
          count: queueStatus?.states.ACTIVE || 0,
        },
      },
      {
        id: 'completed',
        type: 'completed',
        position: { x: 100, y: 250 },
        data: {
          label: 'Completed',
          count: queueStatus?.states.COMPLETED || 0,
        },
      },
      {
        id: 'failed',
        type: 'failed',
        position: { x: 560, y: 250 },
        data: {
          label: 'Failed',
          count: queueStatus?.states.FAILED || 0,
        },
      },
      {
        id: 'deadLetter',
        type: 'deadLetter',
        position: { x: 790, y: 250 },
        data: {
          label: 'Dead Letter',
          count: queueStatus?.queues.dlq || 0,
        },
      },
      {
        id: 'scheduledQueue',
        type: 'scheduledQueue',
        position: { x: 560, y: 400 },
        data: {
          label: 'Scheduled',
          count: queueStatus?.queues.scheduled || 0,
        },
      },
      {
        id: 'retryQueue',
        type: 'retry',
        position: { x: 330, y: 400 },
        data: {
          label: 'Retry',
          count: queueStatus?.queues.retry || 0,
        },
      },
    ];
    return nodes;
  }, [queueStatus]);

  // Define the edges (connections between nodes) - updated with custom handles
  const initialEdges: Edge[] = useMemo(() => {
    const edges: Edge[] = [
      { id: 'submit-primary', source: 'submit', target: 'primaryQueue', targetHandle: 'top-target', animated: true, style: { stroke: '#1976d2', strokeWidth: 2, strokeDasharray: '5,5' } },
      { id: 'primary-active', source: 'primaryQueue', sourceHandle: 'bottom-source', target: 'active', targetHandle: 'top-target', animated: true, style: { stroke: '#16a34a', strokeWidth: 2 } },
      { id: 'active-completed', source: 'active', sourceHandle: 'left-source', target: 'completed', targetHandle: 'right-target', animated: true, style: { stroke: '#16a34a', strokeWidth: 2 } },
      { id: 'active-failed', source: 'active', sourceHandle: 'right-source', target: 'failed', targetHandle: 'left-target', animated: true, style: { stroke: '#ca8a04', strokeWidth: 2 } },
      { id: 'failed-scheduled', source: 'failed', sourceHandle: 'bottom-source', target: 'scheduledQueue', targetHandle: 'top-target', animated: true, style: { stroke: '#ca8a04', strokeWidth: 2, strokeDasharray: '5,5' } },
      { id: 'failed-deadLetter', source: 'failed', sourceHandle: 'right-source', target: 'deadLetter', targetHandle: 'left-target', animated: true, style: { stroke: '#dc2626', strokeWidth: 2, strokeDasharray: '5,5' } },
      { id: 'scheduled-retry', source: 'scheduledQueue', sourceHandle: 'left-source', target: 'retryQueue', targetHandle: 'right-target', animated: true, style: { stroke: '#ca8a04', strokeWidth: 2, strokeDasharray: '5,5' } },
      { id: 'retry-active', source: 'retryQueue', sourceHandle: 'top-source', target: 'active', targetHandle: 'bottom-target', animated: true, style: { stroke: '#ca8a04', strokeWidth: 2, strokeDasharray: '5,5' } },
    ];
    return edges;
  }, []);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  // Update nodes when queueStatus changes
  React.useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  return (
    <div className="h-96 w-full border border-gray-200 rounded-lg bg-white">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={handleNodeClick}
        fitView
        attributionPosition="bottom-left"
      >
        <Controls />
        <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
      </ReactFlow>
    </div>
  );
};

export default TaskFlowGraph;
