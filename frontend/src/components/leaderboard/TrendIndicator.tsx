interface TrendIndicatorProps {
  /** Positive = moving up, negative = moving down, 0 = no change */
  trend: number;
}

export function TrendIndicator({ trend }: TrendIndicatorProps) {
  if (trend === 0) {
    return <span className="text-f1-muted text-xs">&ndash;</span>;
  }

  return trend > 0 ? (
    <span className="text-green-400 text-xs flex items-center gap-0.5">
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path
          fillRule="evenodd"
          d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z"
          clipRule="evenodd"
        />
      </svg>
      {trend}
    </span>
  ) : (
    <span className="text-f1-red text-xs flex items-center gap-0.5">
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path
          fillRule="evenodd"
          d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
          clipRule="evenodd"
        />
      </svg>
      {Math.abs(trend)}
    </span>
  );
}
