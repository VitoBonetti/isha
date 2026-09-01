import React, { useState, useRef, useEffect, useMemo } from 'react';
import { twMerge } from 'tailwind-merge';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { v4 as uuidv4 } from 'uuid';
import {
  Send, Trash2, Bot, User, Link as LinkIcon, FileText, Database,
  Box, Square, Copy, Check, MessageSquare, RefreshCw, Pencil, X, PanelLeft, Plus, CheckSquare, ListChecks,
  ThumbsUp, ThumbsDown
} from 'lucide-react';
import toast, { Toaster } from "react-hot-toast";
import { useAppContext } from "../context/AppContext";
import greenStainIcon from '../assets/greenstain-icon.png';
import type { Citation, Message, FilterItem, ChatSession, ExtendedMessage  } from "../types/board";
import ConfirmModal from '../components/Modals/ConfirmModal';

// Syntax Highlighter
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const ICEBREAKERS = [
  "Summarize the latest critical findings",
  "What is the scope of the recent adversary simulation?"
];

export default function RagChatPage() {
  const { currentUser } = useAppContext();
  const [sessionId, setSessionId] = useState<string>(uuidv4());
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // --- Sidebar & Sessions State ---
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [selectedSessions, setSelectedSessions] = useState<Set<string>>(new Set());

  // --- Modal State ---
  const [modalConfig, setModalConfig] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    confirmText?: string;
    variant?: 'danger' | 'warning' | 'info' | 'secure';
    onConfirm: () => void;
  }>({ isOpen: false, title: '', message: '', onConfirm: () => {} });

  // --- Chat State ---
  const initialWelcomeMessage: Message = {
    role: 'assistant',
    content: 'Hello! I am your Luigi Intelligence assistant. Use `/` for doc types, `@` for assets, and `$` for tests to narrow your search!',
    citations: [],
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  };

  const [messages, setMessages] = useState<ExtendedMessage[]>([initialWelcomeMessage]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | number | null>(null);

  // --- Inline Editing State ---
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editInput, setEditInput] = useState('');

  // --- Auto-Scroll State ---
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isUserScrolling, setIsUserScrolling] = useState(false);

  // --- Autocomplete State ---
  const [availableFilters, setAvailableFilters] = useState<FilterItem[]>([]);
  const [activeTrigger, setActiveTrigger] = useState<string | null>(null);
  const [menuQuery, setMenuQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [totalSources, setTotalSources] = useState<number>(0);

  const [selectedDocType, setSelectedDocType] = useState<string | null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [selectedTestId, setSelectedTestId] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/rag/filters').then(res => res.json()).then(data => setAvailableFilters(data)).catch(err => console.error("Failed to load filters", err));
    fetch('/api/rag/stats').then(res => res.json()).then(data => setTotalSources(data.total_sources)).catch(err => console.error("Failed to load stats", err));
    loadSessions();

    const handleResize = () => {
    // Auto-close on small screens when shrinking, but do NOT auto-open on desktop
    if (window.innerWidth < 768 && isSidebarOpen) setIsSidebarOpen(false);
  };
  window.addEventListener('resize', handleResize);
  return () => window.removeEventListener('resize', handleResize);
}, [isSidebarOpen]);

  const loadSessions = () => {
    fetch('/api/rag/sessions')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setSessions(data);
      })
      .catch(err => console.error("Failed to load sessions", err));
  };

  const loadSessionHistory = async (targetSessionId: string) => {
    if (isSelectionMode) {
      toggleSessionSelection(targetSessionId);
      return;
    }

    try {
      setIsLoading(true);
      const res = await fetch(`/api/rag/sessions/${targetSessionId}`);
      if (!res.ok) throw new Error("Failed to fetch session history");
      const history = await res.json();

      setSessionId(targetSessionId);
      if (history.length > 0) {
        setMessages([initialWelcomeMessage, ...history]);
      } else {
        setMessages([initialWelcomeMessage]);
      }
      if (window.innerWidth < 768) setIsSidebarOpen(false);
    } catch (error) {
      toast.error("Failed to load chat history");
    } finally {
      setIsLoading(false);
    }
  };

  const toggleSelectionMode = () => {
    setIsSelectionMode(!isSelectionMode);
    setSelectedSessions(new Set());
  };

  const toggleSessionSelection = (id: string) => {
    const newSet = new Set(selectedSessions);
    if (newSet.has(id)) newSet.delete(id);
    else newSet.add(id);
    setSelectedSessions(newSet);
  };

  const handleBulkDelete = () => {
    if (selectedSessions.size === 0) return;

    setModalConfig({
      isOpen: true,
      title: 'Delete Selected Chats',
      message: `Are you sure you want to delete ${selectedSessions.size} selected session(s)? This action cannot be undone.`,
      confirmText: 'Delete',
      variant: 'danger',
      onConfirm: async () => {
        setModalConfig(prev => ({ ...prev, isOpen: false }));
        try {
          const ids = Array.from(selectedSessions);
          const res = await fetch(`/api/rag/sessions/bulk-delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_ids: ids })
          });
          if (!res.ok) throw new Error("Failed to delete sessions");

          setSessions(prev => prev.filter(s => !selectedSessions.has(s.session_id)));
          toast.success(`${selectedSessions.size} session(s) deleted`);

          if (selectedSessions.has(sessionId)) handleClearChat();
          toggleSelectionMode();
        } catch (error) {
          toast.error("Failed to delete sessions");
        }
      }
    });
  };

  const handleClearAllSessions = () => {
    setModalConfig({
      isOpen: true,
      title: 'Clear All History',
      message: 'Are you sure you want to permanently delete all chat history? This action cannot be undone.',
      confirmText: 'Clear All',
      variant: 'danger',
      onConfirm: async () => {
        setModalConfig(prev => ({ ...prev, isOpen: false }));
        try {
          const res = await fetch(`/api/rag/sessions/bulk-delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_ids: ["all"] })
          });
          if (!res.ok) throw new Error("Failed to clear sessions");

          setSessions([]);
          handleClearChat();
          toast.success("All history cleared");
        } catch (error) {
          toast.error("Failed to clear history");
        }
      }
    });
  };

  useEffect(() => {
    if (!isUserScrolling) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading, isUserScrolling]);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setIsUserScrolling(!isAtBottom);
  };

  const filteredMenuOptions = useMemo(() => {
    if (!activeTrigger) return [];
    return availableFilters
      .filter(f => f.trigger === activeTrigger && f.name.toLowerCase().includes(menuQuery.toLowerCase()))
      .slice(0, 5);
  }, [activeTrigger, menuQuery, availableFilters]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setInput(val);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;

    const match = val.match(/(?:^|\s)([@$/])([a-zA-Z0-9_-]*)$/);
    if (match) {
      setActiveTrigger(match[1]);
      setMenuQuery(match[2]);
      setSelectedIndex(0);
    } else {
      setActiveTrigger(null);
    }
  };

  const applyFilterSelection = (item: FilterItem) => {
    const newVal = input.replace(/(?:^|\s)([@$/])[a-zA-Z0-9_-]*$/, ` $1${item.name} `).trimStart();
    setInput(newVal);
    setActiveTrigger(null);
    if (item.type === 'doc_type') setSelectedDocType(item.id);
    if (item.type === 'asset') setSelectedAssetId(item.id);
    if (item.type === 'test') setSelectedTestId(item.id);
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (activeTrigger && filteredMenuOptions.length > 0) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIndex((prev) => (prev + 1) % filteredMenuOptions.length); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSelectedIndex((prev) => (prev - 1 + filteredMenuOptions.length) % filteredMenuOptions.length); return; }
      if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); applyFilterSelection(filteredMenuOptions[selectedIndex]); return; }
      if (e.key === 'Escape') { setActiveTrigger(null); return; }
    }

    if (e.key === 'Backspace' && !activeTrigger) {
      const cursorPosition = textareaRef.current?.selectionStart;
      if (cursorPosition) {
        const textBeforeCursor = input.substring(0, cursorPosition);
        const tagMatch = textBeforeCursor.match(/(^|\s)([@$/][^\s]+)\s?$/);
        if (tagMatch) {
          e.preventDefault();
          const fullMatch = tagMatch[0];
          const tagToDelete = tagMatch[2];
          const newInput = input.substring(0, cursorPosition - fullMatch.length + (tagMatch[1] ? 1 : 0)) + input.substring(cursorPosition);
          setInput(newInput);
          if (tagToDelete.startsWith('/')) setSelectedDocType(null);
          if (tagToDelete.startsWith('@')) setSelectedAssetId(null);
          if (tagToDelete.startsWith('$')) setSelectedTestId(null);
          return;
        }
      }
    }

    if (e.key === 'Enter' && !e.shiftKey && !activeTrigger) {
      e.preventDefault();
      handleSend();
      if (textareaRef.current) textareaRef.current.style.height = 'auto';
    }
  };

  const handleClearChat = () => {
    setSessionId(uuidv4());
    setMessages([initialWelcomeMessage]);
    setSelectedDocType(null);
    setSelectedAssetId(null);
    setSelectedTestId(null);
    setEditingIndex(null);
    if (window.innerWidth < 768) setIsSidebarOpen(false);
  };

  const handleCopy = (text: string, id: string | number) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    toast.success('Copied to clipboard');
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleFeedback = async (index: number, logId: string, isGood: boolean) => {
    try {
      await fetch(`/api/rag/logs/${logId}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_good: isGood })
      });
      setMessages(prev => {
        const updated = [...prev];
        updated[index].feedback = isGood;
        return updated;
      });
      toast.success("Feedback submitted");
    } catch (error) {
      toast.error("Failed to submit feedback");
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
    }
  };

  const handleIcebreaker = (prompt: string) => {
    setInput(prompt);
    setTimeout(() => {
      handleSend(undefined, prompt);
    }, 0);
  };

  const executeChatStream = async (queryText: string, baseMessages: Message[]) => {
    setIsLoading(true);
    setIsUserScrolling(false);

    let finalDocType = selectedDocType;
    let finalAssetId = selectedAssetId;
    let finalTestId = selectedTestId;

    const usedDocType = availableFilters.find(f => f.id === selectedDocType);
    if (usedDocType && !queryText.includes(`/${usedDocType.name}`)) finalDocType = null;
    const usedAsset = availableFilters.find(f => f.id === selectedAssetId);
    if (usedAsset && !queryText.includes(`@${usedAsset.name}`)) finalAssetId = null;
    const usedTest = availableFilters.find(f => f.id === selectedTestId);
    if (usedTest && !queryText.includes(`$${usedTest.name}`)) finalTestId = null;

    setMessages(baseMessages);
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch('/api/rag/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: queryText,
          session_id: sessionId,
          doc_type: finalDocType,
          asset_id: finalAssetId,
          test_id: finalTestId
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) throw new Error(`Status ${response.status}`);
      if (!response.body) throw new Error("No readable stream available.");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = '';

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: '',
          citations: [],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);

      setIsLoading(false);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunkText = decoder.decode(value, { stream: true });
        const lines = chunkText.split('\n');

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            if (data.error) throw new Error(data.error);

            if (data.text) {
              assistantMessage += data.text;
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1].content = assistantMessage;
                return updated;
              });
            }

            if (data.citations) {
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1].citations = data.citations;
                if (data.log_id) updated[updated.length - 1].log_id = data.log_id; // Capture ID
                return updated;
              });
            }
          } catch (err) {
            console.error("Error parsing stream line:", line, err);
          }
        }
      }

      loadSessions();

    } catch (error: any) {
      if (error.name === 'AbortError') return;
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
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleSend = async (e?: React.FormEvent, overrideInput?: string) => {
    e?.preventDefault();
    const payloadQuery = (overrideInput || input).trim();
    if (!payloadQuery || isLoading) return;

    setInput('');
    setActiveTrigger(null);

    const newMessages: Message[] = [
      ...messages,
      {
        role: 'user',
        content: payloadQuery,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ];

    await executeChatStream(payloadQuery, newMessages);
  };

  const handleRegenerate = async (assistantIndex: number) => {
    if (isLoading) return;
    let userQuery = '';
    for (let i = assistantIndex - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        userQuery = messages[i].content;
        break;
      }
    }
    if (!userQuery) return;
    const truncated = messages.slice(0, assistantIndex);
    await executeChatStream(userQuery, truncated);
  };

  const startEditing = (index: number, currentText: string) => {
    setEditingIndex(index);
    setEditInput(currentText);
  };

  const saveEditing = async (index: number) => {
    if (!editInput.trim() || isLoading) return;
    const newText = editInput.trim();
    setEditingIndex(null);
    const truncated = messages.slice(0, index);
    const updatedUserMsg: Message = {
      role: 'user',
      content: newText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    await executeChatStream(newText, [...truncated, updatedUserMsg]);
  };

  return (
    <div className="flex h-[calc(100vh-12rem)] md:h-[calc(100vh-11rem)] w-full bg-white dark:bg-zinc-950 text-slate-800 dark:text-zinc-100 rounded-2xl shadow-xl border border-slate-200 dark:border-zinc-800/80 overflow-hidden relative">
      <Toaster position="bottom-right" />

      {/* CONFIRMATION MODAL */}
      <ConfirmModal
        isOpen={modalConfig.isOpen}
        title={modalConfig.title}
        message={modalConfig.message}
        confirmText={modalConfig.confirmText}
        variant={modalConfig.variant}
        onConfirm={modalConfig.onConfirm}
        onCancel={() => setModalConfig(prev => ({ ...prev, isOpen: false }))}
      />

      {/* MOBILE BACKDROP OVERLAY */}
      {isSidebarOpen && (
        <div
          className="md:hidden absolute inset-0 bg-slate-900/50 dark:bg-zinc-950/80 z-20 backdrop-blur-sm transition-opacity"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* --- COLLAPSIBLE LEFT SIDEBAR --- */}
      <div
        className={twMerge(
          "absolute md:relative flex flex-col bg-slate-50 dark:bg-zinc-900 border-r border-slate-200 dark:border-zinc-800 transition-all duration-300 z-30 h-full",
          isSidebarOpen ? "w-64 translate-x-0" : "w-0 -translate-x-full md:translate-x-0 overflow-hidden"
        )}
      >
        <div className="p-4 border-b border-slate-200 dark:border-zinc-800">
          <button
            onClick={handleClearChat}
            className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-bold shadow-sm transition-colors"
          >
            <Plus size={16} /> New Chat
          </button>
        </div>

        <div className="flex flex-col flex-1 overflow-hidden">
          <div className="flex items-center justify-between px-4 pt-3 pb-1">
            <div className="text-xs font-bold text-slate-400 dark:text-zinc-500 uppercase tracking-wider">Recent Chats</div>
            {sessions.length > 0 && (
              <button
                onClick={toggleSelectionMode}
                className="text-xs font-medium text-emerald-600 hover:text-emerald-500 transition-colors"
              >
                {isSelectionMode ? "Done" : "Select"}
              </button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {sessions.length === 0 && (
              <div className="text-xs text-slate-500 px-2 mt-2 italic">No recent history found.</div>
            )}
            {sessions.map(session => {
              const isSelected = selectedSessions.has(session.session_id);
              return (
                <button
                  key={session.session_id}
                  onClick={() => loadSessionHistory(session.session_id)}
                  className={twMerge(
                    "flex items-center gap-3 w-full text-left px-2 py-2.5 rounded-lg text-sm transition-colors group",
                    sessionId === session.session_id && !isSelectionMode
                      ? "bg-slate-200 dark:bg-zinc-800 text-slate-900 dark:text-white font-medium"
                      : "text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800/50"
                  )}
                >
                  {isSelectionMode ? (
                    <div className={twMerge(
                      "shrink-0 flex items-center justify-center w-4 h-4 rounded-sm border transition-colors",
                      isSelected
                        ? "bg-emerald-500 border-emerald-500 text-white"
                        : "border-slate-300 dark:border-zinc-600"
                    )}>
                      {isSelected && <Check size={12} strokeWidth={3} />}
                    </div>
                  ) : (
                    <MessageSquare size={14} className="shrink-0 opacity-70 group-hover:opacity-100" />
                  )}
                  <span className="truncate flex-1">{session.title}</span>
                </button>
              );
            })}
          </div>

          {/* BULK ACTIONS OR CLEAR ALL */}
          {sessions.length > 0 && (
            <div className="p-3 border-t border-slate-200 dark:border-zinc-800 shrink-0">
              {isSelectionMode ? (
                <div className="flex items-center justify-between gap-2">
                  <button
                    onClick={() => {
                      if (selectedSessions.size === sessions.length) {
                        setSelectedSessions(new Set());
                      } else {
                        setSelectedSessions(new Set(sessions.map(s => s.session_id)));
                      }
                    }}
                    className="p-2 text-slate-500 hover:text-slate-800 dark:hover:text-zinc-300 bg-slate-100 dark:bg-zinc-800 rounded-lg transition-colors"
                    title="Select All"
                  >
                    <ListChecks size={16} />
                  </button>
                  <button
                    onClick={handleBulkDelete}
                    disabled={selectedSessions.size === 0}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 text-xs font-medium text-white bg-red-600 hover:bg-red-500 disabled:bg-slate-300 dark:disabled:bg-zinc-800 disabled:text-slate-500 rounded-lg transition-colors"
                  >
                    <Trash2 size={14} /> Delete ({selectedSessions.size})
                  </button>
                </div>
              ) : (
                <button
                  onClick={handleClearAllSessions}
                  className="flex items-center justify-center gap-2 w-full px-4 py-2 text-xs font-medium text-slate-500 hover:text-red-600 hover:bg-red-50 dark:hover:text-red-400 dark:hover:bg-red-950/30 rounded-lg transition-colors"
                >
                  <Trash2 size={14} /> Clear All History
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* --- MAIN CHAT AREA --- */}
      <div className="flex flex-col flex-1 min-w-0 bg-white dark:bg-zinc-950 relative z-10">

        {/* HEADER */}
        <div className="flex items-center justify-between px-4 md:px-6 py-4 bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800 shadow-sm z-10">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="p-2 text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 bg-white dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 rounded-lg transition-colors mr-1 shadow-sm"
              title="Toggle Sidebar"
            >
              <PanelLeft size={18} />
            </button>
            <div className="hidden md:flex p-2 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-lg border border-emerald-500/20">
              <Bot size={20} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base md:text-lg font-bold text-slate-900 dark:text-zinc-100">LUIGI Intelligence</h2>
                <span className="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded uppercase tracking-wider border border-slate-200 dark:border-slate-700 shadow-sm">
                  {totalSources} Sources
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* MESSAGES VIEWPORT */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6 space-y-6" onScroll={handleScroll}>
          {messages.map((msg, index) => {
            const isUser = msg.role === 'user';
            const isEditingThis = editingIndex === index;
            const isCurrentlyStreaming = isLoading && index === messages.length - 1;

            return (
              <div
                key={index}
                className={twMerge(
                  'flex gap-3 md:gap-4 max-w-3xl leading-relaxed text-sm',
                  isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'
                )}
              >
                {/* AVATAR */}
                <div
                  className={twMerge(
                    'w-8 h-8 md:w-9 md:h-9 rounded-full flex items-center justify-center shrink-0 shadow-sm font-bold text-sm mt-1',
                    isUser
                      ? 'bg-gradient-to-tr from-emerald-500 to-indigo-500 text-white'
                      : 'bg-slate-100 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 p-1 md:p-1.5'
                  )}
                >
                  {isUser ? (
                    currentUser?.name ? currentUser.name.charAt(0).toUpperCase() : <User size={16} />
                  ) : (
                    <img src={greenStainIcon} alt="Luigi Logo" className="w-full h-full object-contain" />
                  )}
                </div>

                {/* CHAT BUBBLE */}
                <div
                  className={twMerge(
                    'flex flex-col gap-2 rounded-2xl px-4 md:px-5 py-3 md:py-4 shadow-sm relative min-w-[140px]',
                    isUser
                      ? 'bg-slate-100 dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 rounded-tr-none border border-slate-200 dark:border-zinc-700'
                      : twMerge(
                          'bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-slate-800 dark:text-zinc-300 rounded-tl-none',
                          msg.isError && 'border-red-300 dark:border-red-500/40 bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-300'
                        )
                  )}
                >
                  {/* INLINE EDIT MODE FOR USER */}
                  {isEditingThis ? (
                    <div className="flex flex-col gap-2 w-full min-w-[200px] md:min-w-[280px]">
                      <textarea
                        value={editInput}
                        onChange={(e) => setEditInput(e.target.value)}
                        className="w-full p-2.5 text-sm bg-white dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 rounded-lg border border-emerald-500 focus:outline-none resize-none"
                        rows={3}
                      />
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => setEditingIndex(null)}
                          className="px-2.5 py-1 text-xs text-slate-500 hover:text-slate-700 dark:hover:text-zinc-300 flex items-center gap-1"
                        >
                          <X size={12} /> Cancel
                        </button>
                        <button
                          onClick={() => saveEditing(index)}
                          className="px-3 py-1 text-xs bg-emerald-600 hover:bg-emerald-500 text-white rounded-md font-medium transition-colors"
                        >
                          Save & Submit
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="text-sm leading-relaxed break-words">
                      <ReactMarkdown
                        urlTransform={(url) => url}
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p: ({ node, ...props }) => <p className="mb-3 last:mb-0" {...props} />,
                          strong: ({ node, ...props }) => <strong className="font-semibold text-slate-950 dark:text-white" {...props} />,
                          ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-3 space-y-1" {...props} />,
                          ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-3 space-y-1" {...props} />,
                          li: ({ node, ...props }) => <li className="text-slate-800 dark:text-zinc-300" {...props} />,
                          table: ({ node, ...props }) => (
                            <div className="overflow-x-auto hover:overflow-visible mb-4 border border-slate-200 dark:border-zinc-700 rounded-lg">
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

                          code(props) {
                            const {children, className, node, ...rest} = props;
                            const match = /language-(\w+)/.exec(className || '');
                            const isInline = !match && !String(children).includes('\n');

                            if (isInline) {
                              return (
                                <code className="bg-slate-200 dark:bg-zinc-800 text-pink-600 dark:text-pink-400 px-1.5 py-0.5 rounded text-[11px] font-mono whitespace-pre-wrap" {...rest}>
                                  {children}
                                </code>
                              );
                            }

                            const codeString = String(children).replace(/\n$/, '');
                            const blockId = `${index}-${match?.[1] || 'code'}`;

                            return (
                              <div className="relative group my-4 rounded-lg overflow-hidden border border-slate-700">
                                <div className="flex items-center justify-between px-4 py-1.5 bg-[#1e1e1e] border-b border-slate-700/50 select-none">
                                  <span className="text-[10px] text-slate-400 font-mono lowercase">{match?.[1] || 'text'}</span>
                                  <button
                                    onClick={() => handleCopy(codeString, blockId)}
                                    className="flex items-center gap-1.5 text-[10px] text-slate-400 hover:text-emerald-400 transition-colors"
                                  >
                                    {copiedId === blockId ? (
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
                                  language={match?.[1] || 'text'}
                                  PreTag="div"
                                  customStyle={{ margin: 0, borderRadius: 0, fontSize: '0.75rem' }}
                                />
                              </div>
                            );
                          },

                          a: ({ node, href, children, ...props }) => {
                            if (href?.startsWith('#cite-')) {
                              const citeIdStr = href.replace('#cite-', '').trim();
                              const citationData = msg.citations?.find(c => String(c.id) === citeIdStr);
                              const isCurrentlyStreaming = isLoading && index === messages.length - 1;

                              return (
                                <span
                                  className="relative inline-block hover-group mx-0.5 font-sans align-baseline hover:z-50"
                                  onMouseEnter={(e) => {
                                    const tooltip = e.currentTarget.querySelector('.citation-tooltip');
                                    if (tooltip) tooltip.classList.remove('invisible', 'opacity-0');
                                  }}
                                  onMouseLeave={(e) => {
                                    const tooltip = e.currentTarget.querySelector('.citation-tooltip');
                                    if (tooltip) tooltip.classList.add('invisible', 'opacity-0');
                                  }}
                                >
                                  <a
                                    href={citationData?.url || undefined}
                                    target={citationData?.url ? "_blank" : undefined}
                                    rel="noopener noreferrer"
                                    onClick={(e) => {
                                      if (!citationData?.url) {
                                        e.preventDefault();
                                        if (!isCurrentlyStreaming) toast("Source link unavailable in chat history", { icon: "🗄️" });
                                      }
                                    }}
                                    className={twMerge(
                                      "inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold border rounded cursor-pointer transition-colors no-underline shadow-sm",
                                      citationData
                                        ? "text-emerald-700 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-500/20 border-emerald-500/30 hover:bg-emerald-200 dark:hover:bg-emerald-500/40"
                                        : "text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-zinc-800 border-slate-300 dark:border-zinc-700 hover:bg-slate-200 dark:hover:bg-zinc-700"
                                    )}
                                  >
                                    {children}
                                  </a>

                                  {citationData ? (
                                    <span className="citation-tooltip absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max max-w-[240px] sm:max-w-xs p-2.5 bg-slate-900 dark:bg-zinc-100 text-slate-100 dark:text-zinc-900 text-xs rounded-xl shadow-xl opacity-0 invisible transition-all duration-200 z-[100] pointer-events-none flex flex-col text-left font-normal normal-case">
                                      <span className="font-bold flex items-center gap-1.5 text-xs text-emerald-400 dark:text-emerald-600">
                                        <LinkIcon size={12} className="shrink-0" />
                                        <span className="truncate">{citationData.file_name}</span>
                                      </span>
                                      <span className="mt-1 text-[10px] text-slate-400 dark:text-slate-500 font-semibold text-right block">
                                        Click to open document ↗
                                      </span>
                                      {/* The centered triangle pointer */}
                                      <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-slate-900 dark:bg-zinc-100 rotate-45 block"></span>
                                    </span>
                                  ) : (
                                    <span className="citation-tooltip absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max px-2.5 py-1.5 bg-slate-900 dark:bg-zinc-100 text-slate-100 dark:text-zinc-900 text-[10px] rounded-lg shadow-xl opacity-0 invisible transition-all z-[100] pointer-events-none">
                                      {isCurrentlyStreaming ? "Processing source..." : `Source [${citeIdStr}] (Archived)`}
                                    </span>
                                  )}
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
                    </div>
                  )}

                  {/* CITATIONS SUMMARY (Collapsible Accordion) */}
                  {!isEditingThis && msg.citations && msg.citations.length > 0 && (
                    <details className="mt-3 pt-3 border-t border-slate-200 dark:border-zinc-800 group">
                      <summary className="text-[11px] font-bold uppercase tracking-wider text-slate-500 hover:text-emerald-600 dark:text-zinc-500 dark:hover:text-emerald-400 cursor-pointer list-none flex items-center gap-1.5 select-none transition-colors">
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          width="12" height="12"
                          viewBox="0 0 24 24" fill="none"
                          stroke="currentColor" strokeWidth="2"
                          strokeLinecap="round" strokeLinejoin="round"
                          className="group-open:rotate-90 transition-transform duration-200"
                        >
                          <path d="m9 18 6-6-6-6"/>
                        </svg>
                        {msg.citations.length} Source{msg.citations.length !== 1 && 's'}
                      </summary>

                      <div className="flex flex-wrap gap-2 mt-3 animate-in fade-in slide-in-from-top-1 duration-200">
                        {msg.citations.map((cite) => (
                          <a
                            key={cite.id}
                            href={cite.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 text-xs bg-slate-50 dark:bg-zinc-950 hover:bg-slate-100 dark:hover:bg-zinc-800 text-blue-600 dark:text-blue-400 px-2.5 py-1 rounded-md border border-slate-200 dark:border-zinc-700 transition-colors"
                          >
                            <FileText size={12} />
                            <span className="font-bold text-emerald-600">[{cite.id}]</span>
                            <span className="truncate max-w-[200px]">{cite.file_name}</span>
                          </a>
                        ))}
                      </div>
                    </details>
                  )}

                  {/* FOOTER ACTIONS: EDIT, REGENERATE, COPY, TIMESTAMP */}
                  {!isEditingThis && (
                    <div className="flex items-center justify-end gap-3 mt-1 pt-1">
                      {isUser && (
                        <button
                          onClick={() => startEditing(index, msg.content)}
                          disabled={isLoading}
                          className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors disabled:opacity-30"
                          title="Edit prompt"
                        >
                          <Pencil size={12} />
                          <span>Edit</span>
                        </button>
                      )}

                      {!isUser && index > 0 && (
                        <button
                          onClick={() => handleRegenerate(index)}
                          disabled={isLoading}
                          className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors disabled:opacity-30"
                          title="Regenerate response"
                        >
                          <RefreshCw size={12} className={isLoading ? "animate-spin" : ""} />
                          <span>Retry</span>
                        </button>
                      )}

                      <button
                        onClick={() => handleCopy(msg.content, index)}
                        className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors"
                        title="Copy message text"
                      >
                        {copiedId === index ? (
                          <><Check size={12} className="text-emerald-500" /><span className="text-emerald-500 font-medium">Copied</span></>
                        ) : (
                          <><Copy size={12} /><span>Copy</span></>
                        )}
                      </button>

                      {!isUser && msg.log_id && (
                        <>
                          <button
                            onClick={() => handleFeedback(index, msg.log_id!, true)}
                            disabled={isLoading}
                            className={twMerge(
                              "flex items-center gap-1 text-[10px] transition-colors disabled:opacity-30",
                              msg.feedback === true
                                ? "text-emerald-600 dark:text-emerald-400"
                                : "text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400"
                            )}
                            title="Good response"
                          >
                            <ThumbsUp size={12} className={msg.feedback === true ? "fill-current" : ""} />
                          </button>

                          <button
                            onClick={() => handleFeedback(index, msg.log_id!, false)}
                            disabled={isLoading}
                            className={twMerge(
                              "flex items-center gap-1 text-[10px] transition-colors disabled:opacity-30",
                              msg.feedback === false
                                ? "text-red-500 dark:text-red-400"
                                : "text-slate-400 hover:text-red-500 dark:hover:text-red-400"
                            )}
                            title="Bad response"
                          >
                            <ThumbsDown size={12} className={msg.feedback === false ? "fill-current" : ""} />
                          </button>

                          <span className="w-px h-3 bg-slate-300 dark:bg-zinc-700 mx-1"></span>
                        </>
                      )}

                      <span
                        className={twMerge(
                          'text-[10px]',
                          isUser ? 'text-slate-400 dark:text-zinc-500' : 'text-slate-400 dark:text-zinc-600'
                        )}
                      >
                        {msg.timestamp}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* ICEBREAKER PROMPTS */}
          {messages.length === 1 && !isLoading && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-3xl mt-4 animate-in fade-in slide-in-from-bottom-2">
              {ICEBREAKERS.map((prompt, idx) => (
                <button
                  key={idx}
                  onClick={() => handleIcebreaker(prompt)}
                  className="flex items-center gap-3 p-4 text-left bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 hover:border-emerald-500 dark:hover:border-emerald-500 rounded-xl shadow-sm hover:shadow-md transition-all group"
                >
                  <MessageSquare size={16} className="text-emerald-500 shrink-0 opacity-70 group-hover:opacity-100" />
                  <span className="text-sm text-slate-700 dark:text-zinc-300 font-medium">{prompt}</span>
                </button>
              ))}
            </div>
          )}

          {/* LOADING INDICATOR */}
          {isLoading && (
            <div className="flex gap-4 max-w-3xl mr-auto mt-2">
              <div className="w-9 h-9 rounded-full bg-slate-100 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 flex items-center justify-center p-1.5 shrink-0">
                <img src={greenStainIcon} alt="Luigi Logo" className="w-full h-full object-contain animate-pulse" />
              </div>
              <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl rounded-tl-none px-5 py-4 flex items-center gap-2 shadow-sm">
                <span className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce"></span>
                <span className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></span>
                <span className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* INPUT FORM WITH AUTOCOMPLETE */}
        <form onSubmit={handleSend} className="p-4 bg-slate-50 dark:bg-zinc-900/50 border-t border-slate-200 dark:border-zinc-800 relative z-20">

          {/* THE COMMAND MENU POPUP */}
          {activeTrigger && filteredMenuOptions.length > 0 && (
            <div className="absolute bottom-full mb-2 left-4 w-72 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 shadow-xl rounded-xl overflow-hidden animate-in fade-in slide-in-from-bottom-2">
              <div className="px-3 py-2 bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800 text-xs font-semibold text-slate-500 dark:text-zinc-400 uppercase tracking-wider">
                {activeTrigger === '/' ? 'Filter by Document Type' : activeTrigger === '@' ? 'Filter by Asset' : 'Filter by Test'}
              </div>
              <ul className="max-h-48 overflow-y-auto">
                {filteredMenuOptions.map((item, idx) => (
                  <li
                    key={item.id}
                    className={twMerge(
                      "px-4 py-2.5 flex items-center gap-3 cursor-pointer transition-colors text-sm",
                      idx === selectedIndex
                        ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                        : "text-slate-700 dark:text-zinc-300 hover:bg-slate-50 dark:hover:bg-zinc-800"
                    )}
                    onClick={() => applyFilterSelection(item)}
                  >
                    {item.type === 'doc_type' ? <FileText size={16} className="text-emerald-500" /> : item.type === 'asset' ? <Database size={16} className="text-blue-500" /> : <Box size={16} className="text-amber-500" />}
                    <span className="truncate">{item.name}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="relative flex items-end">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question... Use / for documents, @ for assets, $ for tests"
              className="w-full bg-white dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 placeholder-slate-400 dark:placeholder-zinc-600 text-sm rounded-3xl pl-6 pr-14 py-4 border border-slate-300 dark:border-zinc-700 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 resize-none overflow-y-auto [&::-webkit-scrollbar]:hidden"
              rows={1}
              style={{ minHeight: '54px', maxHeight: '200px' }}
            />
            {/* TOGGLE BUTTON: STOP vs SEND */}
            {isLoading && abortControllerRef.current ? (
              <button
                type="button"
                onClick={handleStop}
                className="absolute right-2 bottom-2 p-2 text-slate-400 bg-white dark:bg-zinc-950 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 border border-slate-200 dark:border-zinc-700 rounded-full transition-all mb-[5px] shadow-sm"
                title="Stop Generating"
              >
                <Square size={16} fill="currentColor" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim() || isLoading}
                className="absolute right-2 bottom-2 p-2 text-white bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:hover:bg-emerald-600 rounded-full transition-all mb-[5px]"
              >
                <Send size={18} />
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}