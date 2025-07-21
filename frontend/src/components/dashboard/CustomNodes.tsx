// frontend/src/components/dashboard/CustomNodes.tsx
import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';

// Define a more specific type for the node data, compatible with React Flow
interface StatusNodeData {
  count: number;
  label: string;
}

// Define the props for a handle, which remains unchanged
interface HandleProps {
  type: 'source' | 'target';
  position: Position;
  id: string;
  style?: React.CSSProperties;
}

// Props for the generic StatusNode component, correctly typed
interface StatusNodeProps {
  data: StatusNodeData;
  handles: HandleProps[];
  className: string;
}

// Generic Status Node component to reduce duplication
const StatusNode: React.FC<StatusNodeProps> = ({ data, handles, className }) => {
  return (
    <div className={`rounded-lg p-3 w-[140px] h-[80px] flex flex-col justify-center text-center text-gray-900 transition-colors cursor-pointer ${className}`}>
      {handles.map((handle) => (
        <Handle
          key={handle.id}
          type={handle.type}
          position={handle.position}
          id={handle.id}
          style={{
            width: 8,
            height: 8,
            border: '2px solid #fff',
            ...handle.style,
          }}
        />
      ))}
      <div className="text-center text-gray-800">
        <div className="font-semibold">{data.label}</div>
        <div className="text-lg font-bold">{data.count || 0}</div>
      </div>
    </div>
  );
};

// Define handle styles for different node types
const successHandleStyle = { background: '#16a34a' };
const warningHandleStyle = { background: '#ca8a04' };
const errorHandleStyle = { background: '#dc2626' };

// Specific node components using the generic StatusNode, with corrected props
export const ActiveNode: React.FC<NodeProps> = ({ data }) => (
  <StatusNode
    data={data as unknown as StatusNodeData}
    className="bg-green-100 border-2 border-green-600 hover:bg-green-200"
    handles={[
      { type: 'target', position: Position.Top, id: 'top-target', style: successHandleStyle },
      { type: 'target', position: Position.Bottom, id: 'bottom-target', style: successHandleStyle },
      { type: 'source', position: Position.Left, id: 'left-source', style: successHandleStyle },
      { type: 'source', position: Position.Right, id: 'right-source', style: warningHandleStyle },
    ]}
  />
);

export const CompletedNode: React.FC<NodeProps> = ({ data }) => (
  <StatusNode
    data={data as unknown as StatusNodeData}
    className="bg-green-100 border-2 border-green-600 hover:bg-green-200"
    handles={[{ type: 'target', position: Position.Right, id: 'right-target', style: successHandleStyle }]}
  />
);

export const PrimaryQueueNode: React.FC<NodeProps> = ({ data }) => (
  <StatusNode
    data={data as unknown as StatusNodeData}
    className="bg-green-100 border-2 border-green-600 hover:bg-green-200"
    handles={[
      { type: 'target', position: Position.Top, id: 'top-target', style: successHandleStyle },
      { type: 'source', position: Position.Bottom, id: 'bottom-source', style: successHandleStyle },
    ]}
  />
);

export const ScheduledQueueNode: React.FC<NodeProps> = ({ data }) => (
  <StatusNode
    data={data as unknown as StatusNodeData}
    className="bg-yellow-100 border-2 border-yellow-600 hover:bg-yellow-200"
    handles={[
      { type: 'target', position: Position.Top, id: 'top-target', style: warningHandleStyle },
      { type: 'source', position: Position.Left, id: 'left-source', style: warningHandleStyle },
    ]}
  />
);

export const RetryNode: React.FC<NodeProps> = ({ data }) => (
  <StatusNode
    data={data as unknown as StatusNodeData}
    className="bg-yellow-100 border-2 border-yellow-600 hover:bg-yellow-200"
    handles={[
      { type: 'target', position: Position.Right, id: 'right-target', style: warningHandleStyle },
      { type: 'source', position: Position.Top, id: 'top-source', style: warningHandleStyle },
    ]}
  />
);

export const FailedNode: React.FC<NodeProps> = ({ data }) => (
  <StatusNode
    data={data as unknown as StatusNodeData}
    className="bg-yellow-100 border-2 border-yellow-600 hover:bg-yellow-200"
    handles={[
      { type: 'target', position: Position.Left, id: 'left-target', style: warningHandleStyle },
      { type: 'source', position: Position.Right, id: 'right-source', style: errorHandleStyle },
      { type: 'source', position: Position.Bottom, id: 'bottom-source', style: warningHandleStyle },
    ]}
  />
);

export const DeadLetterNode: React.FC<NodeProps> = ({ data }) => (
  <StatusNode
    data={data as unknown as StatusNodeData}
    className="bg-red-100 border-2 border-red-600 hover:bg-red-200"
    handles={[{ type: 'target', position: Position.Left, id: 'left-target', style: errorHandleStyle }]}
  />
);
