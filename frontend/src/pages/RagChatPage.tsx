import React, { useState, useRef, useEffect } from 'react';
import { twMerge } from 'tailwind-merge';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { v4 as uuidv4 } from 'uuid';
import { Send, Trash2, Bot, User, Link as LinkIcon } from 'lucide-react';
import type { Citation, Message } from "../types/board";
import toast, { Toaster } from "react-hot-toast";
import { useAppContext } from "../context/AppContext";


export default function RagChatPage() {
  const [sessionId, setSessionId] = useState<string>(uuidv4());
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Hello! I am your Luigi Intelligence assistant. Ask me anything about findings, methodologies, or reports across your pentest workspace.',
      citations: [],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleClearChat = () => {
    setSessionId(uuidv4());
    setMessages([
      {
        role: 'assistant',
        content: 'Session cleared. Starting a new conversation. How can I help?',
        citations: [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  };

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');

    const newMessages: Message[] = [
      ...messages,
      {
        role: 'user',
        content: userMessage,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ];

    setMessages(newMessages);
    setIsLoading(true);

    try {
      const response = await fetch('/api/rag/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMessage, session_id: sessionId }),
      });

      if (!response.ok) throw new Error(`Status ${response.status}`);
      if (!response.body) throw new Error("No readable stream available.");

      // Setup the stream reader
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = '';

      // Immediately append an empty assistant message to the UI to hold the stream
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: '',
          citations: [],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);

      // Stop the bouncing loading dots since the stream is starting
      setIsLoading(false);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunkText = decoder.decode(value, { stream: true });

        // Split by newline because multiple JSON lines might arrive in a single packet
        const lines = chunkText.split('\n');

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const data = JSON.parse(line);

            if (data.error) {
              throw new Error(data.error);
            }

            // Append text tokens to the message content
            if (data.text) {
              assistantMessage += data.text;
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1].content = assistantMessage;
                return updated;
              });
            }

            // Apply final citations when the stream ends
            if (data.citations) {
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1].citations = data.citations;
                return updated;
              });
            }
          } catch (err) {
            console.error("Error parsing stream line:", line, err);
          }
        }
      }
    } catch (error: any) {
      setIsLoading(false);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `⚠️ Error fetching response: ${error.message}`,
          citations: [],
          isError: true,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-12rem)] md:h-[calc(100vh-11rem)] w-full bg-white dark:bg-zinc-950 text-slate-800 dark:text-zinc-100 rounded-2xl shadow-xl border border-slate-200 dark:border-zinc-800/80 overflow-hidden">
      <Toaster position="bottom-right" />

      {/* HEADER */}
      <div className="flex items-center justify-between px-6 py-4 bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-lg border border-emerald-500/20">
            <Bot size={24} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900 dark:text-zinc-100">LUIGI Intelligence</h2>
              <span className="px-1.5 py-0.5 text-[10px] font-bold bg-amber-100 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 rounded uppercase tracking-wider">
                Admin Only
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-zinc-400">Global Knowledge Base Search</p>
          </div>
        </div>

        <button
          onClick={handleClearChat}
          className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-lg transition-colors"
          title="Clear Chat"
        >
          <Trash2 size={20} />
        </button>
      </div>

        {/* MESSAGES VIEWPORT */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg, index) => {
            const isUser = msg.role === 'user';
            return (
              <div
                key={index}
                className={twMerge(
                  'flex gap-4 max-w-3xl leading-relaxed text-sm',
                  isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'
                )}
              >
                {/* AVATAR */}
                <div
                  className={twMerge(
                    'w-9 h-9 rounded-full flex items-center justify-center shrink-0 shadow-sm',
                    isUser
                      ? 'bg-gradient-to-tr from-emerald-500 to-indigo-500 text-white'
                      : 'bg-slate-100 dark:bg-zinc-800 text-emerald-600 dark:text-emerald-400 border border-slate-200 dark:border-zinc-700'
                  )}
                >
                  {isUser ? <User size={16} /> : <Bot size={18} />}
                </div>

                {/* CHAT BUBBLE */}
                <div
                  className={twMerge(
                    'flex flex-col gap-2 rounded-2xl px-5 py-4 shadow-sm relative',
                    isUser
                      ? 'bg-slate-100 dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 rounded-tr-none border border-slate-200 dark:border-zinc-700'
                      : twMerge(
                          'bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-slate-800 dark:text-zinc-300 rounded-tl-none',
                          msg.isError && 'border-red-300 dark:border-red-500/40 bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-300'
                        )
                  )}
                >
                  <div className="text-sm leading-relaxed">
                    <ReactMarkdown
                      urlTransform={(url) => url}
                      remarkPlugins={[remarkGfm]}
                      components={{
                        p: ({ node, ...props }) => <p className="mb-3 last:mb-0" {...props} />,
                        strong: ({ node, ...props }) => <strong className="font-semibold text-slate-950 dark:text-white" {...props} />,
                        ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-3 space-y-1" {...props} />,
                        ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-3 space-y-1" {...props} />,
                        li: ({ node, ...props }) => <li className="text-slate-800 dark:text-zinc-300" {...props} />,

                        // NEW: Table Renderers
                        table: ({ node, ...props }) => (
                          <div className="overflow-x-auto mb-4 border border-slate-200 dark:border-zinc-700 rounded-lg">
                            <table className="min-w-full divide-y divide-slate-200 dark:divide-zinc-700 text-sm" {...props} />
                          </div>
                        ),
                        thead: ({ node, ...props }) => <thead className="bg-slate-100 dark:bg-zinc-800" {...props} />,
                        th: ({ node, ...props }) => (
                          <th className="px-4 py-2.5 text-left font-semibold text-slate-900 dark:text-zinc-100 border-b border-slate-200 dark:border-zinc-700" {...props} />
                        ),
                        td: ({ node, ...props }) => (
                          <td className="px-4 py-2 border-t border-slate-200 dark:border-zinc-700/50" {...props} />
                        ),

                        // CUSTOM INTERACTIVE CITATION CHIP RENDERER (Snippet Removed)
                        a: ({ node, href, children, ...props }) => {
                          if (href?.startsWith('#cite-')) {
                            const citeIdStr = href.replace('#cite-', '').trim();
                            const citationData = msg.citations?.find(c => String(c.id) === citeIdStr);

                            return (
                              <span className="relative inline-block group mx-0.5 font-sans align-baseline">
                                <a
                                  href={citationData?.url || undefined}
                                  target={citationData?.url ? "_blank" : undefined}
                                  rel="noopener noreferrer"
                                  onClick={(e) => {
                                    if (!citationData?.url) {
                                      e.preventDefault();
                                    }
                                  }}
                                  className="inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-500/20 border border-emerald-500/30 rounded cursor-pointer hover:bg-emerald-200 dark:hover:bg-emerald-500/40 transition-colors no-underline shadow-sm"
                                >
                                  {children}
                                </a>

                                {/* HOVER TOOLTIP CARD (Simplified) */}
                                {citationData ? (
                                  <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max max-w-xs p-2.5 bg-slate-900 dark:bg-zinc-100 text-slate-100 dark:text-zinc-900 text-xs rounded-xl shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-[100] pointer-events-none flex flex-col text-left font-normal normal-case">
                                    <span className="font-bold flex items-center gap-1.5 text-xs text-emerald-400 dark:text-emerald-600">
                                      <LinkIcon size={12} className="shrink-0" />
                                      <span className="truncate">{citationData.file_name}</span>
                                    </span>
                                    <span className="mt-1 text-[10px] text-slate-400 dark:text-slate-500 font-semibold text-right block">
                                      Click to open document ↗
                                    </span>
                                    <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-slate-900 dark:bg-zinc-100 rotate-45 block"></span>
                                  </span>
                                ) : (
                                  <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max px-2.5 py-1.5 bg-slate-900 dark:bg-zinc-100 text-slate-100 dark:text-zinc-900 text-[10px] rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-[100] pointer-events-none">
                                    Processing source...
                                  </span>
                                )}
                              </span>
                            );
                          }

                          // Standard web links
                          return (
                            <a
                              className="text-blue-600 dark:text-blue-400 hover:underline font-medium break-all"
                              href={href}
                              target="_blank"
                              rel="noopener noreferrer"
                              {...props}
                            >
                              {children}
                            </a>
                          );
                        },
                        code: ({ node, ...props }) => <code className="bg-slate-200 dark:bg-zinc-800 text-pink-600 dark:text-pink-400 px-1.5 py-0.5 rounded text-xs font-mono" {...props} />,
                        pre: ({ node, ...props }) => <pre className="bg-slate-800 text-slate-50 p-3 rounded-lg overflow-x-auto text-xs mb-3" {...props} />,
                        h1: ({ node, ...props }) => <h1 className="text-lg font-bold mb-2 mt-4 text-slate-900 dark:text-white" {...props} />,
                        h2: ({ node, ...props }) => <h2 className="text-base font-bold mb-2 mt-3 text-slate-900 dark:text-white" {...props} />,
                        h3: ({ node, ...props }) => <h3 className="text-sm font-bold mb-2 mt-3 text-slate-900 dark:text-white" {...props} />
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>

                  {/* CITATIONS SUMMARY LIST AT BOTTOM */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-200 dark:border-zinc-800">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-zinc-500 block mb-2">
                        Sources
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {msg.citations.map((cite) => (
                          <a
                            key={cite.id}
                            href={cite.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 text-xs bg-slate-50 dark:bg-zinc-950 hover:bg-slate-100 dark:hover:bg-zinc-800 text-blue-600 dark:text-blue-400 px-2.5 py-1 rounded-md border border-slate-200 dark:border-zinc-700 transition-colors"
                          >
                            <LinkIcon size={12} />
                            <span className="font-bold text-emerald-600">[{cite.id}]</span>
                            <span className="truncate max-w-[200px]">{cite.file_name}</span>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}

                  <span
                    className={twMerge(
                      'text-[10px] self-end mt-1',
                      isUser ? 'text-slate-400 dark:text-zinc-500' : 'text-slate-400 dark:text-zinc-600'
                    )}
                  >
                    {msg.timestamp}
                  </span>
                </div>
              </div>
            );
          })}

          {/* LOADING INDICATOR */}
          {isLoading && (
            <div className="flex gap-4 max-w-3xl mr-auto">
              <div className="w-9 h-9 rounded-full bg-slate-100 dark:bg-zinc-800 text-emerald-600 dark:text-emerald-400 border border-slate-200 dark:border-zinc-700 flex items-center justify-center shrink-0">
                <Bot size={18} />
              </div>
              <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl rounded-tl-none px-5 py-4 flex items-center gap-2">
                <span className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce"></span>
                <span className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></span>
                <span className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* INPUT FORM */}
        <form onSubmit={handleSend} className="p-4 bg-slate-50 dark:bg-zinc-900/50 border-t border-slate-200 dark:border-zinc-800">
          <div className="relative flex items-end">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                // Auto-resize magic
                e.target.style.height = 'auto';
                e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
              }}
              onKeyDown={(e) => {
                // Submit on Enter (unless Shift is held)
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend(e);
                  // Reset height after sending
                  if (textareaRef.current) {
                    textareaRef.current.style.height = 'auto';
                  }
                }
              }}
              placeholder="Ask a question about findings, scope, leads... (Shift+Enter for new line)"
              className="w-full bg-white dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 placeholder-slate-400 dark:placeholder-zinc-600 text-sm rounded-3xl pl-6 pr-14 py-4 border border-slate-300 dark:border-zinc-700 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 resize-none overflow-y-auto [&::-webkit-scrollbar]:hidden"
              rows={1}
              style={{ minHeight: '54px', maxHeight: '200px' }}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="absolute right-2 bottom-2 p-2 text-white bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:hover:bg-emerald-600 rounded-full transition-all mb-[5px]"
            >
              <Send size={18} />
            </button>
          </div>
        </form>
      </div>
  );
}