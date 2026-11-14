import { S } from "../i18n";

const G = S.guide;

export function GuideView() {
  return (
    <article className="prose">
      <h1>{G.title}</h1>
      <p>{G.intro}</p>

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
