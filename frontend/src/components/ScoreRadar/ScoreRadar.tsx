import { SCORE_DIMENSIONS } from "../../types/api";
import { DIMENSION_LABELS } from "../../lib/agentLabels";

export interface RadarSeries {
  label: string;
  color: string;
  /** dimension -> 0..100 */
  scores: Record<string, number>;
}

export interface ScoreRadarProps {
  series: RadarSeries[];
  size?: number;
  max?: number;
  showLegend?: boolean;
}

const AXES = SCORE_DIMENSIONS;

function polarPoint(
  cx: number,
  cy: number,
  radius: number,
  index: number,
  count: number,
): [number, number] {
  const angle = (-90 + (index * 360) / count) * (Math.PI / 180);
  return [cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)];
}

/**
 * Dependency-free radar (spider) chart for the five scoring dimensions.
 * Supports one or more series for the candidate compare view.
 */
export function ScoreRadar({
  series,
  size = 240,
  max = 100,
  showLegend = true,
}: ScoreRadarProps) {
  const padding = 46;
  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - padding;
  const rings = [0.25, 0.5, 0.75, 1];
  const count = AXES.length;

  return (
    <div className="radar-wrap">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`五维评分雷达图：${series.map((s) => s.label).join("、")}`}
      >
        {/* grid rings */}
        {rings.map((ring) => {
          const points = AXES.map((_, index) =>
            polarPoint(cx, cy, radius * ring, index, count).join(","),
          ).join(" ");
          return (
            <polygon
              key={ring}
              points={points}
              fill="none"
              stroke="var(--line)"
              strokeWidth={1}
            />
          );
        })}

        {/* spokes + axis labels */}
        {AXES.map((dimension, index) => {
          const [x, y] = polarPoint(cx, cy, radius, index, count);
          const [lx, ly] = polarPoint(cx, cy, radius + 20, index, count);
          const anchor =
            Math.abs(lx - cx) < 2 ? "middle" : lx > cx ? "start" : "end";
          return (
            <g key={dimension}>
              <line
                x1={cx}
                y1={cy}
                x2={x}
                y2={y}
                stroke="var(--line)"
                strokeWidth={1}
              />
              <text
                x={lx}
                y={ly}
                textAnchor={anchor}
                dominantBaseline="middle"
                fontSize={11}
                fontWeight={600}
                fill="var(--ink-500)"
              >
                {DIMENSION_LABELS[dimension]}
              </text>
            </g>
          );
        })}

        {/* series polygons */}
        {series.map((serie) => {
          const points = AXES.map((dimension, index) => {
            const value = Math.max(0, Math.min(max, serie.scores[dimension] ?? 0));
            return polarPoint(cx, cy, (radius * value) / max, index, count).join(
              ",",
            );
          }).join(" ");
          return (
            <polygon
              key={serie.label}
              points={points}
              fill={serie.color}
              fillOpacity={series.length > 1 ? 0.14 : 0.2}
              stroke={serie.color}
              strokeWidth={2}
              strokeLinejoin="round"
            />
          );
        })}

        {/* vertices for single-series clarity */}
        {series.length === 1 &&
          series[0] &&
          AXES.map((dimension, index) => {
            const serie = series[0];
            if (!serie) return null;
            const value = Math.max(0, Math.min(max, serie.scores[dimension] ?? 0));
            const [x, y] = polarPoint(cx, cy, (radius * value) / max, index, count);
            return <circle key={dimension} cx={x} cy={y} r={3} fill={serie.color} />;
          })}
      </svg>

      {showLegend && series.length > 1 && (
        <div className="radar-legend">
          {series.map((serie) => (
            <span className="lg" key={serie.label}>
              <span className="sw" style={{ background: serie.color }} />
              {serie.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
