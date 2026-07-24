import { Copy, FileText, ThumbsDown, ThumbsUp } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Citation, QueryResponse } from "../types";

type Props = {
  response: QueryResponse;
  selected: number;
  onSelect: (index: number) => void;
};

function linkifyCitations(text: string) {
  return text
    .split(/(```[\s\S]*?```|`[^`\n]+`)/g)
    .map((part) => part.startsWith("`")
      ? part
      : part.replace(/\[(\d+)]/g, "[$1](#citation-$1)"))
    .join("");
}

function AnswerText({
  text,
  onCitationSelect,
}: {
  text: string;
  onCitationSelect: (index: number) => void;
}) {
  return (
    <div className="answer-copy">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            const citation = href?.match(/^#citation-(\d+)$/);
            if (citation) {
              const number = Number(citation[1]);
              return (
                <button
                  type="button"
                  className="citation-mark"
                  aria-label={`查看证据 ${number}`}
                  onClick={() => onCitationSelect(number - 1)}
                >
                  [{number}]
                </button>
              );
            }
            return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
          },
        }}
      >
        {linkifyCitations(text)}
      </ReactMarkdown>
    </div>
  );
}

function scoreOf(citation: Citation) {
  return citation.scores.rerank ?? citation.scores.vector ?? 0;
}

export function AnswerPanel({ response, selected, onSelect }: Props) {
  return (
    <section className="panel answer-panel">
      <div className="panel-heading answer-heading">
        <div><span className="answer-spark">✦</span><strong>生成的排查建议</strong></div>
        <div className="confidence">
          <span>证据相关度</span>
          <b>{Math.round(response.confidence * 100)}%</b>
        </div>
      </div>
      <AnswerText text={response.answer} onCitationSelect={onSelect} />
      <div className="source-table">
        <div className="source-table-head">
          <span>主要支撑证据</span><span>重排相关度</span>
        </div>
        {response.citations.map((citation, index) => (
          <button
            className={selected === index ? "source-row is-selected" : "source-row"}
            id={`citation-${citation.number}`}
            key={`${citation.source_id}-${citation.number}`}
            onClick={() => onSelect(index)}
          >
            <span className="source-index">{citation.number}</span>
            <FileText size={14} />
            <span className="source-name">{citation.title}</span>
            <code>{citation.source_url.replace(/^https?:\/\//, "").slice(0, 34)}</code>
            <b>{scoreOf(citation).toFixed(2)}</b>
          </button>
        ))}
      </div>
      <div className="answer-footer">
        <span>AI 生成内容可能存在误差，请核验关键操作。</span>
        <div>
          <button><ThumbsUp size={14} />有帮助</button>
          <button><ThumbsDown size={14} />无帮助</button>
          <button onClick={() => navigator.clipboard?.writeText(response.answer)}>
            <Copy size={14} />复制
          </button>
        </div>
      </div>
    </section>
  );
}
