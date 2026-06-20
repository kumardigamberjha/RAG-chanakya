/**
 * AdminPage.jsx
 * ─────────────
 * Minimal admin UI covering:
 *  • Login (any user; redirects non-admin with a clear message)
 *  • Subject list (readable by any logged-in role)
 *  • Create subject (admin only)
 *  • Delete subject (admin only)
 *
 * Accessed via the "Admin" link that appears in the app header when
 * the user navigates to /?admin=1 or directly from App.jsx.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { authApi, login, logout, isLoggedIn, isAdmin, getRole } from '../services/auth';

// ── Tiny icon helpers (no external deps) ─────────────────────────────────────
const Icon = ({ d, size = 16, color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
       stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);
const TrashIcon = () => <Icon d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />;
const PlusIcon  = () => <Icon d="M12 5v14M5 12h14" />;
const LogoutIcon = () => <Icon d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" />;
const ShieldIcon = () => <Icon d="M12 2l9 4.5V11c0 5.25-3.75 10.13-9 11.25C6.75 21.13 3 16.25 3 11V6.5L12 2z" size={20} />;
const BookIcon  = () => <Icon d="M4 19.5A2.5 2.5 0 016.5 17H20M4 4.5A2.5 2.5 0 016.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15z" />;

// ── Sub-components ────────────────────────────────────────────────────────────

function LoginForm({ onSuccess }) {
  const [loginField, setLoginField] = useState('');
  const [password, setPassword]     = useState('');
  const [error, setError]           = useState('');
  const [loading, setLoading]       = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await login(loginField, password);
      onSuccess(data.role);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Login failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <ShieldIcon />
        <span style={styles.cardTitle}>Admin Login</span>
      </div>

      <form onSubmit={handleSubmit} style={styles.form}>
        <div style={styles.field}>
          <label style={styles.label}>Username or Email</label>
          <input
            id="admin-login-field"
            style={styles.input}
            type="text"
            value={loginField}
            onChange={e => setLoginField(e.target.value)}
            placeholder="admin"
            autoFocus
            required
          />
        </div>

        <div style={styles.field}>
          <label style={styles.label}>Password</label>
          <input
            id="admin-login-password"
            style={styles.input}
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="••••••••"
            required
          />
        </div>

        {error && <p style={styles.errorText}>{error}</p>}

        <button id="admin-login-submit" style={{ ...styles.btn, ...styles.btnPrimary }} type="submit" disabled={loading}>
          {loading ? 'Signing in…' : 'Sign In'}
        </button>
      </form>
    </div>
  );
}


const ADMIN_TENANT = 'school-alpha-01';

function AdminSourceRow({ source, subjectId, onDelete }) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting]     = useState(false);
  const [error, setError]           = useState('');

  const handleDelete = async () => {
    if (!confirming) { setConfirming(true); return; }
    setDeleting(true);
    setError('');
    try {
      await authApi.delete(
        `/admin/subjects/${subjectId}/sources/${source.id}`,
        { headers: { 'X-Tenant-ID': ADMIN_TENANT } },
      );
      onDelete(source.id);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Delete failed.');
      setConfirming(false);
    } finally {
      setDeleting(false);
    }
  };

  const visColor  = source.visibility === 'global'
    ? { bg: 'rgba(99,102,241,0.18)', fg: 'var(--p2)' }
    : { bg: 'rgba(245,158,11,0.15)', fg: 'var(--a2)' };
  const statColor = source.status === 'ready'  ? '#4ade80'
                  : source.status === 'failed' ? '#f87171' : '#fbbf24';
  const badgeBase = { fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 99 };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '4px 12px' }}>
      <div style={{ ...styles.subjectRow, background: 'var(--c0)', padding: '8px 12px' }}>
        <div style={{ ...styles.subjectInfo }}>
          <span style={{ ...styles.subjectName, fontSize: 13 }}>{source.title}</span>
        </div>
        <span style={{ ...badgeBase, background: visColor.bg, color: visColor.fg }}>
          {source.visibility}
        </span>
        <span style={{ ...badgeBase, background: 'rgba(0,0,0,0.2)', color: statColor }}>
          {source.status}
        </span>
        <span style={styles.subjectDate}>{source.created_at?.slice(0, 10)}</span>
        <button
          style={{ ...styles.iconBtn, ...(confirming ? styles.iconBtnDanger : {}) }}
          onClick={handleDelete}
          disabled={deleting}
          title={confirming ? 'Click again to confirm deletion' : 'Remove source'}
        >
          {deleting ? '…' : confirming ? '⚠ Confirm' : <TrashIcon />}
        </button>
      </div>
      {error && <p style={{ ...styles.errorText, fontSize: 12, margin: 0 }}>{error}</p>}
    </div>
  );
}


function SubjectRow({ subject, onDelete, canDelete }) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting]     = useState(false);
  const [expanded, setExpanded]     = useState(false);
  const [sources, setSources]       = useState([]);
  const [loadingSrc, setLoadingSrc] = useState(false);
  const [uploading, setUploading]   = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const fileInputRef = React.useRef(null);

  const handleDelete = async () => {
    if (!confirming) { setConfirming(true); return; }
    setDeleting(true);
    try {
      await authApi.delete(`/subjects/${subject.id}`);
      onDelete(subject.id);
    } catch (err) {
      alert(err?.response?.data?.detail || 'Delete failed.');
    } finally {
      setDeleting(false);
      setConfirming(false);
    }
  };

  const toggleSources = async () => {
    if (!expanded && sources.length === 0) {
      setLoadingSrc(true);
      try {
        const { data } = await authApi.get(`/admin/subjects/${subject.id}/sources`);
        setSources(data);
      } catch {
        setSources([]);
      } finally {
        setLoadingSrc(false);
      }
    }
    setExpanded(e => !e);
  };

  const handleSourceDeleted = (sourceId) => {
    setSources(prev => prev.filter(s => s.id !== sourceId));
  };

  const handleUploadSource = async (e) => {
    e.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file) return;
    setUploadError('');
    setUploadSuccess('');
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      await authApi.post(
        `/admin/subjects/${subject.id}/sources/upload`,
        form,
        { headers: { 'X-Tenant-ID': ADMIN_TENANT } }
      );
      setUploadSuccess(`"${file.name}" uploaded successfully! Ingestion running in background.`);
      if (fileInputRef.current) fileInputRef.current.value = '';
      
      // Refresh list
      setLoadingSrc(true);
      const { data: newSources } = await authApi.get(`/admin/subjects/${subject.id}/sources`);
      setSources(newSources);
    } catch (err) {
      setUploadError(err?.response?.data?.detail || 'Upload failed.');
    } finally {
      setUploading(false);
      setLoadingSrc(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <div style={styles.subjectRow}>
        <div style={styles.subjectIcon}><BookIcon /></div>
        <div style={styles.subjectInfo}>
          <span style={styles.subjectName}>{subject.name}</span>
          {subject.description && (
            <span style={styles.subjectDesc}>{subject.description}</span>
          )}
        </div>
        <span style={styles.subjectDate}>{subject.created_at?.slice(0, 10)}</span>
        <button
          id={`sources-toggle-${subject.id}`}
          style={{ ...styles.iconBtn, fontSize: 11, whiteSpace: 'nowrap' }}
          onClick={toggleSources}
          title="Toggle source list"
        >
          {expanded ? '▲' : '▼'} Sources{sources.length > 0 ? ` (${sources.length})` : ''}
        </button>
        {canDelete && (
          <button
            id={`delete-subject-${subject.id}`}
            style={{
              ...styles.iconBtn,
              ...(confirming ? styles.iconBtnDanger : {}),
            }}
            onClick={handleDelete}
            disabled={deleting}
            title={confirming ? 'Click again to confirm' : 'Delete subject'}
          >
            {deleting ? '…' : confirming ? '⚠ Confirm' : <TrashIcon />}
          </button>
        )}
      </div>
      {expanded && (
        <div style={{
          background: 'var(--c1)',
          border: '1px solid var(--border)',
          borderTop: 'none',
          borderRadius: '0 0 10px 10px',
          paddingTop: 4,
          paddingBottom: 4,
        }}>
          {canDelete && (
            <div style={{
              padding: '12px 16px',
              borderBottom: '1px solid var(--border)',
              background: 'var(--c2)',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}>
              <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--t2)', margin: 0, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Upload Global Source</p>
              <form onSubmit={handleUploadSource} style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <input
                  id={`admin-file-input-${subject.id}`}
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.txt,.html"
                  style={{ ...styles.input, flex: 1, padding: '6px 12px', fontSize: 13 }}
                  required
                />
                <button
                  id={`admin-upload-submit-${subject.id}`}
                  style={{ ...styles.btn, ...styles.btnPrimary, padding: '8px 16px', fontSize: 13 }}
                  type="submit"
                  disabled={uploading}
                >
                  {uploading ? 'Uploading…' : 'Upload'}
                </button>
              </form>
              {uploadError && <p style={{ ...styles.errorText, fontSize: 12, margin: 0, padding: '4px 8px' }}>{uploadError}</p>}
              {uploadSuccess && <p style={{ ...styles.errorText, color: '#4ade80', background: 'rgba(74,222,128,0.08)', borderColor: 'rgba(74,222,128,0.25)', fontSize: 12, margin: 0, padding: '4px 8px' }}>{uploadSuccess}</p>}
            </div>
          )}
          {loadingSrc && (
            <p style={{ ...styles.emptyText, padding: '8px 16px', margin: 0 }}>Loading…</p>
          )}
          {!loadingSrc && sources.length === 0 && (
            <p style={{ ...styles.emptyText, padding: '8px 16px', margin: 0 }}>No sources yet.</p>
          )}
          {sources.map(src => (
            <AdminSourceRow
              key={src.id}
              source={src}
              subjectId={subject.id}
              onDelete={handleSourceDeleted}
            />
          ))}
        </div>
      )}
    </div>
  );
}


function SubjectPanel({ role }) {
  const [subjects, setSubjects]         = useState([]);
  const [loading, setLoading]           = useState(true);
  const [creating, setCreating]         = useState(false);
  const [newName, setNewName]           = useState('');
  const [newDesc, setNewDesc]           = useState('');
  const [createError, setCreateError]   = useState('');
  const [showForm, setShowForm]         = useState(false);
  const admin = role === 'admin';

  const fetchSubjects = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await authApi.get('/subjects');
      setSubjects(data);
    } catch (err) {
      console.error('Failed to load subjects', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchSubjects(); }, [fetchSubjects]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreateError('');
    setCreating(true);
    try {
      const { data } = await authApi.post('/subjects', {
        name: newName.trim(),
        description: newDesc.trim() || null,
      });
      setSubjects(prev => [...prev, data].sort((a, b) => a.name.localeCompare(b.name)));
      setNewName('');
      setNewDesc('');
      setShowForm(false);
    } catch (err) {
      setCreateError(err?.response?.data?.detail || 'Create failed.');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleted = (id) => {
    setSubjects(prev => prev.filter(s => s.id !== id));
  };

  return (
    <div style={styles.card}>
      {/* Header */}
      <div style={styles.cardHeader}>
        <BookIcon />
        <span style={styles.cardTitle}>Subjects</span>
        <span style={styles.badge}>{subjects.length}</span>
        <div style={{ marginLeft: 'auto' }}>
          {admin && (
            <button
              id="toggle-create-subject"
              style={{ ...styles.btn, ...styles.btnPrimary, padding: '6px 14px', fontSize: 13 }}
              onClick={() => { setShowForm(f => !f); setCreateError(''); }}
            >
              <PlusIcon /> {showForm ? 'Cancel' : 'New Subject'}
            </button>
          )}
        </div>
      </div>

      {/* Create form (admin only) */}
      {admin && showForm && (
        <form onSubmit={handleCreate} style={styles.createForm}>
          <input
            id="subject-name-input"
            style={{ ...styles.input, flex: 1 }}
            type="text"
            placeholder="Subject name *"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            autoFocus
            required
          />
          <input
            id="subject-desc-input"
            style={{ ...styles.input, flex: 2 }}
            type="text"
            placeholder="Description (optional)"
            value={newDesc}
            onChange={e => setNewDesc(e.target.value)}
          />
          <button
            id="create-subject-submit"
            style={{ ...styles.btn, ...styles.btnPrimary, whiteSpace: 'nowrap' }}
            type="submit"
            disabled={creating}
          >
            {creating ? 'Creating…' : 'Create'}
          </button>
          {createError && <p style={{ ...styles.errorText, width: '100%', marginTop: 4 }}>{createError}</p>}
        </form>
      )}

      {/* Subject list */}
      <div style={styles.subjectList}>
        {loading ? (
          <p style={styles.emptyText}>Loading…</p>
        ) : subjects.length === 0 ? (
          <p style={styles.emptyText}>No subjects yet.{admin ? ' Create one above.' : ''}</p>
        ) : (
          subjects.map(s => (
            <SubjectRow
              key={s.id}
              subject={s}
              onDelete={handleDeleted}
              canDelete={admin}
            />
          ))
        )}
      </div>
    </div>
  );
}


