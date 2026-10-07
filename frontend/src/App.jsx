import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import {
  FolderGit2,
  Plus,
  Send,
  Sparkles,
  Bot,
  User,
  ExternalLink,
  ChevronRight,
  Code2,
  FileText,
  Search,
  Check,
  Copy,
  Loader2,
  AlertCircle,
  Terminal,
  Settings,
  LogOut,
  Layers,
  X,
  Menu,
  Database
} from "lucide-react";

export default function App() {
  // State
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [searchFilter, setSearchFilter] = useState("");
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isAddingRepo, setIsAddingRepo] = useState(false);
  const [newRepoUrl, setNewRepoUrl] = useState("");
  const [isIndexing, setIsIndexing] = useState(false);
  const [indexStatus, setIndexStatus] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [expandedSources, setExpandedSources] = useState({});
  const [showAuthModal, setShowAuthModal] = useState(false);

  const messagesEndRef = useRef(null);

  // Auto-scroll chat
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Load projects from backend
  const fetchProjects = async () => {
    try {
      const res = await fetch("/api/projects");
      if (res.ok) {
        const data = await res.json();
        setProjects(data.projects || []);
        // Auto-select first project if none selected
        if (!selectedProject && data.projects && data.projects.length > 0) {
          setSelectedProject(data.projects[0].name);
        }
      }
    } catch (err) {
      console.error("Failed to load projects:", err);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  // Handle Project Change
  const handleSelectProject = (projectName) => {
    setSelectedProject(projectName);
    setMessages([]);
    setErrorMsg("");
  };

  // Handle Add New Repo
  const handleAddRepo = async (e) => {
    e.preventDefault();
    if (!newRepoUrl.trim()) return;

    setIsIndexing(true);
    setIndexStatus("Connecting to GitHub API & downloading source files...");
    setErrorMsg("");

    try {
      const res = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: newRepoUrl.trim() }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Failed to index repository.");
      }

      setIndexStatus("Done! Chunks stored in Qdrant.");
      await fetchProjects();
      setSelectedProject(data.collection);
      setIsAddingRepo(false);
      setNewRepoUrl("");
      setMessages([
        {
          role: "assistant",
          content: `🎉 Successfully indexed **${data.repo_name}** with **${data.indexed_chunks} chunks** into Qdrant!\n\nYou can now ask me anything about the codebase.`,
        },
      ]);
    } catch (err) {
      setErrorMsg(err.message || "An error occurred while indexing.");
    } finally {
      setIsIndexing(false);
      setIndexStatus("");
    }
  };

  // Handle Send Message
  const handleSendMessage = async (e) => {
    if (e) e.preventDefault();
    if (!inputMessage.trim() || isLoading) return;

    if (!selectedProject) {
      setErrorMsg("Please select or add a repository first.");
      return;
    }

    const userText = inputMessage.trim();
    setInputMessage("");
    setErrorMsg("");

    // Add user message
    const newMsgList = [...messages, { role: "user", content: userText }];
    setMessages(newMsgList);
    setIsLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          collection: selectedProject,
          message: userText,
          top_k: 5,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Failed to get response.");
      }

      setMessages([
        ...newMsgList,
        {
          role: "assistant",
          content: data.answer,
          citations: data.citations || [],
        },
      ]);
    } catch (err) {
      setMessages([
        ...newMsgList,
        {
          role: "assistant",
          content: `⚠️ Error: ${err.message}`,
          isError: true,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = (text, idx) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const toggleSources = (msgIdx) => {
    setExpandedSources((prev) => ({
      ...prev,
      [msgIdx]: !prev[msgIdx],
    }));
  };

  // Filter projects
  const filteredProjects = projects.filter((p) =>
    p.name.toLowerCase().includes(searchFilter.toLowerCase())
  );

  return (
    <div className="flex h-screen w-screen bg-[#0a0a0c] text-[#ececec] font-sans overflow-hidden">
      {/* ───────────────────────────────────────────────────────────── */}
      {/* LEFT SIDEBAR                                                 */}
      {/* ───────────────────────────────────────────────────────────── */}
      <aside
        className={`${
          sidebarOpen ? "w-72" : "w-0"
        } transition-all duration-300 ease-in-out flex flex-col border-r border-[#1e1e24] bg-[#0f0f13] z-20 overflow-hidden shrink-0 select-none`}
      >
        {/* Brand Header */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-[#1c1c22]">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-orange-500/10 border border-orange-500/20 p-1 flex items-center justify-center shadow-md shadow-orange-500/10">
              <img src="/logo.png" alt="Gito Robot Logo" className="w-full h-full object-contain" />
            </div>
            <div>
              <div className="flex items-center gap-1.5 font-bold tracking-tight text-white text-base">
                Gito
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse"></span>
              </div>
              <div className="text-[10px] text-zinc-400 font-medium -mt-0.5 tracking-wider uppercase">
                GitHub Repo Agent
              </div>
            </div>
          </div>
        </div>

        {/* Action Button: Add Project */}
        <div className="p-3">
          <button
            onClick={() => setIsAddingRepo(true)}
            className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-[#191920] hover:bg-[#22222b] text-zinc-200 hover:text-white border border-[#2a2a35] hover:border-orange-500/50 transition-all text-xs font-semibold group cursor-pointer shadow-sm"
          >
            <Plus className="w-4 h-4 text-orange-500 group-hover:scale-110 transition-transform" />
            <span>Add New Repository</span>
          </button>
        </div>

        {/* Project Search Filter */}
        <div className="px-3 pb-2">
          <div className="relative flex items-center">
            <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 pointer-events-none" />
            <input
              type="text"
              placeholder="Search projects..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="w-full bg-[#141418] border border-[#22222a] rounded-md pl-8 pr-3 py-1.5 text-xs text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-orange-500/60 transition-colors"
            />
          </div>
        </div>

        {/* Projects List */}
        <div className="flex-1 overflow-y-auto px-2 space-y-1 py-1">
          <div className="px-2 py-1 text-[10px] font-semibold tracking-wider text-zinc-500 uppercase">
            Indexed Repositories ({filteredProjects.length})
          </div>

          {filteredProjects.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-zinc-500">
              No repositories found.
            </div>
          ) : (
            filteredProjects.map((proj) => {
              const isSelected = selectedProject === proj.name;
              return (
                <button
                  key={proj.name}
                  onClick={() => handleSelectProject(proj.name)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-left text-xs transition-all group cursor-pointer ${
                    isSelected
                      ? "bg-[#1f1f28] text-white font-medium border-l-2 border-orange-500 shadow-sm"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-[#16161c]"
                  }`}
                >
                  <div className="flex items-center gap-2.5 truncate">
                    <Database
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isSelected ? "text-orange-500" : "text-zinc-500 group-hover:text-zinc-400"
                      }`}
                    />
                    <span className="truncate">{proj.name}</span>
                  </div>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full shrink-0 ${
                      isSelected
                        ? "bg-orange-500/20 text-orange-400"
                        : "bg-[#1d1d24] text-zinc-500 group-hover:text-zinc-400"
                    }`}
                  >
                    {proj.count}
                  </span>
                </button>
              );
            })
          )}
        </div>

        {/* Bottom User Profile Section (Auth Placeholder) */}
        <div className="p-3 border-t border-[#1c1c22] bg-[#0c0c0f]">
          <div
            onClick={() => setShowAuthModal(true)}
            className="flex items-center justify-between p-2 rounded-lg hover:bg-[#181820] cursor-pointer transition-colors group"
          >
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-orange-600 to-amber-500 text-white flex items-center justify-center font-bold text-xs ring-1 ring-orange-500/40">
                MY
              </div>
              <div className="truncate">
                <div className="text-xs font-semibold text-zinc-200 group-hover:text-white truncate">
                  Mohan Yadav
                </div>
                <div className="text-[10px] text-zinc-500 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  Ready to Authenticate
                </div>
              </div>
            </div>
            <Settings className="w-3.5 h-3.5 text-zinc-500 group-hover:text-zinc-300 transition-colors" />
          </div>
        </div>
      </aside>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* MAIN CHAT & WORKSPACE AREA                                   */}
      {/* ───────────────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col h-full bg-[#0a0a0c] relative overflow-hidden">
        {/* Top Navbar */}
        <header className="h-14 border-b border-[#18181f] flex items-center justify-between px-4 z-10 bg-[#0a0a0c]/80 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1.5 rounded-md hover:bg-[#181822] text-zinc-400 hover:text-white transition-colors cursor-pointer"
            >
              <Menu className="w-4 h-4" />
            </button>

            {selectedProject ? (
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-zinc-300">
                  {selectedProject}
                </span>
                <span className="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full font-mono">
                  Indexed
                </span>
              </div>
            ) : (
              <span className="text-xs text-zinc-500 font-medium">
                No repository selected
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <div className="text-xs text-zinc-500 hidden sm:flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-orange-500"></span>
              Hybrid RAG: BGE-Small + Qdrant
            </div>
          </div>
        </header>

        {/* Chat / Placeholder Content Area */}
        <div className="flex-1 overflow-y-auto px-4 py-6 flex flex-col items-center">
          {messages.length === 0 ? (
            /* ── CENTER PLACEHOLDER (ChatGPT-like minimal landing) ── */
            <div className="max-w-xl w-full my-auto flex flex-col items-center text-center animate-fade-in px-4">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-b from-orange-500/15 to-transparent border border-orange-500/30 p-2.5 flex items-center justify-center shadow-2xl shadow-orange-500/20 mb-4 transition-transform hover:scale-105 duration-300">
                <img src="/logo.png" alt="Gito Robot Logo" className="w-full h-full object-contain drop-shadow" />
              </div>

              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight mb-2">
                What would you like to explore?
              </h1>
              <p className="text-xs sm:text-sm text-zinc-400 max-w-md mb-8">
                Gito parses complete codebases, chunks AST functions, and answers with file-level citations.
              </p>

              {/* Sample Quick Questions */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full text-left">
                {[
                  {
                    title: "Architecture & Flow",
                    desc: "How does the core system work and what are the main modules?",
                  },
                  {
                    title: "Authentication & Security",
                    desc: "Where is auth handled and what middleware protects routes?",
                  },
                  {
                    title: "Database Models",
                    desc: "Show me the database schema and CRUD operations.",
                  },
                  {
                    title: "Setup & Run",
                    desc: "How do I install dependencies and run this project locally?",
                  },
                ].map((item, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setInputMessage(item.desc);
                    }}
                    className="p-3 rounded-xl bg-[#121217] hover:bg-[#181820] border border-[#202028] hover:border-orange-500/40 transition-all text-left group cursor-pointer"
                  >
                    <div className="text-xs font-semibold text-zinc-200 group-hover:text-orange-400 transition-colors flex items-center justify-between">
                      {item.title}
                      <ChevronRight className="w-3.5 h-3.5 text-zinc-600 group-hover:text-orange-400 group-hover:translate-x-0.5 transition-all" />
                    </div>
                    <div className="text-[11px] text-zinc-500 mt-1 line-clamp-2">
                      {item.desc}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* ── MESSAGE STREAM THREAD ── */
            <div className="w-full max-w-3xl space-y-6 pb-20">
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex gap-3.5 ${
                    msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  {msg.role === "assistant" && (
                    <div className="w-8 h-8 rounded-lg bg-orange-500/15 border border-orange-500/30 flex items-center justify-center shrink-0 mt-1 shadow-md shadow-orange-500/10 p-0.5">
                      <img src="/logo.png" alt="Gito" className="w-full h-full object-contain" />
                    </div>
                  )}

                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-xs sm:text-sm leading-relaxed ${
                      msg.role === "user"
                        ? "bg-[#22222b] text-white border border-[#2e2e3a]"
                        : "bg-[#131317] text-zinc-200 border border-[#202028] shadow-sm"
                    }`}
                  >
                    {/* Message Body with Markdown */}
                    <div className="prose prose-invert prose-xs sm:prose-sm max-w-none">
                      <ReactMarkdown
                        components={{
                          code({ node, inline, className, children, ...props }) {
                            const codeStr = String(children).replace(/\n$/, "");
                            if (inline) {
                              return (
                                <code
                                  className="bg-[#242430] text-orange-300 px-1 py-0.5 rounded text-[11px] font-mono"
                                  {...props}
                                >
                                  {children}
                                </code>
                              );
                            }
                            return (
                              <div className="relative my-2 rounded-lg bg-[#0d0d10] border border-[#22222a] overflow-hidden">
                                <div className="flex items-center justify-between px-3 py-1.5 bg-[#14141a] border-b border-[#22222a] text-[10px] text-zinc-400">
                                  <span>code</span>
                                  <button
                                    onClick={() => handleCopy(codeStr, `${idx}-${codeStr.slice(0, 5)}`)}
                                    className="flex items-center gap-1 hover:text-white transition-colors cursor-pointer"
                                  >
                                    {copiedIndex === `${idx}-${codeStr.slice(0, 5)}` ? (
                                      <>
                                        <Check className="w-3 h-3 text-emerald-400" />
                                        <span>Copied</span>
                                      </>
                                    ) : (
                                      <>
                                        <Copy className="w-3 h-3" />
                                        <span>Copy</span>
                                      </>
                                    )}
                                  </button>
                                </div>
                                <pre className="p-3 text-[11px] font-mono overflow-x-auto text-zinc-300">
                                  {children}
                                </pre>
                              </div>
                            );
                          },
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    </div>

                    {/* Citations / Retrieved Sources Section */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-4 pt-3 border-t border-[#22222a]">
                        <button
                          onClick={() => toggleSources(idx)}
                          className="flex items-center gap-1.5 text-[11px] font-semibold text-orange-400 hover:text-orange-300 transition-colors cursor-pointer"
                        >
                          <Layers className="w-3.5 h-3.5" />
                          <span>
                            {expandedSources[idx]
                              ? "Hide Citations"
                              : `Sources (${msg.citations.length} cited files)`}
                          </span>
                        </button>

                        {expandedSources[idx] && (
                          <div className="mt-2.5 space-y-2">
                            {msg.citations.map((cite, cIdx) => (
                              <div
                                key={cIdx}
                                className="p-2.5 rounded-lg bg-[#0b0b0e] border border-[#1e1e26] text-[11px]"
                              >
                                <div className="flex items-center justify-between text-zinc-400 mb-1">
                                  <div className="flex items-center gap-1.5 font-medium text-zinc-200">
                                    {cite.chunk_type === "code" ? (
                                      <Code2 className="w-3 h-3 text-orange-400" />
                                    ) : (
                                      <FileText className="w-3 h-3 text-blue-400" />
                                    )}
                                    <span>{cite.filepath}</span>
                                    <span className="text-zinc-500 font-mono text-[10px]">
                                      ({cite.name})
                                    </span>
                                  </div>
                                  <span className="text-[10px] bg-orange-500/10 text-orange-400 border border-orange-500/20 px-1.5 py-0.5 rounded">
                                    {(cite.score * 100).toFixed(1)}% match
                                  </span>
                                </div>
                                <pre className="text-[10px] font-mono text-zinc-400 bg-[#070709] p-2 rounded max-h-28 overflow-y-auto whitespace-pre-wrap">
                                  {cite.content}
                                </pre>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {msg.role === "user" && (
                    <div className="w-7 h-7 rounded-lg bg-zinc-700 flex items-center justify-center shrink-0 mt-1">
                      <User className="w-4 h-4 text-white" />
                    </div>
                  )}
                </div>
              ))}

              {/* Loading Indicator */}
              {isLoading && (
                <div className="flex items-center gap-3 text-zinc-400 text-xs py-2">
                  <div className="w-8 h-8 rounded-lg bg-orange-500/15 border border-orange-500/30 flex items-center justify-center shrink-0 p-0.5 animate-pulse">
                    <img src="/logo.png" alt="Gito" className="w-full h-full object-contain" />
                  </div>
                  <span className="animate-pulse">Gito is searching codebase & synthesizing answer...</span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Error Notification */}
        {errorMsg && (
          <div className="mx-auto max-w-xl mb-2 px-3 py-2 bg-red-950/80 border border-red-800 text-red-200 rounded-lg text-xs flex items-center justify-between gap-2 shadow-lg">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button onClick={() => setErrorMsg("")} className="text-red-400 hover:text-white">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Fixed Bottom Input Bar */}
        <div className="w-full border-t border-[#181820] bg-[#0c0c0f] p-4 flex flex-col items-center">
          <form
            onSubmit={handleSendMessage}
            className="w-full max-w-3xl relative flex items-center bg-[#141419] border border-[#24242e] focus-within:border-orange-500/70 rounded-2xl shadow-lg transition-all"
          >
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder={
                selectedProject
                  ? `Ask about ${selectedProject}...`
                  : "Select a repository to start querying..."
              }
              disabled={isLoading || !selectedProject}
              className="w-full bg-transparent px-4 py-3.5 text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={isLoading || !inputMessage.trim() || !selectedProject}
              className="mr-2.5 p-2 rounded-xl bg-orange-600 hover:bg-orange-500 disabled:bg-[#202028] disabled:text-zinc-600 text-white transition-all cursor-pointer disabled:cursor-not-allowed shadow-md shadow-orange-600/20"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>

          <div className="text-[10px] text-zinc-500 mt-2 text-center">
            Gito answers are grounded in indexed code chunks. Always verify critical implementation details.
          </div>
        </div>
      </main>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* MODAL: ADD REPOSITORY                                        */}
      {/* ───────────────────────────────────────────────────────────── */}
      {isAddingRepo && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#121217] border border-[#262632] rounded-2xl max-w-md w-full p-6 shadow-2xl relative animate-scale-in">
            <button
              onClick={() => {
                if (!isIndexing) {
                  setIsAddingRepo(false);
                  setErrorMsg("");
                }
              }}
              className="absolute top-4 right-4 text-zinc-500 hover:text-white transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-orange-500/10 border border-orange-500/30 p-1 flex items-center justify-center">
                <img src="/logo.png" alt="Gito" className="w-full h-full object-contain" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Add GitHub Repository</h3>
                <p className="text-xs text-zinc-400">
                  Gito will extract, chunk AST functions, and index into Qdrant.
                </p>
              </div>
            </div>

            <form onSubmit={handleAddRepo} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                  GitHub Repository URL
                </label>
                <input
                  type="url"
                  required
                  placeholder="https://github.com/owner/repository"
                  value={newRepoUrl}
                  onChange={(e) => setNewRepoUrl(e.target.value)}
                  disabled={isIndexing}
                  className="w-full bg-[#181820] border border-[#292936] rounded-xl px-3.5 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-orange-500 transition-colors"
                />
              </div>

              {isIndexing && (
                <div className="p-3 rounded-xl bg-orange-500/10 border border-orange-500/20 text-xs text-orange-300 flex items-center gap-2.5 animate-pulse">
                  <Loader2 className="w-4 h-4 animate-spin text-orange-400" />
                  <span>{indexStatus || "Indexing repository..."}</span>
                </div>
              )}

              {errorMsg && (
                <div className="p-3 rounded-xl bg-red-950/80 border border-red-800 text-xs text-red-300 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  disabled={isIndexing}
                  onClick={() => setIsAddingRepo(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-zinc-400 hover:text-white transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isIndexing || !newRepoUrl.trim()}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white transition-all flex items-center gap-2 cursor-pointer shadow-md shadow-orange-600/25"
                >
                  {isIndexing ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Indexing...</span>
                    </>
                  ) : (
                    <span>Start Ingestion</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ───────────────────────────────────────────────────────────── */}
      {/* MODAL: AUTHENTICATION PLACEHOLDER                             */}
      {/* ───────────────────────────────────────────────────────────── */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#121217] border border-[#262632] rounded-2xl max-w-sm w-full p-6 shadow-2xl relative">
            <button
              onClick={() => setShowAuthModal(false)}
              className="absolute top-4 right-4 text-zinc-500 hover:text-white transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex flex-col items-center text-center">
              <div className="w-14 h-14 rounded-full bg-gradient-to-tr from-orange-600 to-amber-500 text-white flex items-center justify-center font-bold text-lg mb-3 shadow-lg shadow-orange-500/25 ring-2 ring-orange-500/30">
                MY
              </div>
              <h3 className="text-base font-bold text-white">Mohan Yadav</h3>
              <p className="text-xs text-zinc-400">yadavmohanhere@gmail.com</p>
              <span className="mt-2 text-[10px] bg-orange-500/10 text-orange-400 border border-orange-500/20 px-2 py-0.5 rounded-full font-medium">
                Developer Plan
              </span>
            </div>

            <div className="mt-6 pt-4 border-t border-[#1e1e26] space-y-2">
              <div className="p-3 rounded-xl bg-[#17171e] text-xs text-zinc-300">
                <div className="font-semibold text-white mb-0.5">Authentication Ready</div>
                <div className="text-[11px] text-zinc-400">
                  Firebase / Supabase / OAuth login module will plug directly into this user context.
                </div>
              </div>

              <button
                onClick={() => setShowAuthModal(false)}
                className="w-full py-2.5 rounded-xl bg-[#20202a] hover:bg-[#282834] text-xs font-medium text-zinc-200 transition-colors cursor-pointer"
              >
                Close Settings
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
