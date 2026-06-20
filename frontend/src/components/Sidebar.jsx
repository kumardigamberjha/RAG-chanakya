import React, { useState } from 'react'
import { Plus, Trash2, Edit2, Check, X } from 'lucide-react'

const getGroupLabel = (dateStr) => {
  if (!dateStr) return 'Older'
  const chatDate = new Date(dateStr)
  const now = new Date()

  // Reset hours/minutes/seconds/ms for day-based comparison
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)

  const sevenDaysAgo = new Date(today)
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)

  const thirtyDaysAgo = new Date(today)
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

  if (chatDate >= today) {
    return 'Today'
  } else if (chatDate >= yesterday) {
    return 'Yesterday'
  } else if (chatDate >= sevenDaysAgo) {
    return 'Previous 7 Days'
  } else if (chatDate >= thirtyDaysAgo) {
    return 'Previous 30 Days'
  } else {
    const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    if (chatDate.getFullYear() === today.getFullYear()) {
      return months[chatDate.getMonth()]
    } else {
      return `${months[chatDate.getMonth()]} ${chatDate.getFullYear()}`
    }
  }
}

const Sidebar = ({ chats, activeChatId, setActiveChatId, onCreateChat, onDeleteChat, onRenameChat }) => {
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')

  const startEditing = (chat) => {
    setEditingId(chat.id)
    setEditName(chat.name)
  }

  const saveEdit = () => {
    onRenameChat(editingId, editName)
    setEditingId(null)
  }

  const sortedChats = [...chats].sort((a, b) => {
    const dateA = a.created_at ? new Date(a.created_at) : new Date(0)
    const dateB = b.created_at ? new Date(b.created_at) : new Date(0)
    return dateB - dateA
  })

  const grouped = {}
  const groupLabels = []
  sortedChats.forEach(chat => {
    const label = getGroupLabel(chat.created_at)
    if (!grouped[label]) {
      grouped[label] = []
    }
    grouped[label].push(chat)
    if (!groupLabels.includes(label)) {
      groupLabels.push(label)
    }
  })

  return (
    <div id="sidebar" style={{ 
      backgroundColor: 'var(--c1)', 
      borderRight: '1px solid var(--border)', 
      display: 'flex', 
      flexDirection: 'column', 
      zIndex: 10 
    }}>
      <div className="logo-area" style={{ padding: '18px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
        <div className="logo-tile" style={{ 
          width: '34px', height: '34px', background: 'var(--indigo-gradient)', borderRadius: '9px', 
          display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 700, fontSize: '18px',
          boxShadow: '0 0 0 1px rgba(129,140,248,.3), 0 4px 12px rgba(99,102,241,.4)'
        }}>S</div>
        <div className="logo-text">
          <h1 style={{ fontSize: '14px', fontWeight: 600, letterSpacing: '-0.01em' }}>Sanjaya</h1>
          <p style={{ fontFamily: "'Fira Code', monospace", fontSize: '9.5px', color: 'var(--t3)', marginTop: '1px' }}>RAG · LOCAL</p>
        </div>
      </div>

      <div className="nav-section" style={{ padding: '0 14px', flex: 1, overflowY: 'auto' }}>
        <button className="btn-new-session" onClick={onCreateChat} style={{
          width: '100%', padding: '8px 12px', background: 'rgba(99,102,241,.06)', border: '1px solid rgba(129,140,248,.3)',
          borderRadius: '6px', color: 'var(--p2)', fontSize: '13px', fontWeight: 500, display: 'flex', alignItems: 'center',
          gap: '10px', cursor: 'pointer', transition: 'all 0.2s ease', marginBottom: '24px'
        }}>
          <div className="plus-box" style={{ width: '18px', height: '18px', border: '1.5px solid var(--p2)', borderRadius: '3px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px', fontWeight: 600 }}>+</div>
          New Session
        </button>

        <div className="custom-scroll" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {groupLabels.map(label => (
            <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{
                fontSize: '11px',
                fontWeight: 600,
                color: 'var(--t3)',
                padding: '4px 6px',
                letterSpacing: '0.02em',
                opacity: 0.8
              }}>
                {label}
              </div>
              {grouped[label].map(chat => (
                <div 
                  key={chat.id} 
                  className={`session-item ${activeChatId === chat.id ? 'active' : ''}`}
                  onClick={() => setActiveChatId(chat.id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '10px', padding: '9px 10px', borderRadius: '6px',
                    cursor: 'pointer', position: 'relative', transition: 'all 0.2s ease',
                    color: activeChatId === chat.id ? 'var(--t1)' : 'var(--t2)',
                    backgroundColor: activeChatId === chat.id ? 'rgba(99,102,241,.12)' : 'transparent',
                    border: activeChatId === chat.id ? '1px solid rgba(129,140,248,.18)' : '1px solid transparent'
                  }}
                >
                  <div className="pip" style={{ 
                    width: '5px', height: '5px', borderRadius: '50%', 
                    backgroundColor: activeChatId === chat.id ? 'var(--p)' : 'var(--t4)',
                    boxShadow: activeChatId === chat.id ? '0 0 5px var(--p)' : 'none'
                  }}></div>
                  
                  {editingId === chat.id ? (
                    <input 
                      autoFocus
                      className="session-name"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onBlur={saveEdit}
                      onKeyDown={(e) => e.key === 'Enter' && saveEdit()}
                      style={{ background: 'transparent', border: 'none', color: 'inherit', outline: 'none', width: '100%' }}
                    />
                  ) : (
                    <div className="session-name" style={{ fontSize: '13.5px', flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {chat.name}
                    </div>
                  )}

                  <div className="session-actions" style={{ display: 'flex', gap: '4px' }}>
                    <button className="action-btn" onClick={(e) => { e.stopPropagation(); startEditing(chat); }} style={{ background: 'transparent', border: 'none', color: 'var(--t3)', cursor: 'pointer' }}>
                      <Edit2 size={12} />
                    </button>
                    <button className="action-btn" onClick={(e) => { e.stopPropagation(); onDeleteChat(chat.id); }} style={{ background: 'transparent', border: 'none', color: 'var(--t3)', cursor: 'pointer' }}>
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className="sidebar-footer" style={{ padding: '16px 20px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '10px', fontFamily: "'Fira Code', monospace", fontSize: '9.5px', color: 'var(--t3)' }}>
        <div className="blink-dot"></div>
        v0.2 · React · local
      </div>
    </div>
  )
}

export default Sidebar
