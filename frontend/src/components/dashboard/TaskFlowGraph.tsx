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
  // Define the initial nodes based on the task flow
  const initialNodes: Node[] = useMemo(() => [
    {
      id: 'submit',
      type: 'input',
      position: { x: 50, y: 150 },
      data: { 
        label: (
          <div className="text-center">
            <div className="font-semibold">Task Submit</div>
          </div>
        )
      },
      style: {
        background: '#e3f2fd',
        border: '2px solid #1976d2',
        borderRadius: '8px',
        padding: '10px',
        minWidth: '120px',
        textAlign: 'center'
      }
    },
    {
      id: 'primary-queue',
      position: { x: 250, y: 150 },
      data: { 
        label: (
          <div className="text-center">
            <div className="font-semibold">Primary Queue</div>
            <div className="text-lg font-bold">{queueStatus?.queues.primary || 0}</div>
          </div>
        )
      },
      style: {
        background: queueStatus?.queues.primary ? '#fff3e0' : '#f5f5f5',
        border: `2px solid ${queueStatus?.queues.primary ? '#f57c00' : '#bdbdbd'}`,
        borderRadius: '8px',
        padding: '10px',
        minWidth: '120px',
        textAlign: 'center'
      }
    },
    {
      id: 'processing',
      position: { x: 450, y: 150 },
      data: { 
        label: (
          <div className="text-center">
            <div className="font-semibold">Processing</div>
            <div className="text-lg font-bold">{queueStatus?.states.processing || 0}</div>
          </div>
        )
      },
      style: {
        background: queueStatus?.states.processing ? '#e8f5e8' : '#f5f5f5',
        border: `2px solid ${queueStatus?.states.processing ? '#4caf50' : '#bdbdbd'}`,
        borderRadius: '8px',
        padding: '10px',
        minWidth: '120px',
        textAlign: 'center'
      }
    },
    {
      id: 'completed',
      type: 'output',
      position: { x: 650, y: 50 },
      data: { 
        label: (
          <div className="text-center">
            <div className="font-semibold">Completed</div>
            <div className="text-lg font-bold">{queueStatus?.states.completed || 0}</div>
          </div>
        )
      },
      style: {
        background: queueStatus?.states.completed ? '#e8f5e8' : '#f5f5f5',
        border: `2px solid ${queueStatus?.states.completed ? '#2e7d32' : '#bdbdbd'}`,
        borderRadius: '8px',
        padding: '10px',
        minWidth: '120px',
        textAlign: 'center'
      }
    },
    {
      id: 'failed',
      position: { x: 650, y: 250 },
      data: { 
        label: (
          <div className="text-center">
            <div className="font-semibold">Failed</div>
            <div className="text-lg font-bold">{queueStatus?.states.failed || 0}</div>
          </div>
        )
      },
      style: {
        background: queueStatus?.states.failed ? '#ffebee' : '#f5f5f5',
        border: `2px solid ${queueStatus?.states.failed ? '#d32f2f' : '#bdbdbd'}`,
        borderRadius: '8px',
        padding: '10px',
        minWidth: '120px',
        textAlign: 'center'
      }
    },
    {
      id: 'retry-queue',
      position: { x: 450, y: 350 },
      data: { 
        label: (
          <div className="text-center">
            <div className="font-semibold">Retry Queue</div>
            <div className="text-lg font-bold">{queueStatus?.queues.retry || 0}</div>
          </div>
        )
      },
      style: {
        background: queueStatus?.queues.retry ? '#fff8e1' : '#f5f5f5',
        border: `2px solid ${queueStatus?.queues.retry ? '#ffa000' : '#bdbdbd'}`,
        borderRadius: '8px',
        padding: '10px',
        minWidth: '120px',
        textAlign: 'center'
      }
    },
    {
      id: 'scheduled-queue',
      position: { x: 250, y: 350 },
      data: { 
        label: (
          <div className="text-center">
            <div className="font-semibold">Scheduled Queue</div>
            <div className="text-lg font-bold">{queueStatus?.queues.scheduled || 0}</div>
          </div>
        )
      },
      style: {
        background: queueStatus?.queues.scheduled ? '#f3e5f5' : '#f5f5f5',
        border: `2px solid ${queueStatus?.queues.scheduled ? '#7b1fa2' : '#bdbdbd'}`,
        borderRadius: '8px',
        padding: '10px',
        minWidth: '120px',
        textAlign: 'center'
      }
    },
    {
      id: 'dlq',
      type: 'output',
      position: { x: 650, y: 400 },
      data: { 
        label: (
          <div className="text-center">
            <div className="font-semibold">Dead Letter Queue</div>
            <div className="text-lg font-bold">{queueStatus?.queues.dlq || 0}</div>
          </div>
        )
      },
      style: {
        background: queueStatus?.queues.dlq ? '#ffebee' : '#f5f5f5',
        border: `2px solid ${queueStatus?.queues.dlq ? '#c62828' : '#bdbdbd'}`,
        borderRadius: '8px',
        padding: '10px',
        minWidth: '120px',
        textAlign: 'center'
      }
    }
  ], [queueStatus]);

  // Define the edges (connections between nodes)
  const initialEdges: Edge[] = useMemo(() => [
    {
      id: 'submit-primary',
      source: 'submit',
      target: 'primary-queue',
      animated: true,
      style: { stroke: '#1976d2', strokeWidth: 2 }
    },
    {
      id: 'primary-processing',
      source: 'primary-queue',
      target: 'processing',
      animated: true,
      style: { stroke: '#f57c00', strokeWidth: 2 }
    },
    {
      id: 'processing-completed',
      source: 'processing',
      target: 'completed',
      animated: true,
      style: { stroke: '#4caf50', strokeWidth: 2 }
    },
    {
      id: 'processing-failed',
      source: 'processing',
      target: 'failed',
      animated: true,
      style: { stroke: '#d32f2f', strokeWidth: 2 }
    },
    {
      id: 'failed-retry',
      source: 'failed',
      target: 'retry-queue',
      animated: true,
      style: { stroke: '#ffa000', strokeWidth: 2 }
    },
    {
      id: 'retry-scheduled',
      source: 'retry-queue',
      target: 'scheduled-queue',
      animated: true,
      style: { stroke: '#7b1fa2', strokeWidth: 2 }
    },
    {
      id: 'scheduled-primary',
      source: 'scheduled-queue',
      target: 'primary-queue',
      animated: true,
      style: { stroke: '#7b1fa2', strokeWidth: 2 }
    },
    {
      id: 'failed-dlq',
      source: 'failed',
      target: 'dlq',
      animated: true,
      style: { stroke: '#c62828', strokeWidth: 2 }
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
