import { cn } from "../../lib/utils";

export default function Card({ 
  title, 
  subtitle,
  children, 
  className = '', 
  glow = '',
  headerAction,
  noPadding = false
}) {
  return (
    <div className={cn(
      "glass-card rounded-xl border border-[--glass-border] flex flex-col overflow-hidden animate-fade-in transition-all duration-300",
      glow,
      className
    )}>
      {(title || subtitle || headerAction) && (
        <div className="px-5 py-4 border-b border-[--glass-border] flex items-center justify-between bg-white/[0.01] shrink-0">
          <div>
            {title && (
              <h2
                className="text-xs font-bold uppercase tracking-widest text-green-400"
                style={{ fontFamily: "'Space Grotesk', sans-serif" }}
              >
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="text-[10px] text-[--text-muted] mt-0.5 leading-none">
                {subtitle}
              </p>
            )}
          </div>
          {headerAction && (
            <div className="flex items-center gap-2">
              {headerAction}
            </div>
          )}
        </div>
      )}
      <div className={cn(
        "flex-1 overflow-y-auto custom-scrollbar",
        !noPadding && "p-5"
      )}>
        {children}
      </div>
    </div>
  );
}
