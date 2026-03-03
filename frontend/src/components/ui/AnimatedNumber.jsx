import { useState, useEffect, useRef } from 'react';

export default function AnimatedNumber({ value, format = (v) => v.toFixed(2), duration = 600, className = '' }) {
  const [display, setDisplay] = useState(value ?? 0);
  const prevRef = useRef(value ?? 0);
  const rafRef = useRef(null);

  useEffect(() => {
    if (value == null || isNaN(value)) return;

    const from = prevRef.current;
    const to = value;
    const startTime = performance.now();

    if (from === to) {
      setDisplay(to);
      return;
    }

    const animate = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(from + (to - from) * eased);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };

    rafRef.current = requestAnimationFrame(animate);
    prevRef.current = to;

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [value, duration]);

  return (
    <span className={`tabular-nums ${className}`}>
      {format(display)}
    </span>
  );
}
