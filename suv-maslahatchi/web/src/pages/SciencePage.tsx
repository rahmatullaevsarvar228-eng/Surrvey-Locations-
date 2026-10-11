import { useT } from "../lib/i18n";

const SECTIONS: { h: string; items: string; tone: string; ordered?: boolean }[] = [
  { h: "science.model_h", items: "science.model_p", tone: "border-water" },
  { h: "science.params_h", items: "science.params", tone: "border-soil" },
  { h: "science.gap_h", items: "science.gap", tone: "border-alert" },
  { h: "science.plan_h", items: "science.plan", tone: "border-leaf", ordered: true },
  { h: "science.refs_h", items: "science.refs", tone: "border-muted" },
];

export function SciencePage() {
  const { t, list } = useT();
  return (
    <article className="max-w-3xl space-y-4">
      <h1 className="text-[28px] font-semibold">{t("web.science_title")}</h1>
      {SECTIONS.map((s) => {
        const L = s.ordered ? "ol" : "ul";
        return (
          <section key={s.h} className={`card border-l-8 ${s.tone}`}>
            <h2 className="text-xl font-semibold mb-2">{t(s.h)}</h2>
            <L className={`${s.ordered ? "list-decimal" : "list-disc"} pl-5 space-y-1.5 leading-relaxed`}>
              {list(s.items).map((x) => <li key={x}>{x}</li>)}
            </L>
          </section>
        );
      })}
    </article>
  );
}
