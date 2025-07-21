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
import { nodeTypes } from './CustomNodes';

interface TaskFlowGraphProps {
  queueStatus: QueueStatus | null;
}

const TaskFlowGraph: React.FC<TaskFlowGraphProps> = ({ queueStatus }) => {
  const navigate = useNavigate();

  // Function to get filter parameters for navigation
  const getFilterParams = (nodeId: string): string => {
    switch (nodeId) {
      case 'completed':
        return 'status=COMPLETED';
      case 'failed':
        return 'status=FAILED';
      case 'processing':
        return 'status=ACTIVE';
      case 'primary-queue':
        return 'queue=primary';
      case 'scheduled-queue':
        return 'queue=scheduled';
      case 'retry-queue':
        return 'queue=retry';
      case 'dlq':
        return 'status=DLQ';
      default:
        return '';
    }
  };

  // Function to get node count for determining if clickable
  const getNodeCount = useCallback((nodeId: string): number => {
    if (!queueStatus) return 0;
    
    switch (nodeId) {
      case 'completed':
        return queueStatus.states.COMPLETED || 0;
      case 'failed':
        return queueStatus.states.FAILED || 0;
      case 'processing':
        return queueStatus.states.ACTIVE || 0;
      case 'primary-queue':
        return queueStatus.queues.primary || 0;
      case 'scheduled-queue':
        return queueStatus.queues.scheduled || 0;
      case 'retry-queue':
        return queueStatus.queues.retry || 0;
      case 'dlq':
        return queueStatus.queues.dlq || 0;
      default:
        return 0;
    }
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
  const initialNodes: Node[] = useMemo(() => [
    {
      id: 'submit',
      type: 'input',
      position: { x: 330, y: 50 },
      data: { 
        label: (
          <div className="text-center text-gray-800">
            <div className="font-semibold">Task Submit</div>
          </div>
        )
      },
      className: 'bg-blue-100 border-2 border-blue-600 rounded-lg p-3 w-[140px] h-[80px] flex flex-col justify-center text-center text-gray-900'
    },
    {
      id: 'primary-queue',
      type: 'primaryQueueNode',
      position: { x: 330, y: 150 },
      data: { 
        count: queueStatus?.queues.primary || 0
      }
    },
    {
      id: 'processing',
      type: 'activeNode',
      position: { x: 330, y: 250 },
      data: { 
        count: queueStatus?.states.ACTIVE || 0
      }
    },
    {
      id: 'completed',
      type: 'completedNode',
      position: { x: 100, y: 250 },
      data: { 
        count: queueStatus?.states.COMPLETED || 0
      }
    },
    {
      id: 'failed',
      type: 'failedNode',
      position: { x: 560, y: 250 },
      data: { 
        count: queueStatus?.states.FAILED || 0
      }
    },
    {
      id: 'dlq',
      type: 'deadLetterNode',
      position: { x: 790, y: 250 },
      data: { 
        count: queueStatus?.queues.dlq || 0
      }
    },
    {
      id: 'scheduled-queue',
      type: 'scheduledQueueNode',
      position: { x: 560, y: 400 },
      data: { 
        count: queueStatus?.queues.scheduled || 0
      }
    },
    {
      id: 'retry-queue',
      type: 'retryNode',
      position: { x: 330, y: 400 },
      data: { 
        count: queueStatus?.queues.retry || 0
      }
    }
  ], [queueStatus]);

  // Define the edges (connections between nodes) - updated with custom handles
  const initialEdges: Edge[] = useMemo(() => [
    {
      id: 'submit-primary',
      source: 'submit',
      target: 'primary-queue',
      targetHandle: 'top-target',
      animated: true,
      style: { stroke: '#1976d2', strokeWidth: 2, strokeDasharray: '5,5' }
    },
    {
      id: 'primary-processing',
      source: 'primary-queue',
      sourceHandle: 'bottom-source',
      target: 'processing',
      targetHandle: 'top-target',
      animated: true,
      style: { stroke: '#16a34a', strokeWidth: 2 }
    },
    {
      id: 'processing-completed',
      source: 'processing',
      sourceHandle: 'left-source',
      target: 'completed',
      targetHandle: 'right-target',
      animated: true,
      style: { stroke: '#16a34a', strokeWidth: 2 }
    },
    {
      id: 'processing-failed',
      source: 'processing',
      sourceHandle: 'right-source',
      target: 'failed',
      targetHandle: 'left-target',
      animated: true,
      style: { stroke: '#ca8a04', strokeWidth: 2 }
    },
    {
      id: 'failed-scheduled',
      source: 'failed',
      sourceHandle: 'bottom-source',
      target: 'scheduled-queue',
      targetHandle: 'top-target',
      animated: true,
      style: { stroke: '#ca8a04', strokeWidth: 2, strokeDasharray: '5,5' }
    },
    {
      id: 'failed-dlq',
      source: 'failed',
      sourceHandle: 'right-source',
      target: 'dlq',
      targetHandle: 'left-target',
      animated: true,
      style: { stroke: '#dc2626', strokeWidth: 2, strokeDasharray: '5,5' }
    },
    {
      id: 'scheduled-retry',
      source: 'scheduled-queue',
      sourceHandle: 'left-source',
      target: 'retry-queue',
      targetHandle: 'right-target',
      animated: true,
      style: { stroke: '#ca8a04', strokeWidth: 2, strokeDasharray: '5,5' }
    },
    {
      id: 'retry-processing',
      source: 'retry-queue',
      sourceHandle: 'top-source',
      target: 'processing',
      targetHandle: 'bottom-target',
      animated: true,
      style: { stroke: '#ca8a04', strokeWidth: 2, strokeDasharray: '5,5' }
    }
  ], []);

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