// ── Student Upload Panel ──────────────────────────────────────────────────────

function StudentUploadPanel() {
  const [subjects, setSubjects]         = useState([]);
  const [selectedSubject, setSelected]  = useState('');
  const [sources, setSources]           = useState([]);
  const [uploading, setUploading]       = useState(false);
  const [loadingSources, setLoadingSrcs]= useState(false);
  const [error, setError]               = useState('');
  const [success, setSuccess]           = useState('');
  const fileRef                         = React.useRef(null);

  useEffect(() => {
    authApi.get('/subjects').then(({ data }) => {
      setSubjects(data);
      if (data.length > 0) setSelected(String(data[0].id));
    }).catch(() => {});
  }, []);

  const fetchSources = async (subjectId) => {
    if (!subjectId) return;
    setLoadingSrcs(true);
    try {
      const { data } = await authApi.get(`/subjects/${subjectId}/sources`);
      setSources(data);
    } catch {
      setSources([]);
    } finally {
      setLoadingSrcs(false);
    }
  };

  useEffect(() => { fetchSources(selectedSubject); }, [selectedSubject]);

  const handleSubjectChange = (e) => {
    setSelected(e.target.value);
    setError('');
    setSuccess('');
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file || !selectedSubject) return;
    setError('');
    setSuccess('');
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      await authApi.post(`/subjects/${selectedSubject}/sources/upload`, form);
      setSuccess(`"${file.name}" uploaded — ingestion running in background.`);
      if (fileRef.current) fileRef.current.value = '';
      fetchSources(selectedSubject);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const statusColor = (s) => s === 'ready' ? '#4ade80' : s === 'failed' ? '#f87171' : '#fbbf24';

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <Icon d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" size={18} />
        <span style={styles.cardTitle}>My Documents</span>
      </div>

      <form onSubmit={handleUpload} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={styles.field}>
          <label style={styles.label}>Subject</label>
          {subjects.length === 0 ? (
            <p style={{ fontSize: 13, color: 'var(--t3)' }}>No subjects available yet.</p>
          ) : (
            <select
              style={{ ...styles.input, cursor: 'pointer' }}
              value={selectedSubject}
              onChange={handleSubjectChange}
            >
              {subjects.map(s => (
                <option key={s.id} value={String(s.id)}>{s.name}</option>
              ))}
            </select>
          )}
        </div>

        <div style={styles.field}>
          <label style={styles.label}>File (PDF, TXT, HTML)</label>
          <input
            ref={fileRef}
            style={styles.input}
            type="file"
            accept=".pdf,.txt,.html"
            required
          />
        </div>

        {error   && <p style={styles.errorText}>{error}</p>}
        {success && <p style={{ ...styles.errorText, color: '#4ade80', background: 'rgba(74,222,128,0.08)', borderColor: 'rgba(74,222,128,0.25)' }}>{success}</p>}

        <button
          style={{ ...styles.btn, ...styles.btnPrimary, alignSelf: 'flex-start' }}
          type="submit"
          disabled={uploading || !selectedSubject}
        >
          {uploading ? 'Uploading…' : 'Upload'}
        </button>
      </form>

      {/* Source list */}
      <div style={{ marginTop: 24 }}>
        <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--t2)', letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 10 }}>
          Visible Sources {loadingSources ? '…' : `(${sources.length})`}
        </p>
        {sources.length === 0 && !loadingSources ? (
          <p style={styles.emptyText}>No sources yet for this subject.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {sources.map(src => (
              <div key={src.id} style={{ ...styles.subjectRow, flexWrap: 'wrap' }}>
                <div style={{ ...styles.subjectInfo }}>
                  <span style={styles.subjectName}>{src.title}</span>
                </div>
                <span style={{
                  fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 99,
                  background: src.visibility === 'global' ? 'rgba(99,102,241,0.18)' : 'rgba(245,158,11,0.15)',
                  color: src.visibility === 'global' ? 'var(--p2)' : 'var(--a2)',
                }}>
                  {src.visibility}
                </span>
                <span style={{
                  fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 99,
                  background: 'rgba(0,0,0,0.2)',
                  color: statusColor(src.status),
                }}>
                  {src.status}
                </span>
                <span style={styles.subjectDate}>{src.created_at?.slice(0, 10)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


// ── Main AdminPage ────────────────────────────────────────────────────────────

export default function AdminPage({ onBack }) {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn());
  const [role, setRole]         = useState(getRole());

  const handleLoginSuccess = (newRole) => {
    setLoggedIn(true);
    setRole(newRole);
  };

  const handleLogout = () => {
    logout();
    setLoggedIn(false);
    setRole(null);
  };

  return (
    <div style={styles.page}>
      {/* Ambient glow */}
      <div style={styles.orb} />

      {/* Top bar */}
      <header style={styles.topBar}>
        <div style={styles.topBarLeft}>
          <div style={styles.logo}>
            <ShieldIcon />
            <span>Wings of AI — Admin</span>
          </div>
          {loggedIn && (
            <span style={styles.rolePill} data-role={role}>
              {role === 'admin' ? '🛡 Admin' : '🎓 Student'}
            </span>
          )}
        </div>
        <div style={styles.topBarRight}>
          <button id="admin-back-btn" style={styles.ghostBtn} onClick={onBack}>
            ← Back to Chat
          </button>
          {loggedIn && (
            <button id="admin-logout-btn" style={styles.ghostBtn} onClick={handleLogout}>
              <LogoutIcon /> Sign Out
            </button>
          )}
        </div>
      </header>

      {/* Main content */}
      <main style={styles.main}>
        {!loggedIn ? (
          <LoginForm onSuccess={handleLoginSuccess} />
        ) : role === 'admin' ? (
          <SubjectPanel role={role} />
        ) : (
          <StudentUploadPanel />
        )}
      </main>
    </div>
  );
}


// ── Styles (design tokens match index.css) ────────────────────────────────────
const styles = {
  page: {
    position: 'fixed', inset: 0,
    background: 'var(--c0)',
    color: 'var(--t1)',
    fontFamily: "'Inter', sans-serif",
    display: 'flex', flexDirection: 'column',
    zIndex: 100,
    overflow: 'auto',
  },
  orb: {
    position: 'fixed', top: -120, left: '50%',
    transform: 'translateX(-50%)',
    width: 700, height: 700,
    background: 'radial-gradient(circle, rgba(99,102,241,0.08) 0%, transparent 70%)',
    pointerEvents: 'none', zIndex: 0,
  },
  topBar: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '12px 24px',
    borderBottom: '1px solid var(--border)',
    background: 'var(--c1)',
    position: 'sticky', top: 0, zIndex: 10,
    backdropFilter: 'blur(10px)',
  },
  topBarLeft: { display: 'flex', alignItems: 'center', gap: 12 },
  topBarRight: { display: 'flex', alignItems: 'center', gap: 8 },
  logo: {
    display: 'flex', alignItems: 'center', gap: 8,
    fontWeight: 600, fontSize: 15,
    color: 'var(--p2)',
  },
  rolePill: {
    fontSize: 11, fontWeight: 600, padding: '3px 10px',
    borderRadius: 99,
    background: 'rgba(129,140,248,0.15)',
    color: 'var(--p2)',
    border: '1px solid var(--border2)',
    letterSpacing: '0.03em',
  },
  ghostBtn: {
    background: 'transparent',
    border: '1px solid var(--border2)',
    color: 'var(--t2)',
    borderRadius: 8,
    padding: '6px 14px',
    fontSize: 13, cursor: 'pointer',
    display: 'flex', alignItems: 'center', gap: 6,
    transition: 'all 0.15s',
  },
  main: {
    flex: 1,
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    padding: '40px 16px',
    gap: 20,
    position: 'relative', zIndex: 1,
  },
  card: {
    width: '100%', maxWidth: 780,
    background: 'var(--c2)',
    border: '1px solid var(--border)',
    borderRadius: 16,
    padding: 24,
    boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
  },
  cardHeader: {
    display: 'flex', alignItems: 'center', gap: 10,
    marginBottom: 20,
  },
  cardTitle: {
    fontSize: 16, fontWeight: 600, color: 'var(--t1)',
  },
  badge: {
    fontSize: 11, fontWeight: 700,
    padding: '2px 8px', borderRadius: 99,
    background: 'rgba(99,102,241,0.18)',
    color: 'var(--p2)',
  },
  form: { display: 'flex', flexDirection: 'column', gap: 14 },
  field: { display: 'flex', flexDirection: 'column', gap: 6 },
  label: { fontSize: 12, fontWeight: 600, color: 'var(--t2)', letterSpacing: '0.04em', textTransform: 'uppercase' },
  input: {
    background: 'var(--c3)',
    border: '1px solid var(--border2)',
    borderRadius: 10,
    color: 'var(--t1)',
    padding: '10px 14px',
    fontSize: 14,
    outline: 'none',
    transition: 'border-color 0.15s',
  },
  errorText: {
    color: '#f87171', fontSize: 13,
    background: 'rgba(239,68,68,0.1)',
    border: '1px solid rgba(239,68,68,0.25)',
    borderRadius: 8,
    padding: '8px 12px',
  },
  btn: {
    borderRadius: 10, border: 'none', cursor: 'pointer',
    padding: '10px 20px', fontSize: 14, fontWeight: 600,
    display: 'inline-flex', alignItems: 'center', gap: 6,
    transition: 'opacity 0.15s',
  },
  btnPrimary: {
    background: 'var(--indigo-gradient)',
    color: '#fff',
  },
  createForm: {
    display: 'flex', flexWrap: 'wrap', gap: 10,
    marginBottom: 18,
    padding: 16,
    background: 'var(--c3)',
    borderRadius: 12,
    border: '1px solid var(--border)',
  },
  subjectList: {
    display: 'flex', flexDirection: 'column', gap: 6,
  },
  subjectRow: {
    display: 'flex', alignItems: 'center', gap: 12,
    padding: '12px 14px',
    borderRadius: 10,
    background: 'var(--c3)',
    border: '1px solid var(--border)',
    transition: 'border-color 0.15s',
  },
  subjectIcon: {
    color: 'var(--p)',
    flexShrink: 0,
  },
  subjectInfo: {
    display: 'flex', flexDirection: 'column', gap: 2, flex: 1, minWidth: 0,
  },
  subjectName: {
    fontWeight: 600, fontSize: 14, color: 'var(--t1)',
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  },
  subjectDesc: {
    fontSize: 12, color: 'var(--t2)',
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  },
  subjectDate: {
    fontSize: 11, color: 'var(--t3)',
    flexShrink: 0,
  },
  iconBtn: {
    background: 'transparent',
    border: '1px solid var(--border)',
    color: 'var(--t2)',
    borderRadius: 8,
    padding: '5px 10px',
    fontSize: 12, cursor: 'pointer',
    display: 'flex', alignItems: 'center', gap: 4,
    transition: 'all 0.15s', flexShrink: 0,
  },
  iconBtnDanger: {
    borderColor: 'rgba(239,68,68,0.5)',
    color: '#f87171',
    background: 'rgba(239,68,68,0.08)',
  },
  infoBox: {
    width: '100%', maxWidth: 780,
    background: 'rgba(245,158,11,0.08)',
    border: '1px solid rgba(245,158,11,0.25)',
    borderRadius: 12,
    padding: '12px 16px',
    fontSize: 13, color: 'var(--a2)',
  },
  emptyText: {
    textAlign: 'center', color: 'var(--t3)',
    fontSize: 14, padding: '24px 0',
  },
};
