import React, { useState, useEffect, useRef } from 'react'
import api from '../services/api'
import { Send, User, Bot, ChevronDown, ChevronRight } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import Provenance from './Provenance'

const CollapsibleAnswers = ({ children }) => {
  const [isOpen, setIsOpen] = useState(false);
  if (!children || children.length === 0) return null;
  return (
    <div style={{ marginTop: '16px', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        style={{ width: '100%', padding: '12px 16px', background: 'rgba(255,255,255,0.03)', border: 'none', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', color: 'var(--t1)', fontWeight: 500 }}
      >
        <span>Reveal Answers</span>
        <ChevronDown style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} size={18} />
      </button>
      {isOpen && (
        <div style={{ padding: '16px', borderTop: '1px solid var(--border)', background: 'rgba(0,0,0,0.1)' }}>
          {children}
        </div>
      )}
    </div>
  );
};

const MarkdownRenderer = ({ text }) => {
  if (!text) return null;

  const lines = text.split('\n');
  const elements = [];
  const answerElements = [];
  
  let inAnswerSection = false;
  let currentList = [];
  let currentListType = null; // 'ul' or 'ol'
  let insideCodeBlock = false;
  let codeBlockContent = [];

  const flushList = (key) => {
    if (currentList.length > 0) {
      let el;
      if (currentListType === 'ul') {
        el = (
          <ul key={`ul-${key}`} style={{ margin: '8px 0', paddingLeft: '20px', listStyleType: 'disc' }}>
            {currentList}
          </ul>
        );
      } else {
        el = (
          <ol key={`ol-${key}`} style={{ margin: '8px 0', paddingLeft: '20px', listStyleType: 'decimal' }}>
            {currentList}
          </ol>
        );
      }
      if (inAnswerSection) answerElements.push(el);
      else elements.push(el);
      
      currentList = [];
      currentListType = null;
    }
  };

  const parseInline = (rawStr) => {
    if (!rawStr) return '';
    
    // Replace common LaTeX math arrows with unicode symbols
    let str = rawStr
      .replace(/\$\s*\\rightarrow\s*\$/g, '→')
      .replace(/\$\s*\\leftarrow\s*\$/g, '←')
      .replace(/\$\s*\\leftrightarrow\s*\$/g, '↔')
      .replace(/\$\s*\\Rightarrow\s*\$/g, '⇒')
      .replace(/\$\s*\\Leftarrow\s*\$/g, '⇐')
      .replace(/\$\s*\\Leftrightarrow\s*\$/g, '⇔');
      
    const regex = /(\*\*.*?\*\*|__.*?__|`.*?`|\*.*?\*|_.*?_)/g;
    const parts = str.split(regex);
    
    return parts.map((part, idx) => {
      if ((part.startsWith('**') && part.endsWith('**')) || (part.startsWith('__') && part.endsWith('__'))) {
        return <strong key={idx} style={{ fontWeight: 700, color: 'var(--t1)' }}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return <code key={idx} style={{ fontFamily: 'monospace', background: 'rgba(255,255,255,0.08)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px', color: 'var(--p2)' }}>{part.slice(1, -1)}</code>;
      }
      if ((part.startsWith('*') && part.endsWith('*')) || (part.startsWith('_') && part.endsWith('_'))) {
        return <em key={idx} style={{ fontStyle: 'italic', color: 'var(--t2)' }}>{part.slice(1, -1)}</em>;
      }
      return part;
    });
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.trim().toLowerCase() === '## answer key' || line.trim().toLowerCase() === '### answer key' || line.trim().toLowerCase() === 'answer key:' || line.trim().toLowerCase() === 'answer key' || line.trim() === '=== ANSWERS ===') {
      flushList(i);
      inAnswerSection = true;
      continue;
    }

    const target = inAnswerSection ? answerElements : elements;

    if (line.trim().startsWith('```')) {
      flushList(i);
      if (insideCodeBlock) {
        target.push(
          <pre key={`code-${i}`} style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', borderRadius: '8px', padding: '12px', margin: '12px 0', overflowX: 'auto', fontFamily: 'monospace', fontSize: '13px' }}>
            <code style={{ color: 'var(--t1)' }}>{codeBlockContent.join('\n')}</code>
          </pre>
        );
        codeBlockContent = [];
        insideCodeBlock = false;
      } else {
        insideCodeBlock = true;
      }
      continue;
    }

    if (insideCodeBlock) {
      codeBlockContent.push(line);
      continue;
    }

    if (!line.trim()) {
      flushList(i);
      continue;
    }

    if (/^(?:\*|-|_){3,}$/.test(line.trim())) {
      flushList(i);
      target.push(<hr key={i} style={{ margin: '18px 0', border: 'none', borderTop: '1px solid var(--border)' }} />);
      continue;
    }

    if (line.startsWith('### ')) {
      flushList(i);
      target.push(<h3 key={i} style={{ fontSize: '15.5px', fontWeight: 600, color: 'var(--t1)', margin: '14px 0 6px 0' }}>{parseInline(line.slice(4))}</h3>);
      continue;
    }
    if (line.startsWith('## ')) {
      flushList(i);
      target.push(<h2 key={i} style={{ fontSize: '17.5px', fontWeight: 600, color: 'var(--t1)', margin: '18px 0 8px 0' }}>{parseInline(line.slice(3))}</h2>);
      continue;
    }
    if (line.startsWith('# ')) {
      flushList(i);
      target.push(<h1 key={i} style={{ fontSize: '19.5px', fontWeight: 700, color: 'var(--t1)', margin: '22px 0 10px 0' }}>{parseInline(line.slice(2))}</h1>);
      continue;
    }

    const bulletMatch = line.match(/^[-*+]\s+(.*)/);
    if (bulletMatch) {
      if (currentListType && currentListType !== 'ul') {
        flushList(i);
      }
      currentListType = 'ul';
      currentList.push(<li key={`li-${i}`} style={{ margin: '4px 0', lineHeight: 1.5, color: 'var(--t1)' }}>{parseInline(bulletMatch[1])}</li>);
      continue;
    }

    const numberedMatch = line.match(/^(\d+)\.\s+(.*)/);
    if (numberedMatch) {
      if (currentListType && currentListType !== 'ol') {
        flushList(i);
      }
      currentListType = 'ol';
      currentList.push(<li key={`li-${i}`} style={{ margin: '4px 0', lineHeight: 1.5, color: 'var(--t1)' }}>{parseInline(numberedMatch[2])}</li>);
      continue;
    }

    flushList(i);
    if (line.includes('***')) {
      const parts = line.split('***');
      target.push(
        <div key={i} style={{ margin: '8px 0', lineHeight: 1.6 }}>
          {parts.map((part, partIdx) => (
            <React.Fragment key={partIdx}>
              {partIdx > 0 && (
                <div style={{ 
                  margin: '16px 0', 
                  borderTop: '1px solid var(--border)', 
                  opacity: 0.8
                }} />
              )}
              {parseInline(part)}
            </React.Fragment>
          ))}
        </div>
      );
    } else {
      target.push(<p key={i} style={{ margin: '8px 0', lineHeight: 1.6 }}>{parseInline(line)}</p>);
    }
  }

  flushList('end');

  if (insideCodeBlock && codeBlockContent.length > 0) {
    const target = inAnswerSection ? answerElements : elements;
    target.push(
      <pre key="code-unclosed" style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', borderRadius: '8px', padding: '12px', margin: '12px 0', overflowX: 'auto', fontFamily: 'monospace', fontSize: '13px' }}>
        <code style={{ color: 'var(--t1)' }}>{codeBlockContent.join('\n')}</code>
      </pre>
    );
  }

  if (answerElements.length > 0) {
    elements.push(
      <CollapsibleAnswers key="answers-section">
        {answerElements}
      </CollapsibleAnswers>
    );
  }

  return <div className="markdown-body" style={{ color: 'var(--t1)', fontSize: '14.5px' }}>{elements}</div>;
};

const ChatArea = ({ activeChat, onCreateChat, onRenameChatLocal, onMessageSent, selectedSubject, onSubjectChange }) => {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [models, setModels] = useState([
    { id: 'gemma_ollama', name: 'Gemma 31B' },
    { id: 'mistral_ollama', name: 'Mistral Latest' },
    { id: 'minimax_nvidia', name: 'MiniMax-M3 (Nvidia)' }
  ])
  const [selectedModel, setSelectedModel] = useState('gemma_ollama')
  const [subjects, setSubjects] = useState([])
  const [suggestions, setSuggestions] = useState([
    "Summarize the key principles discussed in the document.",
    "What are the most important lessons or takeaways?",
    "Can you provide an overview of the main topics covered?"
  ])
  const scrollRef = useRef(null)

  useEffect(() => {
    fetchModels()
    fetchSuggestions()
    fetchSubjects()
  }, [])

  useEffect(() => {
    if (activeChat) {
      fetchHistory()
    } else {
      setMessages([])
    }
    fetchSuggestions()
  }, [activeChat?.id])

  const fetchSuggestions = async () => {
    try {
      const response = await api.get('/tenant/suggestions')
      if (response.data && Array.isArray(response.data) && response.data.length > 0) {
        setSuggestions(response.data)
      }
    } catch (error) {
      console.error('Error fetching suggestions:', error)
    }
  }

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const fetchModels = async () => {
    try {
      const response = await api.get('/models')
      setModels(response.data)
      if (response.data && response.data.length > 0) {
        setSelectedModel(response.data[0].id)
      }
    } catch (error) {
      console.error('Error fetching models:', error)
    }
  }

  const fetchSubjects = async () => {
    try {
      const response = await api.get('/subjects')
      setSubjects(response.data)
    } catch (error) {
      console.error('Error fetching subjects:', error)
    }
  }

  const fetchHistory = async () => {
    if (isSending || isStreaming) return
    try {
      const response = await api.get(`/chats/${activeChat.id}/history`)
      setMessages(response.data)
    } catch (error) {
      console.error('Error fetching history:', error)
    }
  }

  const handleSend = async (customInput = null, isQuiz = false) => {
    const userQuery = (typeof customInput === 'string' ? customInput : input).trim()
    if (!userQuery || isSending) return

    setInput('')
    setIsSending(true)
    setIsStreaming(false)

    // Optimistic update for user message
    setMessages(prev => [...prev, { type: 'human', content: userQuery }])
    
    // Placeholder for AI response
    setMessages(prev => [...prev, { type: 'ai', content: '', sources: [] }])

    try {
      let chatId = activeChat ? activeChat.id : null
      if (!chatId) {
        // Create the session first in DB
        const newChat = await onCreateChat(userQuery)
        if (!newChat) {
          throw new Error('Failed to create session')
        }
        chatId = newChat.id
      }

      const payload = { query: userQuery, model: selectedModel, is_quiz: isQuiz }
      if (selectedSubject) {
        payload.subject_id = parseInt(selectedSubject, 10)
      }

      // Use native fetch for streaming (Axios doesn't support streaming in browser easily)
      const response = await fetch(`${api.defaults.baseURL}/chats/${chatId}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': 'school-alpha-01' // Consistent with api.js interceptor
        },
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to fetch response')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let accumulatedAnswer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (!line.trim()) continue
          
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6))
              
              if (data.title && onRenameChatLocal) {
                onRenameChatLocal(chatId, data.title)
              }

              if (data.chunk) {
                if (!isStreaming) setIsStreaming(true)
                accumulatedAnswer += data.chunk
                setMessages(prev => {
                  const updated = [...prev]
                  const lastIdx = updated.length - 1
                  if (lastIdx >= 0) {
                    updated[lastIdx] = { ...updated[lastIdx], content: accumulatedAnswer }
                  }
                  return updated
                })
              }
              
              if (data.sources) {
                setMessages(prev => {
                  const updated = [...prev]
                  const lastIdx = updated.length - 1
                  if (lastIdx >= 0) {
                    updated[lastIdx] = { ...updated[lastIdx], sources: data.sources }
                  }
                  return updated
                })
              }

              if (data.error) {
                throw new Error(data.error)
              }
            } catch (e) {
              console.error('Error parsing SSE:', e, line)
            }
          }
        }
      }
      if (onMessageSent) {
        onMessageSent()
      }
    } catch (error) {
      console.error('Error sending message:', error)
      setMessages(prev => {
        if (prev.length === 0) return prev
        const updated = [...prev]
        const lastIdx = updated.length - 1
        updated[lastIdx] = { ...updated[lastIdx], content: `Error: ${error.message}` }
        return updated
      })
    } finally {
      setIsSending(false)
      setIsStreaming(false)
    }
  }

  const handleGenerateQuiz = () => {
    handleSend("Generate a 5-question quiz ranging from beginner to experienced level based on this subject.", true)
  }

  return (
    <div id="center-panel" style={{ display: 'flex', flexDirection: 'column', height: '100vh', position: 'relative' }}>
      <div className="topbar" style={{ height: '54px', padding: '0 24px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', backdropFilter: 'blur(8px)', zIndex: 5 }}>
        <div className="session-info" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className="session-title-main" style={{ fontSize: '15px', fontWeight: 600 }}>{activeChat ? activeChat.name : 'New Session'}</div>
          <div className="badge-pill badge-green" style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', padding: '4px 10px', borderRadius: '99px', background: 'rgba(16,185,129,.08)', color: '#34d399', border: '1px solid rgba(16,185,129,.2)' }}>
            <div className="dot-small" style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'currentColor' }}></div>
            online
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className="subject-selector-container" style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <select
              value={selectedSubject}
              onChange={(e) => onSubjectChange(e.target.value)}
              style={{
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                padding: '6px 28px 6px 12px',
                color: 'var(--t1)',
                fontSize: '13px',
                fontWeight: 500,
                cursor: 'pointer',
                outline: 'none',
                transition: 'all 0.2s ease',
                fontFamily: 'inherit',
                appearance: 'none',
              }}
            >
              <option value="" style={{ background: '#0b0f19', color: 'var(--t1)' }}>Global Knowledge</option>
              {subjects.map(s => (
                <option key={s.id} value={s.id} style={{ background: '#0b0f19', color: 'var(--t1)' }}>
                  {s.name}
                </option>
              ))}
            </select>
            <div style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: 'var(--t3)', display: 'flex', alignItems: 'center' }}>
              <ChevronDown size={14} />
            </div>
          </div>

          <div className="model-selector-container" style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              style={{
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                padding: '6px 28px 6px 12px',
                color: 'var(--t1)',
                fontSize: '13px',
                fontWeight: 500,
                cursor: 'pointer',
                outline: 'none',
                transition: 'all 0.2s ease',
                fontFamily: 'inherit',
                appearance: 'none',
              }}
            >
              {models.map(m => (
                <option key={m.id} value={m.id} style={{ background: '#0b0f19', color: 'var(--t1)' }}>
                  {m.name}
                </option>
              ))}
            </select>
            <div style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: 'var(--t3)', display: 'flex', alignItems: 'center' }}>
              <ChevronDown size={14} />
            </div>
          </div>
          
          <button
            onClick={handleGenerateQuiz}
            disabled={isSending}
            style={{
              background: 'linear-gradient(135deg, rgba(79, 195, 247, 0.15) 0%, rgba(41, 121, 255, 0.15) 100%)',
              border: '1px solid rgba(79, 195, 247, 0.3)',
              borderRadius: '8px',
              padding: '6px 16px',
              color: '#4FC3F7',
              fontSize: '13px',
              fontWeight: 600,
              cursor: isSending ? 'not-allowed' : 'pointer',
              outline: 'none',
              transition: 'all 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              opacity: isSending ? 0.5 : 1
            }}
            onMouseOver={(e) => {
              if (!isSending) e.currentTarget.style.background = 'linear-gradient(135deg, rgba(79, 195, 247, 0.25) 0%, rgba(41, 121, 255, 0.25) 100%)'
            }}
            onMouseOut={(e) => {
              if (!isSending) e.currentTarget.style.background = 'linear-gradient(135deg, rgba(79, 195, 247, 0.15) 0%, rgba(41, 121, 255, 0.15) 100%)'
            }}
          >
            Generate Quiz
          </button>
        </div>
      </div>

      <div className="chat-viewport custom-scroll" ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '32px 0', display: 'flex', flexDirection: 'column', gap: '28px' }}>
        <AnimatePresence initial={false}>
          {messages.length === 0 && (
            <motion.div 
              key="suggestions"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="suggestions-container"
              style={{ width: '100%', maxWidth: '800px', margin: '0 auto', padding: '0 32px', display: 'flex', flexDirection: 'column', gap: '16px' }}
            >
              <div style={{ color: 'var(--t2)', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                Suggested inquiries:
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
                {suggestions.map((topic, i) => (
                  <div 
                    key={i}
                    onClick={() => handleSend(topic)}
                    style={{
                      background: 'rgba(255,255,255,.02)',
                      border: '1px solid var(--border)',
                      borderRadius: '12px',
                      padding: '16px',
                      cursor: 'pointer',
                      color: 'var(--t1)',
                      fontSize: '13.5px',
                      lineHeight: 1.5,
                      transition: 'all 0.2s ease',
                      boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(255,255,255,.05)';
                      e.currentTarget.style.borderColor = 'rgba(129,140,248,.4)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'rgba(255,255,255,.02)';
                      e.currentTarget.style.borderColor = 'var(--border)';
                    }}
                  >
                    {topic}
                  </div>
                ))}
              </div>
            </motion.div>
          )}
          {messages.map((msg, idx) => (
            <motion.div 
              key={`msg-${idx}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className={`message-row ${msg.type === 'human' ? 'user-row' : 'ai-row'}`}
              style={{ width: '100%', maxWidth: '800px', margin: '0 auto', padding: '0 32px', display: 'flex', flexDirection: 'column', alignItems: msg.type === 'human' ? 'flex-end' : 'flex-start' }}
            >
              {msg.type === 'ai' && (
                <div className="ai-header" style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                  <div className="ai-avatar" style={{ width: '26px', height: '26px', background: 'var(--indigo-gradient)', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '13px', color: 'white' }}>S</div>
                  <span className="ai-name" style={{ fontSize: '13px', fontWeight: 600, color: 'var(--t2)' }}>Sanjaya</span>
                </div>
              )}
              
              <div 
                className={msg.type === 'human' ? 'user-bubble' : 'ai-bubble'}
                style={msg.type === 'human' ? {
                  maxWidth: '70%', background: 'var(--user-gradient)', border: '1px solid rgba(129,140,248,.22)',
                  borderRadius: '14px 14px 3px 14px', padding: '12px 16px', fontSize: '14.5px', lineHeight: 1.5, color: 'var(--t1)'
                } : {
                  maxWidth: '86%', background: 'rgba(255,255,255,.025)', border: '1px solid var(--border)',
                  borderRadius: '3px 14px 14px 14px', padding: '13px 15px', fontSize: '14.5px', lineHeight: 1.6, color: 'var(--t1)'
                }}
              >
                {msg.type === 'ai' ? (
                  <MarkdownRenderer text={msg.content} />
                ) : (
                  msg.content
                )}
              </div>

              {msg.type === 'ai' && msg.sources && msg.sources.length > 0 && (
                <Provenance sources={msg.sources} />
              )}
            </motion.div>
          ))}
          {isSending && !isStreaming && (
             <div key="synthesizing-loader" className="message-row ai-row" style={{ width: '100%', maxWidth: '800px', margin: '0 auto', padding: '0 32px', display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                <div className="ai-header" style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                  <div className="ai-avatar" style={{ width: '26px', height: '26px', background: 'var(--indigo-gradient)', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '13px', color: 'white' }}>S</div>
                  <span className="ai-name" style={{ fontSize: '13px', fontWeight: 600, color: 'var(--t2)' }}>Sanjaya is synthesizing...</span>
                </div>
             </div>
          )}
        </AnimatePresence>
      </div>

      <div className="input-bar" style={{ padding: '24px 32px', borderTop: '1px solid var(--border)', backdropFilter: 'blur(8px)', zIndex: 5 }}>
        <div className="input-shell" style={{ maxWidth: '800px', margin: '0 auto', background: 'rgba(255,255,255,.03)', border: '1px solid var(--border2)', borderRadius: '12px', padding: '8px 12px', display: 'flex', alignItems: 'flex-end', gap: 12 }}>
          <textarea 
            id="chat-input"
            rows={1}
            placeholder="Ask Sanjaya..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSend())}
            style={{ flex: 1, background: 'transparent', border: 'none', color: 'var(--t1)', fontFamily: 'inherit', fontSize: '14.5px', padding: '8px 0', resize: 'none', outline: 'none' }}
          />
          <button 
            className="btn-send" 
            onClick={handleSend}
            disabled={isSending || !input.trim()}
            style={{
              width: '34px', height: '34px', background: 'var(--indigo-gradient)', border: 'none', borderRadius: '8px',
              display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
              boxShadow: '0 2px 10px rgba(99,102,241,.4)', transition: 'all 0.2s ease', opacity: isSending || !input.trim() ? 0.5 : 1
            }}
          >
            <Send size={16} color="white" />
          </button>
        </div>
      </div>
    </div>
  )
}

export default ChatArea
