import type { Tab } from "../state/store";
import { S } from "../i18n";
import { useStore } from "../state/store";
import { ViewHeader } from "../ui/ViewHeader";

const G = S.guide;

export function GuideView() {
  const { dispatch } = useStore();
  const open = (tab: Tab) => dispatch({ type: "tab", tab });
  return (
    // Phase 4 correction: the same document container as Data and validation (prose-wide)
    <article className="prose prose-wide">
      <ViewHeader eyebrow={S.shell.eyebrows.guide} title={G.title} subtitle={G.intro} />

      {/* UI simplification: the workflow first, one step per tab, with a direct way into each */}
      <section className="guide-start" aria-labelledby="guide-start-h">
        <h2 id="guide-start-h">{G.startHeading}</h2>
        <p>{G.startIntro}</p>
        <ol className="guide-steps">
          {G.steps.map((st) => (
            <li key={st.title}>
              <button type="button" className="guide-step" onClick={() => open(st.tab as Tab)} aria-label={G.openStep(st.title)}>
                <strong>{st.title}</strong>
                <span>{st.text}</span>
              </button>
            </li>
          ))}
        </ol>
        <p><a href="#data" className="guide-data-link">{G.dataLink}</a></p>
      </section>

      <h2>{G.panoramaHeading}</h2>
      {G.panorama.map((p) => <p key={p}>{p}</p>)}

      <h2>{G.timelineHeading}</h2>
      <p>{G.timeline}</p>

      <h2>{G.rulesHeading}</h2>
      <dl>
        {G.rules.map((d) => <Entry key={d.term} term={d.term} text={d.text} />)}
      </dl>

      <h2>{G.radioHeading}</h2>
      <p>{G.radio}</p>

      <h2>{G.powerHeading}</h2>
      <p>{G.power}</p>

      <h2>{G.glossaryHeading}</h2>
      <dl>
        {G.glossary.map((d) => <Entry key={d.term} term={d.term} text={d.text} />)}
      </dl>
    </article>
  );
}

function Entry({ term, text }: { term: string; text: string }) {
  return <><dt>{term}</dt><dd>{text}</dd></>;
}
