import React from 'react';
// eslint-disable-next-line no-restricted-imports
import { Tooltip } from 'antd';

interface PremiumFeatureTooltipProps {
  premiumUser: boolean;
  featureName: string;
  children: React.ReactNode;
}

export function PremiumFeatureTooltip({ premiumUser, featureName, children }: PremiumFeatureTooltipProps) {
  return (
    <Tooltip
      title={!premiumUser ? `Setting ${featureName} is a premium feature` : ""}
      placement="top"
    >
      {children}
    </Tooltip>
  );
}
