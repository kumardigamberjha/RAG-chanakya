import React, { useState, useEffect } from 'react'
import api from './services/api'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'
import RightPanel from './components/RightPanel'
import AdminPage from './components/AdminPage'

const App = () => {
  const [chats, setChats] = useState([])
  const [activeChatId, setActiveChatId] = useState(null)
  const [tenantFiles, setTenantFiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdmin, setShowAdmin] = useState(window.location.pathname === '/admin')
  const [selectedSubject, setSelectedSubject] = useState('')

  useEffect(() => {
    const handlePopState = () => {
      setShowAdmin(window.location.pathname === '/admin')
    }
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  useEffect(() => {
    fetchChats()
    fetchTenantFiles()
  }, [])

  useEffect(() => {
    fetchTenantFiles()
  }, [selectedSubject])

  const fetchChats = async () => {
    try {
      const response = await api.get('/chats')
      setChats(response.data)
      if (response.data.length > 0 && !activeChatId) {
        // Optional: auto-select first chat
      }
    } catch (error) {
      console.error('Error fetching chats:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchTenantFiles = async () => {
    try {
      if (selectedSubject) {
        const response = await api.get(`/subjects/${selectedSubject}/sources`)
        // The backend returns a list of dictionaries for sources
        setTenantFiles(response.data.map(src => ({ id: src.id, title: src.title, isOldFormat: false })))
      } else {
        const response = await api.get('/tenant/files')
        setTenantFiles(response.data.map(fname => ({ id: fname, title: fname, isOldFormat: true })))
      }
    } catch (error) {
      console.error('Error fetching files:', error)
    }
  }

  const handleCreateChat = async (initialName = 'New Scroll') => {
    try {
      const response = await api.post('/chats', { name: initialName })
      setChats(prev => [response.data, ...prev])
      setActiveChatId(response.data.id)
      return response.data
    } catch (error) {
      console.error('Error creating chat:', error)
      return null
    }
  }

  const handleNewSessionClick = () => {
    setActiveChatId(null)
  }

  const handleDeleteChat = async (id) => {
    try {
      await api.delete(`/chats/${id}`)
      setChats(chats.filter(c => c.id !== id))
      if (activeChatId === id) setActiveChatId(null)
    } catch (error) {
      console.error('Error deleting chat:', error)
    }
  }

  const handleRenameChat = async (id, newName) => {
    try {
      const response = await api.patch(`/chats/${id}`, { name: newName })
      setChats(chats.map(c => c.id === id ? response.data : c))
    } catch (error) {
      console.error('Error renaming chat:', error)
    }
  }

  const handleRenameChatLocal = (id, newName) => {
    setChats(prev => prev.map(c => c.id === id ? { ...c, name: newName } : c))
  }

  const activeChat = chats.find(c => c.id === activeChatId)

  if (showAdmin) {
    return <AdminPage onBack={() => {
      setShowAdmin(false)
      window.history.pushState({}, '', '/')
    }} />
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '232px 1fr 288px', height: '100vh', width: '100vw', position: 'relative' }}>
      <div className="ambient-orb"></div>

      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        setActiveChatId={setActiveChatId}
        onCreateChat={handleNewSessionClick}
        onDeleteChat={handleDeleteChat}
        onRenameChat={handleRenameChat}
      />

      <ChatArea
        activeChat={activeChat}
        onCreateChat={handleCreateChat}
        onMessageSent={fetchChats}
        onRenameChatLocal={handleRenameChatLocal}
        selectedSubject={selectedSubject}
        onSubjectChange={setSelectedSubject}
      />

      <RightPanel
        tenantFiles={tenantFiles}
        onUpdate={fetchTenantFiles}
        selectedSubject={selectedSubject}
      />
    </div>
  )
}

export default App
