import React from "react";

interface GlyphProps {
  state: "convergent" | "divergent" | "neutral";
}

export const Glyph: React.FC<GlyphProps> = ({ state }) => {
  return (
    <svg
      width="48"
      height="48"
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ transition: "all 0.5s ease" }}
      aria-label={`Guilford Glyph - Current thinking mode: ${state}`}
    >
      {/* Background circle */}
      <circle cx="24" cy="24" r="23" stroke="#2C2A28" strokeWidth="1" />
      
      {/* Central point */}
      <circle cx="24" cy="24" r="3" fill="#E3DFD5" />

      {/* Convergent Paths (Inward arrows) */}
      {state === "convergent" && (
        <g stroke="#7091B5" strokeWidth="2" strokeLinecap="round">
          {/* Arrow 1: Top to Center */}
          <line x1="24" y1="8" x2="24" y2="18" />
          <path d="M21 15L24 18L27 15" fill="none" />
          
          {/* Arrow 2: Bottom to Center */}
          <line x1="24" y1="40" x2="24" y2="30" />
          <path d="M21 33L24 30L27 33" fill="none" />
          
          {/* Arrow 3: Left to Center */}
          <line x1="8" y1="24" x2="18" y2="24" />
          <path d="M15 21L18 24L15 27" fill="none" />
          
          {/* Arrow 4: Right to Center */}
          <line x1="40" y1="24" x2="30" y2="24" />
          <path d="M33 21L30 24L33 27" fill="none" />
        </g>
      )}

      {/* Divergent Paths (Outward arrows) */}
      {state === "divergent" && (
        <g stroke="#D49B55" strokeWidth="2" strokeLinecap="round">
          {/* Arrow 1: Center to Top-Left */}
          <line x1="24" y1="24" x2="14" y2="14" />
          <path d="M14 19V14H19" fill="none" />
          
          {/* Arrow 2: Center to Top-Right */}
          <line x1="24" y1="24" x2="34" y2="14" />
          <path d="M29 14H34V19" fill="none" />
          
          {/* Arrow 3: Center to Bottom-Left */}
          <line x1="24" y1="24" x2="14" y2="34" />
          <path d="M19 34H14V29" fill="none" />
          
          {/* Arrow 4: Center to Bottom-Right */}
          <line x1="24" y1="24" x2="34" y2="34" />
          <path d="M34 29V34H29" fill="none" />
        </g>
      )}

      {/* Neutral State (Both styles balanced) */}
      {state === "neutral" && (
        <g stroke="#7D786F" strokeWidth="1.5" strokeLinecap="round" opacity="0.6">
          <circle cx="24" cy="24" r="10" strokeDasharray="3 3" />
          <line x1="24" y1="6" x2="24" y2="42" />
          <line x1="6" y1="24" x2="42" y2="24" />
        </g>
      )}
    </svg>
  );
};
