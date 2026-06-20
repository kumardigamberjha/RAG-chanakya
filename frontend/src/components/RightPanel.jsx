import React, { useState } from 'react'
import api from '../services/api'
import { Upload, FileText, X, Database } from 'lucide-react'

const RightPanel = ({ tenantFiles, onUpdate, selectedSubject }) => {
  const [isUploading, setIsUploading] = useState(false)

  const handleFileUpload = async (e) => {
    const files = e.target.files
    if (!files.length) return

    setIsUploading(true)
    try {
      for (let i = 0; i < files.length; i++) {
        const formData = new FormData()
        formData.append('file', files[i])
        if (selectedSubject) {
          // If a subject is selected, upload it as a source
          const token = localStorage.getItem('token') || ''
          await api.post(`/subjects/${selectedSubject}/sources/upload`, formData, {
            headers: { 'Authorization': `Bearer ${token}` }
          })
        } else {
          // Fallback to tenant upload
          await api.post(`/tenant/upload`, formData)
        }
      }
      onUpdate()
    } catch (error) {
      console.error('Error uploading file:', error)
      alert(`Upload failed: ${error.response?.data?.detail || error.message}`)
    } finally {
      setIsUploading(false)
      e.target.value = '' // Reset input
    }
  }

  const handleDeleteFile = async (file) => {
    try {
      if (file.isOldFormat) {
        await api.delete(`/tenant/files/${file.id}`)
      } else {
        // Need to use the admin delete source endpoint or normal delete if available.
        // The backend has /api/admin/subjects/{subject_id}/sources/{source_id}
        const token = localStorage.getItem('token') || ''
        await api.delete(`/admin/subjects/${selectedSubject}/sources/${file.id}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      }
      onUpdate()
    } catch (error) {
      console.error('Error deleting file:', error)
    }
  }

  return (
    <div id="right-panel" style={{ backgroundColor: 'var(--c1)', borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', zIndex: 10 }}>
      <div className="right-header" style={{ padding: '18px 24px', borderBottom: '1px solid var(--border)', position: 'relative' }}>
        <h3 style={{ fontSize: '13px', fontWeight: 600, marginBottom: '2px' }}>Corpus</h3>
        <p style={{ fontSize: '11px', color: 'var(--t3)' }}>Manage session knowledge</p>
        <div className="corpus-badge" style={{ position: 'absolute', top: '20px', right: '24px', background: 'rgba(99,102,241,.08)', border: '1px solid rgba(129,140,248,.2)', color: 'var(--p2)', fontSize: '10px', fontWeight: 600, padding: '2px 6px', borderRadius: '4px' }}>
          {tenantFiles?.length || 0} scrolls
        </div>
      </div>

      <div className="drop-zone-container" style={{ padding: '24px' }}>
        <label className="drop-zone" style={{
          display: 'block', border: '1.5px dashed rgba(99,102,241,.2)', borderRadius: '10px', padding: '30px 20px',
          textAlign: 'center', cursor: 'pointer', transition: 'all 0.2s ease', background: 'rgba(255, 255, 255, 0.01)'
        }}>
          <input type="file" multiple onChange={handleFileUpload} style={{ display: 'none' }} disabled={isUploading} />
          <div className="upload-icon-box" style={{ width: '36px', height: '36px', background: 'rgba(99,102,241,0.1)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px', color: 'var(--p)' }}>
            <Upload size={18} />
          </div>
          <h4 style={{ fontSize: '12px', fontWeight: 500, marginBottom: '4px' }}>{isUploading ? 'Ingesting...' : 'Drop scrolls here'}</h4>
          <p style={{ fontFamily: "'Fira Code', monospace", fontSize: '10px', color: 'var(--t3)', marginBottom: '12px' }}>PDF · TXT · HTML</p>
          <span className="btn-browse" style={{ color: 'var(--p2)', fontSize: '11px', fontWeight: 600 }}>Browse Files</span>
        </label>
      </div>

      <div className="file-list custom-scroll" style={{ flex: 1, overflowY: 'auto', padding: '0 24px' }}>
        {tenantFiles?.map((file, idx) => (
          <div key={idx} className="file-card" style={{
            background: 'rgba(255,255,255,.02)', border: '1px solid var(--border)', borderRadius: '8px',
            padding: '9px 11px', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '12px',
            position: 'relative', transition: 'all 0.25s ease', overflow: 'hidden'
          }}>
            <div className="file-icon-box" style={{ width: '28px', height: '28px', background: 'rgba(245,158,11, 0.12)', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--a)', fontSize: '14px' }}>
              <FileText size={14} />
            </div>
            <div className="file-info" style={{ flex: 1, minWidth: 0 }}>
              <div className="file-name" style={{ fontSize: '12.5px', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginBottom: '2px' }}>{file.title}</div>
              <div className="file-meta" style={{ fontFamily: "'Fira Code', monospace", fontSize: '9.5px', color: 'var(--t3)' }}>Ready for session</div>
            </div>
            <button className="file-del" onClick={() => handleDeleteFile(file)} style={{ background: 'transparent', border: 'none', color: 'var(--t4)', cursor: 'pointer', transition: 'color 0.2s' }}>
              <X size={14} />
            </button>
          </div>
        ))}
      </div>

      <div className="corpus-footer" style={{ padding: '16px 24px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="corpus-stats" style={{ fontFamily: "'Fira Code', monospace", fontSize: '10px', color: 'var(--t3)' }}>
          DB: Local Vector
        </div>
        <div className="indexed-pill" style={{ display: 'flex', alignItems: 'center', gap: '5px', fontFamily: "'Fira Code', monospace", fontSize: '9px', color: '#34d399', background: 'rgba(16,185,129,0.08)', padding: '2px 6px', borderRadius: '4px' }}>
          <Database size={10} />
          INDEXED
        </div>
      </div>
    </div>
  )
}

export default RightPanel
