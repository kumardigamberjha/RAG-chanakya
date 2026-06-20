import React, { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

const Provenance = ({ sources }) => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="provenance-section" style={{ marginTop: '12px', width: '100%', maxWidth: '86%' }}>
      <button 
        className="prov-toggle" 
        onClick={() => setIsOpen(!isOpen)}
        style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'transparent', border: 'none', color: 'var(--t3)', fontSize: '12px', cursor: 'pointer', transition: 'color 0.2s', padding: '4px 0' }}
      >
        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        ◈ Provenance
        <span className="prov-pill" style={{ background: 'rgba(245,158,11,.12)', border: '1px solid rgba(245,158,11,.25)', color: 'var(--a2)', padding: '1px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 500 }}>
          {sources.length} sources
        </span>
      </button>

      {isOpen && (
        <div className="prov-drawer" style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '10px', maxHeight: '180px', overflowY: 'auto' }}>
          {sources.map((src, i) => (
            <div key={i} className="prov-item" style={{ background: 'rgba(245,158,11,.03)', borderLeft: '2px solid var(--a)', padding: '10px 12px', borderRadius: '0 4px 4px 0' }}>
              <div className="prov-file" style={{ fontFamily: "'Fira Code', monospace", fontSize: '11px', color: 'var(--a2)', marginBottom: '4px' }}>
                {src.metadata.source}
                <span className="prov-folio" style={{ color: 'var(--t3)', fontSize: '10px', marginLeft: '8px' }}>
                  Folio {src.metadata.page || 'N/A'}
                </span>
              </div>
              <div className="prov-text" style={{ fontSize: '12.5px', color: 'var(--t2)', lineHeight: 1.5, fontStyle: 'italic' }}>
                "{src.page_content}"
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default Provenance
