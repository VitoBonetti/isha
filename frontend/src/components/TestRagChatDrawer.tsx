import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  X, Send, Bot, User, Sparkles, RefreshCw, Loader2, ExternalLink, FileText, ChevronRight, Copy, Check, Link as LinkIcon
} from "lucide-react";
import { v4 as uuidv4 } from "uuid";
import toast from "react-hot-toast";
import type { Message, Citation, TestRagChatDrawerProps } from "../types/board";

export default function TestRagChatDrawer({
  isOpen,
  onClose,
  testId,
  testName,
  assetId,
  assetName,
}: TestRagChatDrawerProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [copiedCodeId, setCopiedCodeId] = useState<string | null>(null);
  const [sessionId] = useState(() => uuidv4());

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  const quickPrompts = [
    `Summarize findings for ${testName}`,
    assetName ? `Did we find vulnerabilities in previous tests of ${assetName}?` : "Summarize past asset vulnerabilities",
    "What is the live status on Keep Secure 24?",
    "Are there any open high or critical risks?",
  ];

  const handleCopyCode = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCodeId(id);
    toast.success("Code copied!");
    setTimeout(() => setCopiedCodeId(null), 2000);
  };

  const handleSend = async (queryText?: string) => {
    const textToSend = queryText || input;
    if (!textToSend.trim() || isGenerating) return;

    const userMessageId = uuidv4();
    const assistantMessageId = uuidv4();

    const newMessages: Message[] = [
      ...messages,
      { id: userMessageId, role: "user", content: textToSend },
      { id: assistantMessageId, role: "assistant", content: "", isStreaming: true },
    ];

    setMessages(newMessages);
    setInput("");
    setIsGenerating(true);

    try {
      const response = await fetch("/api/rag/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: textToSend,
          session_id: sessionId,
          test_id: testId,
          asset_id: assetId || null,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No reader available");

      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const data = JSON.parse(line);

            if (data.text) {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? { ...msg, content: msg.content + data.text }
                    : msg
                )
              );
            }

            if (data.citations) {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? { ...msg, citations: data.citations, isStreaming: false }
                    : msg
                )
              );
            }

            if (data.error) {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? { ...msg, content: `Error: ${data.error}`, isStreaming: false }
                    : msg
                )
              );
            }
          } catch (err) {
            console.error("Failed to parse stream chunk", err);
          }
        }
      }

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId ? { ...msg, isStreaming: false } : msg
        )
      );
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, content: `Failed to connect to Luigi: ${err.message}`, isStreaming: false }
            : msg
        )
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleResetChat = () => {
    setMessages([]);
  };

  if (!isOpen) return null;

  return (
    /* BACKDROP OVERLAY: Clicking outside closes the drawer */
    <div
      className="fixed inset-0 z-50 overflow-hidden bg-slate-900/40 backdrop-blur-sm transition-opacity"
      onClick={onClose}
    >
      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        {/* DRAWER CONTAINER: Stop propagation so clicking inside doesn't close */}
        <div
          className="w-screen max-w-xl bg-white dark:bg-zinc-900 border-l border-slate-200 dark:border-zinc-800 shadow-2xl flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >

          {/* Drawer Header */}
          <div className="p-4 md:p-5 border-b border-slate-200 dark:border-zinc-800 flex items-center justify-between bg-slate-50/50 dark:bg-zinc-900/50">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-xl">
                <Bot size={22} />
              </div>
              <div>
                <h2 className="font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-1.5 text-base">
                  Luigi Assistant
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-extrabold bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300 uppercase tracking-wider">
                    Test Co-Pilot
                  </span>
                </h2>
                <p className="text-xs text-slate-500 dark:text-zinc-400 truncate max-w-[280px]">
                  Scoped to: <span className="font-medium text-slate-700 dark:text-zinc-300">{testName}</span>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={handleResetChat}
                title="Clear Conversation"
                className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-zinc-200 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
              >
                <RefreshCw size={18} />
              </button>
              <button
                type="button"
                onClick={onClose}
                className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-zinc-200 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
              >
                <X size={20} />
              </button>
            </div>
          </div>

          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col justify-center items-center text-center p-4">
                <div className="p-4 bg-indigo-50 dark:bg-indigo-950/30 text-indigo-600 dark:text-indigo-400 rounded-2xl mb-4 border border-indigo-100 dark:border-indigo-900/50">
                  <Sparkles size={32} />
                </div>
                <h3 className="font-bold text-slate-800 dark:text-zinc-200 mb-1 text-base">
                  How can Luigi help with this test?
                </h3>
                <p className="text-xs text-slate-500 dark:text-zinc-400 max-w-xs mb-6">
                  Ask anything about scope, findings, Keep Secure 24 status, or historical pentest reports for this asset.
                </p>

                {/* Quick Prompts */}
                <div className="w-full space-y-2">
                  <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400 block text-left">
                    Suggested Questions
                  </span>
                  {quickPrompts.map((prompt, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleSend(prompt)}
                      className="w-full text-left p-3 rounded-xl bg-slate-50 hover:bg-indigo-50/60 dark:bg-zinc-800/60 dark:hover:bg-zinc-800 text-xs text-slate-700 dark:text-zinc-300 border border-slate-200/80 dark:border-zinc-700/60 transition-all flex items-center justify-between group"
                    >
                      <span className="truncate pr-2">{prompt}</span>
                      <ChevronRight size={14} className="text-slate-400 group-hover:text-indigo-500 shrink-0 transition-colors" />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  {msg.role === "assistant" && (
                    <div className="p-2 h-8 w-8 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 shrink-0 flex items-center justify-center mt-1">
                      <Bot size={18} />
                    </div>
                  )}

                  <div className={`max-w-[88%] rounded-2xl p-4 text-xs leading-relaxed ${
                    msg.role === "user"
                      ? "bg-indigo-600 text-white font-medium rounded-br-none"
                      : "bg-slate-100 dark:bg-zinc-800/90 text-slate-800 dark:text-zinc-200 border border-slate-200/60 dark:border-zinc-700/50 rounded-bl-none"
                  }`}>
                    {/* MARKDOWN RENDERER */}
                    <div className="text-xs leading-relaxed break-words">
                      <ReactMarkdown
                        urlTransform={(url) => url}
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,
                          strong: ({ node, ...props }) => <strong className="font-semibold text-slate-950 dark:text-white" {...props} />,
                          ul: ({ node, ...props }) => <ul className="list-disc pl-4 mb-2 space-y-1" {...props} />,
                          ol: ({ node, ...props }) => <ol className="list-decimal pl-4 mb-2 space-y-1" {...props} />,
                          li: ({ node, ...props }) => <li className="text-slate-800 dark:text-zinc-300" {...props} />,
                          table: ({ node, ...props }) => (
                            <div className="overflow-x-auto my-2 border border-slate-200 dark:border-zinc-700 rounded-lg">
                              <table className="min-w-full divide-y divide-slate-200 dark:divide-zinc-700 text-xs" {...props} />
                            </div>
                          ),
                          thead: ({ node, ...props }) => <thead className="bg-slate-200/60 dark:bg-zinc-800" {...props} />,
                          th: ({ node, ...props }) => (
                            <th className="px-3 py-1.5 text-left font-semibold text-slate-900 dark:text-zinc-100 border-b border-slate-200 dark:border-zinc-700" {...props} />
                          ),
                          td: ({ node, ...props }) => (
                            <td className="px-3 py-1.5 border-t border-slate-200 dark:border-zinc-700/50" {...props} />
                          ),
                          code(props) {
                            const { children, className, node, ...rest } = props;
                            const match = /language-(\w+)/.exec(className || "");
                            const isInline = !match && !String(children).includes("\n");

                            if (isInline) {
                              return (
                                <code className="bg-slate-200 dark:bg-zinc-700/70 text-pink-600 dark:text-pink-400 px-1 py-0.5 rounded text-[11px] font-mono whitespace-pre-wrap" {...rest}>
                                  {children}
                                </code>
                              );
                            }

                            const codeString = String(children).replace(/\n$/, "");
                            const blockId = `${msg.id}-${match?.[1] || "code"}`;

                            return (
                              <div className="relative group my-3 rounded-lg overflow-hidden border border-slate-700">
                                <div className="flex items-center justify-between px-3 py-1 bg-[#1e1e1e] border-b border-slate-700/50 select-none">
                                  <span className="text-[10px] text-slate-400 font-mono lowercase">{match?.[1] || "text"}</span>
                                  <button
                                    type="button"
                                    onClick={() => handleCopyCode(codeString, blockId)}
                                    className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-emerald-400 transition-colors"
                                  >
                                    {copiedCodeId === blockId ? (
                                      <><Check size={12} /><span>Copied</span></>
                                    ) : (
                                      <><Copy size={12} /><span>Copy</span></>
                                    )}
                                  </button>
                                </div>
                                <SyntaxHighlighter
                                  {...rest}
                                  children={codeString}
                                  style={vscDarkPlus}
                                  language={match?.[1] || "text"}
                                  PreTag="div"
                                  customStyle={{ margin: 0, borderRadius: 0, fontSize: "0.75rem" }}
                                />
                              </div>
                            );
                          },
                          a: ({ node, href, children, ...props }) => {
                            if (href?.startsWith("#cite-")) {
                              const citeIdStr = href.replace("#cite-", "").trim();
                              const citationData = msg.citations?.find(c => String(c.id) === citeIdStr);

                              return (
                                <span className="relative inline-block mx-0.5 font-sans align-baseline">
                                  <a
                                    href={citationData?.url || undefined}
                                    target={citationData?.url ? "_blank" : undefined}
                                    rel="noopener noreferrer"
                                    onClick={(e) => {
                                      if (!citationData?.url) e.preventDefault();
                                    }}
                                    className={`inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold border rounded cursor-pointer transition-colors no-underline shadow-sm ${
                                      citationData
                                        ? "text-emerald-700 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-500/20 border-emerald-500/30 hover:bg-emerald-200 dark:hover:bg-emerald-500/40"
                                        : "text-slate-500 dark:text-slate-400 bg-slate-200 dark:bg-zinc-700 border-slate-300 dark:border-zinc-600"
                                    }`}
                                  >
                                    {children}
                                  </a>
                                </span>
                              );
                            }
                            return (
                              <a className="text-blue-600 dark:text-blue-400 hover:underline font-medium break-all" href={href} target="_blank" rel="noopener noreferrer" {...props}>
                                {children}
                              </a>
                            );
                          }
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>

                      {msg.isStreaming && (
                        <span className="inline-block ml-1 animate-pulse font-bold text-indigo-500">
                          ...
                        </span>
                      )}
                    </div>

                    {/* Citations / Sources */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-3 pt-2.5 border-t border-slate-200/60 dark:border-zinc-700/60 space-y-1.5">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                          Referenced Sources ({msg.citations.length})
                        </span>
                        <div className="flex flex-col gap-1">
                          {msg.citations.map((cite, idx) => (
                            <a
                              key={idx}
                              href={cite.url || "#"}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1.5 text-[11px] text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 hover:underline truncate"
                            >
                              <FileText size={12} className="shrink-0" />
                              <span className="truncate">{cite.file_name}</span>
                              {cite.url && <ExternalLink size={10} className="shrink-0 ml-auto" />}
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {msg.role === "user" && (
                    <div className="p-2 h-8 w-8 rounded-xl bg-slate-200 dark:bg-zinc-700 text-slate-600 dark:text-zinc-300 shrink-0 flex items-center justify-center mt-1">
                      <User size={18} />
                    </div>
                  )}
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Drawer Footer Input */}
          <div className="p-4 border-t border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                placeholder="Ask Luigi about findings, status, scope..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={isGenerating}
                className="flex-1 p-2.5 bg-slate-100 dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 rounded-xl text-xs border border-transparent focus:border-indigo-500 focus:bg-white dark:focus:bg-zinc-950 outline-none transition-all disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!input.trim() || isGenerating}
                className="p-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl transition-colors shrink-0 shadow-sm flex items-center justify-center"
              >
                {isGenerating ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Send size={16} />
                )}
              </button>
            </form>
          </div>

        </div>
      </div>
    </div>
  );
}