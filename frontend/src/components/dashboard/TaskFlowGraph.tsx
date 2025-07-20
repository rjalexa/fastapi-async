// frontend/src/components/dashboard/TaskFlowGraph.tsx
import React, { useCallback, useMemo } from 'react';
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

interface TaskFlowGraphProps {
  queueStatus: QueueStatus | null;
}

const TaskFlowGraph: React.FC<TaskFlowGraphProps> = ({ queueStatus }) => {
  // Define the initial nodes based on the task flow - shifted left to prevent truncation
  const initialNodes: Node[] = useMemo(() => [
    {
      id: 'submit',
      type: 'input',
      position: { x: 250, y: 50 },
      data: { 
        label: (
          <div className="text-center text-gray-800">
            <div className="font-semibold">Task Submit</div>
          </div>
        )
      },
      className: 'bg-blue-100 border-2 border-blue-600 rounded-lg p-2.5 min-w-[120px] text-center text-gray-900'
    },
    {
      id: 'primary-queue',
      position: { x: 250, y: 150 },
      data: { 
        label: (
          <div className="text-center text-gray-800">
            <div className="font-semibold">Primary Queue</div>
            <div className="text-lg font-bold">{queueStatus?.queues.primary || 0}</div>
          </div>
        )
      },
      className: 'bg-green-100 border-2 border-green-600 rounded-lg p-2.5 min-w-[120px] text-center text-gray-900'
    },
    {
      id: 'processing',
      position: { x: 350, y: 250 },
      data: { 
        label: (
          <div className="text-center text-gray-800">
            <div className="font-semibold">Active</div>
            <div className="text-lg font-bold">{queueStatus?.states.ACTIVE || 0}</div>
          </div>
        )
      },
      className: 'bg-green-100 border-2 border-green-600 rounded-lg p-2.5 min-w-[120px] text-center text-gray-900'
    },
    {
      id: 'completed',
      type: 'output',
      position: { x: 155, y: 350 },
      data: { 
        label: (
          <div className="text-center text-gray-800">
            <div className="font-semibold">Completed</div>
            <div className="text-lg font-bold">{queueStatus?.states.COMPLETED || 0}</div>
          </div>
        )
      },
      className: 'bg-green-100 border-2 border-green-600 rounded-lg p-2.5 min-w-[120px] text-center text-gray-900'
    },
    {
      id: 'failed',
      position: { x: 545, y: 350 },
      data: { 
        label: (
          <div className="text-center text-gray-800">
            <div className="font-semibold">Failed</div>
            <div className="text-lg font-bold">{queueStatus?.states.FAILED || 0}</div>
          </div>
        )
      },
      className: 'bg-yellow-100 border-2 border-yellow-600 rounded-lg p-2.5 min-w-[120px] text-center text-gray-900'
    },
    {
      id: 'scheduled-queue',
      position: { x: 465, y: 470 },
      data: { 
        label: (
          <div className="text-center text-gray-800">
            <div className="font-semibold">Scheduled Queue</div>
            <div className="text-lg font-bold">{queueStatus?.queues.scheduled || 0}</div>
          </div>
        )
      },
      className: 'bg-yellow-100 border-2 border-yellow-600 rounded-lg p-2.5 min-w-[120px] text-center text-gray-900'
    },
    {
      id: 'dlq',
      type: 'output',
      position: { x: 625, y: 470 },
      data: { 
        label: (
          <div className="text-center text-gray-800">
            <div className="font-semibold">Dead Letter Queue</div>
            <div className="text-lg font-bold">{queueStatus?.queues.dlq || 0}</div>
          </div>
        )
      },
      className: 'bg-red-100 border-2 border-red-600 rounded-lg p-2.5 min-w-[120px] text-center text-gray-900'
    },
    {
      id: 'retry-queue',
      position: { x: 350, y: 570 },
      data: { 
        label: (
          <div className="text-center text-gray-800">
            <div className="font-semibold">Retry Queue</div>
            <div className="text-lg font-bold">{queueStatus?.queues.retry || 0}</div>
          </div>
        )
      },
      className: 'bg-yellow-100 border-2 border-yellow-600 rounded-lg p-2.5 min-w-[120px] text-center text-gray-900'
    }
  ], [queueStatus]);

  // Define the edges (connections between nodes) - matching the exact layout from the image
  const initialEdges: Edge[] = useMemo(() => [
    {
      id: 'submit-primary',
      source: 'submit',
      target: 'primary-queue',
      animated: true,
      style: { stroke: '#1976d2', strokeWidth: 2, strokeDasharray: '5,5' }
    },
    {
      id: 'primary-processing',
      source: 'primary-queue',
      target: 'processing',
      animated: true,
      style: { stroke: '#16a34a', strokeWidth: 2 }
    },
    {
      id: 'processing-completed',
      source: 'processing',
      target: 'completed',
      animated: true,
      style: { stroke: '#16a34a', strokeWidth: 2, strokeDasharray: '5,5' }
    },
    {
      id: 'processing-failed',
      source: 'processing',
      target: 'failed',
      animated: true,
      style: { stroke: '#ca8a04', strokeWidth: 2 }
    },
    {
      id: 'failed-scheduled',
      source: 'failed',
      target: 'scheduled-queue',
      animated: true,
      style: { stroke: '#ca8a04', strokeWidth: 2, strokeDasharray: '5,5' }
    },
    {
      id: 'failed-dlq',
      source: 'failed',
      target: 'dlq',
      animated: true,
      style: { stroke: '#dc2626', strokeWidth: 2, strokeDasharray: '5,5' }
    },
    {
      id: 'scheduled-retry',
      source: 'scheduled-queue',
      target: 'retry-queue',
      animated: true,
      style: { stroke: '#ca8a04', strokeWidth: 2, strokeDasharray: '5,5' }
    },
    {
      id: 'retry-processing',
      source: 'retry-queue',
      target: 'processing',
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
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
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