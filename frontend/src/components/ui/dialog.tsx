import React from 'react';

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

interface DialogContentProps {
  children: React.ReactNode;
  className?: string;
}

interface DialogHeaderProps {
  children: React.ReactNode;
}

interface DialogTitleProps {
  children: React.ReactNode;
}

interface DialogDescriptionProps {
  children: React.ReactNode;
}

interface DialogFooterProps {
  children: React.ReactNode;
}

export const Dialog: React.FC<DialogProps> = ({ open, onOpenChange, children }) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div 
        className="fixed inset-0 bg-black bg-opacity-50" 
        onClick={() => onOpenChange(false)}
      />
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
};

export const DialogContent: React.FC<DialogContentProps> = ({ children, className = '' }) => {
  return (
    <div className={`bg-white rounded-lg shadow-lg p-6 max-w-md w-full mx-4 ${className}`}>
      {children}
    </div>
  );
};

export const DialogHeader: React.FC<DialogHeaderProps> = ({ children }) => {
  return (
    <div className="mb-4">
      {children}
    </div>
  );
};

export const DialogTitle: React.FC<DialogTitleProps> = ({ children }) => {
  return (
    <h2 className="text-lg font-semibold text-gray-900">
      {children}
    </h2>
  );
};

export const DialogDescription: React.FC<DialogDescriptionProps> = ({ children }) => {
  return (
    <p className="text-sm text-gray-600 mt-2">
      {children}
    </p>
  );
};

export const DialogFooter: React.FC<DialogFooterProps> = ({ children }) => {
  return (
    <div className="flex justify-end space-x-2 mt-6">
      {children}
    </div>
  );
};
