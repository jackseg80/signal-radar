import { heatColor } from '../../utils/format';

export default function HeatCell({ value, min = 0, max = 3, scale = 'sequential', children, className = '' }) {
  const bg = heatColor(value, min, max, scale);
  return (
    <td
      className={`py-2.5 px-3 text-center ${className}`}
      style={{ backgroundColor: bg }}
    >
      {children}
    </td>
  );
}
