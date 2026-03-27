import { cn } from "@/lib/utils";

interface BadgeProps {
  variant?: "default" | "success" | "warning" | "danger" | "info";
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant = "default", children, className }: BadgeProps) {
  const variants = {
    default: "bg-f1-surface-light text-gray-300 border-f1-border",
    success: "bg-green-900/30 text-green-400 border-green-800",
    warning: "bg-yellow-900/30 text-yellow-400 border-yellow-800",
    danger: "bg-f1-red/10 text-f1-red border-f1-red/30",
    info: "bg-f1-blue/10 text-f1-blue border-f1-blue/30",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border",
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
