// frontend/src/components/dashboard/CustomNodes.tsx
import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';

interface CustomNodeData {
  count?: number;
  label?: React.ReactNode;
}

// Custom Active Node
export const ActiveNode: React.FC<NodeProps> = ({ data }) => {
  const nodeData = data as unknown as CustomNodeData;
  return (
    <div className="bg-green-100 border-2 border-green-600 rounded-lg p-3 w-[140px] h-[80px] flex flex-col justify-center text-center text-gray-900 transition-colors cursor-pointer hover:bg-green-200">
      {/* Central target handle on top border for Primary node edge */}
      <Handle
        type="target"
        position={Position.Top}
        id="top-target"
        style={{
          background: '#16a34a',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      {/* Target handle on bottom border */}
      <Handle
        type="target"
        position={Position.Bottom}
        id="bottom-target"
        style={{
          background: '#16a34a',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      {/* Source handle on left border for Completed edge */}
      <Handle
        type="source"
        position={Position.Left}
        id="left-source"
        style={{
          background: '#16a34a',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      {/* Source handle on right border for Failed edge */}
      <Handle
        type="source"
        position={Position.Right}
        id="right-source"
        style={{
          background: '#ca8a04',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      <div className="text-center text-gray-800">
        <div className="font-semibold">Active</div>
        <div className="text-lg font-bold">{nodeData.count || 0}</div>
      </div>
    </div>
  );
};

// Custom Completed Node
export const CompletedNode: React.FC<NodeProps> = ({ data }) => {
  const nodeData = data as unknown as CustomNodeData;
  return (
    <div className="bg-green-100 border-2 border-green-600 rounded-lg p-3 w-[140px] h-[80px] flex flex-col justify-center text-center text-gray-900 transition-colors cursor-pointer hover:bg-green-200">
      {/* Target handle on right border */}
      <Handle
        type="target"
        position={Position.Right}
        id="right-target"
        style={{
          background: '#16a34a',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      <div className="text-center text-gray-800">
        <div className="font-semibold">Completed</div>
        <div className="text-lg font-bold">{nodeData.count || 0}</div>
      </div>
    </div>
  );
};

// Custom Primary Queue Node
export const PrimaryQueueNode: React.FC<NodeProps> = ({ data }) => {
  const nodeData = data as unknown as CustomNodeData;
  return (
    <div className="bg-green-100 border-2 border-green-600 rounded-lg p-3 w-[140px] h-[80px] flex flex-col justify-center text-center text-gray-900 transition-colors cursor-pointer hover:bg-green-200">
      {/* Target handle on top border */}
      <Handle
        type="target"
        position={Position.Top}
        id="top-target"
        style={{
          background: '#16a34a',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      {/* Source handle on bottom border */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom-source"
        style={{
          background: '#16a34a',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      <div className="text-center text-gray-800">
        <div className="font-semibold">Primary</div>
        <div className="text-lg font-bold">{nodeData.count || 0}</div>
      </div>
    </div>
  );
};

// Custom Scheduled Queue Node
export const ScheduledQueueNode: React.FC<NodeProps> = ({ data }) => {
  const nodeData = data as unknown as CustomNodeData;
  return (
    <div className="bg-yellow-100 border-2 border-yellow-600 rounded-lg p-3 w-[140px] h-[80px] flex flex-col justify-center text-center text-gray-900 transition-colors cursor-pointer hover:bg-yellow-200">
      {/* Target handle on top border */}
      <Handle
        type="target"
        position={Position.Top}
        id="top-target"
        style={{
          background: '#ca8a04',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      {/* Source handle on left border */}
      <Handle
        type="source"
        position={Position.Left}
        id="left-source"
        style={{
          background: '#ca8a04',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      <div className="text-center text-gray-800">
        <div className="font-semibold">Scheduled</div>
        <div className="text-lg font-bold">{nodeData.count || 0}</div>
      </div>
    </div>
  );
};

// Custom Retry Node
export const RetryNode: React.FC<NodeProps> = ({ data }) => {
  const nodeData = data as unknown as CustomNodeData;
  return (
    <div className="bg-yellow-100 border-2 border-yellow-600 rounded-lg p-3 w-[140px] h-[80px] flex flex-col justify-center text-center text-gray-900 transition-colors cursor-pointer hover:bg-yellow-200">
      {/* Target handle on right border */}
      <Handle
        type="target"
        position={Position.Right}
        id="right-target"
        style={{
          background: '#ca8a04',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      {/* Source handle on top border for going back to Active */}
      <Handle
        type="source"
        position={Position.Top}
        id="top-source"
        style={{
          background: '#ca8a04',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      <div className="text-center text-gray-800">
        <div className="font-semibold">Retry</div>
        <div className="text-lg font-bold">{nodeData.count || 0}</div>
      </div>
    </div>
  );
};

// Custom Failed Node
export const FailedNode: React.FC<NodeProps> = ({ data }) => {
  const nodeData = data as unknown as CustomNodeData;
  return (
    <div className="bg-yellow-100 border-2 border-yellow-600 rounded-lg p-3 w-[140px] h-[80px] flex flex-col justify-center text-center text-gray-900 transition-colors cursor-pointer hover:bg-yellow-200">
      {/* Target handle on left border for Active node edge */}
      <Handle
        type="target"
        position={Position.Left}
        id="left-target"
        style={{
          background: '#ca8a04',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      {/* Source handle on right border for Dead Letter edge */}
      <Handle
        type="source"
        position={Position.Right}
        id="right-source"
        style={{
          background: '#dc2626',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      {/* Source handle on bottom border for Scheduled edge */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom-source"
        style={{
          background: '#ca8a04',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      <div className="text-center text-gray-800">
        <div className="font-semibold">Failed</div>
        <div className="text-lg font-bold">{nodeData.count || 0}</div>
      </div>
    </div>
  );
};

// Custom Dead Letter Node
export const DeadLetterNode: React.FC<NodeProps> = ({ data }) => {
  const nodeData = data as unknown as CustomNodeData;
  return (
    <div className="bg-red-100 border-2 border-red-600 rounded-lg p-3 w-[140px] h-[80px] flex flex-col justify-center text-center text-gray-900 transition-colors cursor-pointer hover:bg-red-200">
      {/* Target handle on left border for Failed node edge */}
      <Handle
        type="target"
        position={Position.Left}
        id="left-target"
        style={{
          background: '#dc2626',
          width: 8,
          height: 8,
          border: '2px solid #fff',
        }}
      />
      
      <div className="text-center text-gray-800">
        <div className="font-semibold">Dead Letter</div>
        <div className="text-lg font-bold">{nodeData.count || 0}</div>
      </div>
    </div>
  );
};

// Export node types for ReactFlow
// eslint-disable-next-line react-refresh/only-export-components
export const nodeTypes = {
  activeNode: ActiveNode,
  completedNode: CompletedNode,
  primaryQueueNode: PrimaryQueueNode,
  scheduledQueueNode: ScheduledQueueNode,
  retryNode: RetryNode,
  failedNode: FailedNode,
  deadLetterNode: DeadLetterNode,
};
