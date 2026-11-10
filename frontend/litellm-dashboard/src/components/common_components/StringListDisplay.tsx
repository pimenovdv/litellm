import React from 'react';
// eslint-disable-next-line no-restricted-imports
import { Text } from '@tremor/react';

interface StringListDisplayProps {
  label: string;
  items?: string[] | null;
  emptyText?: React.ReactNode;
  fallbackText?: string;
}

export function StringListDisplay({ label, items, emptyText = "Not specified", fallbackText }: StringListDisplayProps) {
  const displayEmptyText = fallbackText || emptyText;
  const hasItems = Array.isArray(items) && items.length > 0;

  const emptyContent = typeof displayEmptyText === "string" ? <Text>{displayEmptyText}</Text> : <>{displayEmptyText}</>;

  return (
    <div>
      <Text className="font-medium">{label}</Text>
      <div className="flex flex-wrap gap-2 mt-1">
        {hasItems ? (
          items!.map((item, index) => (
            <span key={index} className="px-2 py-1 bg-blue-100 rounded-sm text-xs">
              {item}
            </span>
          ))
        ) : (
          emptyContent
        )}
      </div>
    </div>
  );
}
