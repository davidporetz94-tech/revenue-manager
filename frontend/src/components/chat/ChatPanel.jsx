import React, { useState, useRef, useEffect, useMemo } from 'react';
import { chatWithAI } from '../../api/client';

function buildStarterQuestions(summaryData) {
  if (!summaryData || !summaryData.unit_types) {
    return [
      "Which unit type needs attention first?",
      "What's my biggest revenue risk right now?",
    ];
  }

  const entries = Object.entries(summaryData.unit_types);
  // Find worst performer (lowest occ)
  const worst = entries.reduce((w, [code, d]) => (!w || d.occ < w[1].occ) ? [code, d] : w, null);
  // Find highest burn
  const highBurn = entries.reduce((w, [code, d]) => (!w || d.dailyBurn > w[1].dailyBurn) ? [code, d] : w, null);
  // Find one priced above comps
  const aboveComps = entries.find(([, d]) => d.asking > d.comps);

  const questions = [];
  if (worst) questions.push(`Why is ${worst[0]} at ${Math.round(worst[1].occ * 100)}% occupancy?`);
  if (aboveComps) questions.push(`What happens if I cut ${aboveComps[0]} by $50?`);
  questions.push("Which unit type needs attention first?");
  if (highBurn) questions.push(`How do I reduce the ${highBurn[0]} vacancy burn?`);

  return questions.slice(0, 4);
}

export default function ChatPanel({ propertyId, propertyName, latestRunId, summaryData, isOpen, onToggle }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function sendMessage(text) {
    if (!text.trim() || loading) return;

    const userMsg = { role: 'user', content: text.trim() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await chatWithAI(propertyId, text.trim(), latestRunId);
      setMessages(prev => [...prev, { role: 'assistant', content: res.response, sources: res.sources }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Failed to get a response. Please try again.', error: true }]);
    }
    setLoading(false);
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  const starterQuestions = useMemo(() => buildStarterQuestions(summaryData), [summaryData]);

  if (!isOpen) return null;

  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-white border-l border-stone-200 shadow-2xl z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-stone-200 bg-stone-50">
        <div>
          <h3 className="font-semibold text-sm text-stone-800">Ask about {propertyName}</h3>
          <p className="text-[10px] text-stone-400">Powered by AI analysis</p>
        </div>
        <button onClick={onToggle} className="text-stone-400 hover:text-stone-600 p-1">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div>
            <p className="text-xs text-stone-400 mb-3">Try asking:</p>
            <div className="space-y-2">
              {starterQuestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(q)}
                  className="w-full text-left text-xs text-stone-600 bg-stone-50 hover:bg-stone-100 rounded-lg px-3 py-2 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
              msg.role === 'user'
                ? 'bg-stone-800 text-white'
                : msg.error
                  ? 'bg-red-50 text-red-700 border border-red-200'
                  : 'bg-stone-100 text-stone-700'
            }`}>
              <ChatContent text={msg.content} />
              {msg.sources && (
                <div className="mt-1 flex gap-1">
                  {msg.sources.map((s, j) => (
                    <span key={j} className="text-[9px] bg-stone-200 text-stone-500 px-1.5 py-0.5 rounded">
                      {s}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-stone-100 rounded-lg px-3 py-2 text-sm text-stone-400 flex items-center gap-2">
              <div className="w-3 h-3 border-2 border-stone-300 border-t-stone-600 rounded-full animate-spin" />
              Analyzing...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-stone-200 px-4 py-3">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about pricing..."
            className="flex-1 text-sm border border-stone-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-stone-300"
            disabled={loading}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={loading || !input.trim()}
            className="px-3 py-2 bg-stone-800 text-white rounded-lg text-sm font-medium hover:bg-stone-700 disabled:opacity-30 transition-colors"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

function ChatContent({ text }) {
  if (!text) return null;
  // Split on bullet chars (•, -, *) at line start to detect bulleted content
  const lines = text.split('\n').filter(l => l.trim());
  const bulletPattern = /^[\s]*[•\-\*]\s+/;
  const hasBullets = lines.some(l => bulletPattern.test(l));

  if (!hasBullets) return <span>{text}</span>;

  // Separate lead-in text from bullets
  const parts = [];
  let currentBullets = [];

  for (const line of lines) {
    if (bulletPattern.test(line)) {
      currentBullets.push(line.replace(bulletPattern, '').trim());
    } else {
      if (currentBullets.length > 0) {
        parts.push({ type: 'bullets', items: currentBullets });
        currentBullets = [];
      }
      parts.push({ type: 'text', content: line.trim() });
    }
  }
  if (currentBullets.length > 0) {
    parts.push({ type: 'bullets', items: currentBullets });
  }

  return (
    <div className="space-y-1.5">
      {parts.map((part, i) =>
        part.type === 'text' ? (
          <p key={i}>{part.content}</p>
        ) : (
          <ul key={i} className="space-y-1 ml-1">
            {part.items.map((item, j) => (
              <li key={j} className="flex items-start gap-1.5">
                <span className="text-stone-400 mt-0.5 text-[8px]">●</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        )
      )}
    </div>
  );
}
