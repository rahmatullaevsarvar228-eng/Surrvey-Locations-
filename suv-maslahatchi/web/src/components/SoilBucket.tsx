import { useId } from "react";
import type { SimRow } from "../lib/api";
import { useT } from "../lib/i18n";

/**
 * «Tuproq stakani» — vertikal tuproq ustuni.
 *  - suv sathi = ildiz zonasidagi foydali suv zaxirasi (1 − Dr/TAW)
 *  - shtrix chiziq = RAW chegarasi (sath undan pastga tushsa — stress)
 *  - ildizlar Zr bilan o‘sadi
 *  - ildizdan pastga tushayotgan tomchilar = chuqur o‘tish (yo‘qotish, --alert)
 * Barcha qiymatlar serverdagi engine natijasi (SimRow); bu yerda faqat chizish.
 */
const W = 240, H = 440;
const COL_X = 62, COL_W = 132, SURFACE = 92, BOTTOM = 410;

export function SoilBucket({ row, zrMax, title, tone = "water", compact = false }: {
  row: SimRow; zrMax: number; title: string; tone?: "water" | "soil"; compact?: boolean;
}) {
  const { t } = useT();
  const clip = `col${useId().replace(/:/g, "")}`;
  const depthMax = zrMax + 0.35;
  const pxPerM = (BOTTOM - SURFACE) / depthMax;
  const rootBottom = SURFACE + row.zr_m * pxPerM;
  const rootH = rootBottom - SURFACE;
  const reserve = row.taw_mm > 0 ? Math.max(0, Math.min(1, 1 - row.tanqislik_mm / row.taw_mm)) : 0;
  const rawFrac = row.taw_mm > 0 ? row.raw_mm / row.taw_mm : 0;
  const waterTop = rootBottom - reserve * rootH;
  const rawY = rootBottom - (1 - rawFrac) * rootH;
  const stressed = row.stress;
  const irrigated = row.sugorish_mm > 0;
  const raining = row.yomgir >= 1;
  const deep = row.chuqur_mm > 0;
  const sunOpacity = Math.min(1, 0.25 + row.et0 / 9);
  const waterColor = stressed ? "rgb(var(--alert))" : "rgb(var(--water))";
  const roots = rootPaths(row.zr_m * pxPerM);

  return (
    <figure className={`card shadow-[0_8px_24px_-12px_rgba(0,0,0,0.35)] flex flex-col items-center border-t-8 ${tone === "soil" ? "border-t-soil" : "border-t-water"}`} aria-label={title}>
      <figcaption className="self-stretch flex items-baseline justify-between gap-2 mb-1">
        <span className="font-semibold">{title}</span>
        <span className={`num text-2xl ${stressed ? "text-alert" : ""}`}>{Math.round(reserve * 100)}%</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className={`bucket-svg w-full ${compact ? "max-w-[220px]" : "max-w-[280px]"}`}
           role="img" aria-label={`${t("web.reserve")}: ${Math.round(reserve * 100)}%`}>
        <defs>
          <pattern id="soil-dots" width="10" height="10" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="3" r="1" fill="rgb(var(--soil))" opacity="0.35" />
            <circle cx="7" cy="8" r="0.8" fill="rgb(var(--soil))" opacity="0.25" />
          </pattern>
          <clipPath id={clip}><rect x={COL_X} y={SURFACE} width={COL_W} height={BOTTOM - SURFACE} rx="6" /></clipPath>
        </defs>

        {/* quyosh: ET0 qancha katta — shuncha yorqin */}
        <g aria-hidden="true">
          <circle cx={W - 34} cy={28} r={14} fill="rgb(var(--sun))" opacity={sunOpacity} />
          {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
            <line key={a} x1={W - 34} y1={6} x2={W - 34} y2={0} stroke="rgb(var(--sun))" strokeWidth="2"
                  opacity={sunOpacity} transform={`rotate(${a} ${W - 34} 28)`} />
          ))}
          <text x={W - 34} y={66} textAnchor="middle" className="num" fontSize="11" fill="rgb(var(--muted))">
            ET0 {row.et0.toFixed(1)}
          </text>
        </g>

        {/* yomg‘ir */}
        {raining && (
          <g aria-hidden="true">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <line key={i} x1={COL_X + 14 + i * 22} y1={20} x2={COL_X + 10 + i * 22} y2={32}
                    stroke="rgb(var(--water))" strokeWidth="2" strokeLinecap="round" className="anim-rain"
                    style={{ animationDelay: `${i * 0.11}s`, ["--fall" as string]: "48px" }} />
            ))}
            <text x={COL_X} y={14} fontSize="11" fill="rgb(var(--water))" className="num">
              {t("web.rain")} {row.yomgir.toFixed(0)} mm
            </text>
          </g>
        )}

        {/* o‘simlik */}
        <g aria-hidden="true">
          <line x1={W / 2} y1={SURFACE} x2={W / 2} y2={SURFACE - 30} stroke="rgb(var(--leaf))" strokeWidth="3" />
          <ellipse cx={W / 2 - 10} cy={SURFACE - 24} rx="10" ry="5" fill="rgb(var(--leaf))" transform={`rotate(-25 ${W / 2 - 10} ${SURFACE - 24})`} />
          <ellipse cx={W / 2 + 10} cy={SURFACE - 30} rx="10" ry="5" fill="rgb(var(--leaf))" transform={`rotate(25 ${W / 2 + 10} ${SURFACE - 30})`} />
        </g>

        {/* tuproq ustuni */}
        <rect x={COL_X} y={SURFACE} width={COL_W} height={BOTTOM - SURFACE} rx="6"
              fill="rgb(var(--soil) / 0.16)" stroke="rgb(var(--soil))" strokeWidth="2" />
        <rect x={COL_X} y={SURFACE} width={COL_W} height={BOTTOM - SURFACE} rx="6" fill="url(#soil-dots)" />

        <g clipPath={`url(#${clip})`}>
          {/* ildiz zonasi chegarasi */}
          <rect x={COL_X} y={SURFACE} width={COL_W} height={rootH} fill="rgb(var(--soil) / 0.12)" className="level" />
          {/* suv */}
          <rect x={COL_X} y={waterTop} width={COL_W} height={Math.max(0, rootBottom - waterTop)}
                fill={waterColor} opacity="0.55" className="level" />
          <line x1={COL_X} x2={COL_X + COL_W} y1={waterTop} y2={waterTop} stroke={waterColor} strokeWidth="2" className="level" />
          {/* ildizlar */}
          <g stroke="rgb(var(--soil))" strokeWidth="2" fill="none" strokeLinecap="round" transform={`translate(${W / 2} ${SURFACE})`}>
            {roots.map((d, i) => <path key={i} d={d} opacity={i === 0 ? 1 : 0.8} />)}
          </g>
        </g>

        {/* sug‘orish oqimi */}
        {irrigated && (
          <g aria-hidden="true">
            <path d={`M${COL_X} ${SURFACE - 4} q18 -8 36 0 t36 0 t36 0 t36 0`} stroke="rgb(var(--water))" strokeWidth="5" fill="none" />
            <text x={COL_X} y={SURFACE - 40} fontSize="12" fontWeight="600" fill="rgb(var(--water))" className="num">
              +{row.sugorish_mm.toFixed(0)} mm
            </text>
          </g>
        )}

        {/* RAW chegarasi */}
        <line x1={COL_X - 8} x2={COL_X + COL_W + 8} y1={rawY} y2={rawY} stroke="rgb(var(--ink))" strokeWidth="1.5"
              strokeDasharray="6 4" className="level" />
        <text x={COL_X + COL_W + 10} y={rawY + 4} fontSize="10" fill="rgb(var(--muted))">RAW</text>
        {/* ildiz chuqurligi */}
        <line x1={COL_X - 14} x2={COL_X - 4} y1={rootBottom} y2={rootBottom} stroke="rgb(var(--soil))" strokeWidth="2" />
        <text x={COL_X - 16} y={rootBottom + 4} fontSize="10" textAnchor="end" className="num" fill="rgb(var(--muted))">
          {row.zr_m.toFixed(2)} m
        </text>
        <text x={COL_X - 16} y={SURFACE + 4} fontSize="10" textAnchor="end" className="num" fill="rgb(var(--muted))">0</text>

        {/* chuqur o‘tish — yo‘qotish */}
        {deep && (
          <g aria-hidden="true">
            {[0, 1, 2].map((i) => (
              <path key={i} d="M0 0 q4 6 0 10 q-4 -4 0 -10z" fill="rgb(var(--alert))" className="anim-drop"
                    transform={`translate(${COL_X + 40 + i * 32} ${rootBottom + 6})`}
                    style={{ animationDelay: `${i * 0.25}s`, ["--fall" as string]: `${Math.max(16, BOTTOM - rootBottom - 18)}px` }} />
            ))}
          </g>
        )}
      </svg>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm self-stretch mt-1">
        <dt className="text-muted">{t("web.depletion")}</dt>
        <dd className="num text-right">{row.tanqislik_mm.toFixed(0)} / {row.taw_mm.toFixed(0)} mm</dd>
        <dt className="text-muted">{t("web.deep_loss")}</dt>
        <dd className={`num text-right ${deep ? "text-alert font-semibold" : ""}`}>{row.chuqur_mm.toFixed(0)} mm</dd>
      </dl>
    </figure>
  );
}

/** Ildiz shoxlari: chuqurlikka mos cho‘ziladi (faqat bezak, hisobsiz). */
function rootPaths(depthPx: number): string[] {
  const d = Math.max(8, depthPx);
  return [
    `M0 0 C 2 ${d * 0.3}, -3 ${d * 0.6}, 0 ${d}`,
    `M0 ${d * 0.15} C -14 ${d * 0.3}, -26 ${d * 0.5}, -30 ${d * 0.78}`,
    `M0 ${d * 0.2} C 14 ${d * 0.35}, 24 ${d * 0.55}, 32 ${d * 0.8}`,
    `M0 ${d * 0.45} C -8 ${d * 0.6}, -14 ${d * 0.75}, -16 ${d * 0.95}`,
    `M0 ${d * 0.5} C 8 ${d * 0.65}, 14 ${d * 0.8}, 18 ${d * 0.96}`,
  ];
}
