import { ClipboardCheck, Copy, FileText, SearchCheck } from "lucide-react";
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
  const hasAnswer = Boolean(response.answer.trim());

  return (
    <section className="panel answer-panel">
      <div className="panel-heading answer-heading">
        <div><span className="answer-spark"><SearchCheck size={17} /></span><strong>知识库回答</strong></div>
        {hasAnswer ? (
          <div className="confidence">
            <span>证据相关度</span>
            <b>{Math.round(response.confidence * 100)}%</b>
          </div>
        ) : null}
      </div>
      {hasAnswer ? (
        <>
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
                <FileText size={16} />
                <span className="source-name">{citation.title}</span>
                <code>{citation.source_url.replace(/^https?:\/\//, "").slice(0, 34)}</code>
                <b>{scoreOf(citation).toFixed(2)}</b>
              </button>
            ))}
          </div>
          <div className="answer-footer">
            <span>AI 生成内容可能存在误差，请在执行变更前核验关键操作。</span>
            <button onClick={() => navigator.clipboard?.writeText(response.answer)}>
              <Copy size={16} />复制答案
            </button>
          </div>
        </>
      ) : (
        <div className="answer-empty">
          <span className="empty-icon"><ClipboardCheck size={26} /></span>
          <div>
            <strong>输入问题开始检索</strong>
            <p>系统会检索当前知识库，并返回带原文引用的可核验回答。</p>
          </div>
        </div>
      )}
    </section>
  );
}
