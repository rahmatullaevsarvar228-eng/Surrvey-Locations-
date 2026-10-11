import { useEffect, useRef } from "react";
import type { EChartsCoreOption } from "echarts/core";
import { echarts } from "../lib/charts";

export function EChart({ option, height = 280, label }: { option: EChartsCoreOption; height?: number; label: string }) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  useEffect(() => {
    if (!el.current) return;
    chart.current = echarts.init(el.current, undefined, { renderer: "svg" });
    const ro = new ResizeObserver(() => chart.current?.resize());
    ro.observe(el.current);
    return () => { ro.disconnect(); chart.current?.dispose(); };
  }, []);
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    chart.current?.setOption({ animation: !reduce, ...option }, { notMerge: true });
  }, [option]);
  return <div ref={el} role="img" aria-label={label} style={{ height, width: "100%" }} />;
}
