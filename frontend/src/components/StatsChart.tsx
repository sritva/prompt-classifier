import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { PromptRecord } from "../types";

interface StatsChartProps {
  history: PromptRecord[];
}

export const StatsChart: React.FC<StatsChartProps> = ({ history }) => {
  // Aggregate data
  const counts = {
    factual_lookup: 0,
    computation: 0,
    code_debugging: 0,
    decision_making: 0,
    other: 0,
    divergent: 0,
  };

  history.forEach((record) => {
    if (record.classification === "divergent") {
      counts.divergent += 1;
    } else if (record.classification === "convergent" && record.subtype) {
      counts[record.subtype] = (counts[record.subtype] || 0) + 1;
    }
  });

  const data = [
    { name: "Fact Lookup", value: counts.factual_lookup, type: "convergent" },
    { name: "Computation", value: counts.computation, type: "convergent" },
    { name: "Code Debug", value: counts.code_debugging, type: "convergent" },
    { name: "Decision", value: counts.decision_making, type: "convergent" },
    { name: "Other Conv", value: counts.other, type: "convergent" },
    { name: "Divergent", value: counts.divergent, type: "divergent" },
  ].filter((item) => item.value > 0);

  if (data.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          color: "var(--color-muted)",
          fontFamily: "var(--font-mono)",
          fontSize: "0.8rem",
        }}
      >
        [ NO DATA YET ]
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart
        data={data}
        margin={{ top: 10, right: 10, left: -25, bottom: 0 }}
      >
        <XAxis
          dataKey="name"
          stroke="var(--color-muted)"
          fontSize={10}
          tickLine={false}
          axisLine={{ stroke: "var(--color-border)" }}
          fontFamily="var(--font-mono)"
        />
        <YAxis
          stroke="var(--color-muted)"
          fontSize={10}
          tickLine={false}
          axisLine={{ stroke: "var(--color-border)" }}
          allowDecimals={false}
          fontFamily="var(--font-mono)"
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#181716",
            border: "1px solid var(--color-border)",
            borderRadius: "0",
            fontFamily: "var(--font-body)",
            fontSize: "0.85rem",
          }}
          itemStyle={{ color: "var(--color-text)" }}
          cursor={{ fill: "#242220" }}
        />
        <Bar dataKey="value" maxBarSize={40}>
          {data.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={
                entry.type === "convergent"
                  ? "var(--color-convergent)"
                  : "var(--color-divergent)"
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
};
