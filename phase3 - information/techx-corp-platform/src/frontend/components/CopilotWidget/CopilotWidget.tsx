// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
//
// Shopping Copilot chat widget (AIO02 service, embedded in the storefront).
// Talks to the copilot via the same-origin edge route /api/copilot/* (Envoy -> shopping-copilot).
// Self-contained: inline styles, no extra deps. Renders client-side only to avoid SSR/hydration.

import { useEffect, useRef, useState } from 'react';

type Role = 'user' | 'assistant';
interface Message {
  role: Role;
  content: string;
  token?: string | null; // set on assistant messages that need a write confirmation
}

const STORAGE_USER = 'copilot_user_id';
const STORAGE_SESSION = 'copilot_session_id';

const randomId = () =>
  'xxxxxxxx'.replace(/x/g, () => Math.floor(Math.random() * 16).toString(16)) + '-' + Date.now().toString(16);

const CopilotWidget = () => {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: 'Xin chào! Tôi là trợ lý mua sắm. Bạn cần tìm gì hôm nay?' },
  ]);
  const userId = useRef<string>('');
  const sessionId = useRef<string>('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);
    try {
      userId.current = localStorage.getItem(STORAGE_USER) || randomId();
      localStorage.setItem(STORAGE_USER, userId.current);
      sessionId.current = localStorage.getItem(STORAGE_SESSION) || randomId();
      localStorage.setItem(STORAGE_SESSION, sessionId.current);
    } catch {
      userId.current = randomId();
      sessionId.current = randomId();
    }
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, open]);

  const post = async (path: string, body: Record<string, unknown>) => {
    const res = await fetch(`/api/copilot/${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (res.status === 429) throw new Error('rate_limited');
    return res.json();
  };

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setMessages(m => [...m, { role: 'user', content: text }]);
    setLoading(true);
    try {
      const r = await post('chat', { message: text, session_id: sessionId.current, user_id: userId.current });
      if (r.session_id) sessionId.current = r.session_id;
      setMessages(m => [
        ...m,
        { role: 'assistant', content: r.reply || 'Xin lỗi, tôi chưa có câu trả lời.', token: r.token || null },
      ]);
    } catch (e) {
      const msg = (e as Error).message === 'rate_limited'
        ? 'Bạn thao tác hơi nhanh — vui lòng thử lại sau giây lát.'
        : 'Dịch vụ tạm thời không khả dụng, thử lại sau nhé.';
      setMessages(m => [...m, { role: 'assistant', content: msg }]);
    } finally {
      setLoading(false);
    }
  };

  const confirm = async (token: string) => {
    setLoading(true);
    try {
      const r = await post('confirm', { session_id: sessionId.current, token, confirmed: true });
      setMessages(m => [...m, { role: 'assistant', content: r.reply || 'Đã xử lý.' }]);
    } catch {
      setMessages(m => [...m, { role: 'assistant', content: 'Không xác nhận được, thử lại sau.' }]);
    } finally {
      setLoading(false);
    }
  };

  if (!mounted) return null;

  const accent = '#5a2a9e';

  return (
    <div style={{ position: 'fixed', right: 20, bottom: 20, zIndex: 1000, fontFamily: 'inherit' }}>
      {open && (
        <div
          style={{
            width: 360,
            maxWidth: 'calc(100vw - 40px)',
            height: 520,
            maxHeight: 'calc(100vh - 120px)',
            display: 'flex',
            flexDirection: 'column',
            background: '#fff',
            borderRadius: 14,
            boxShadow: '0 12px 40px rgba(0,0,0,0.25)',
            overflow: 'hidden',
            marginBottom: 12,
          }}
        >
          <div style={{ background: accent, color: '#fff', padding: '12px 16px', fontWeight: 600, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>Trợ lý mua sắm</span>
            <button onClick={() => setOpen(false)} aria-label="Đóng" style={{ background: 'none', border: 'none', color: '#fff', fontSize: 20, cursor: 'pointer', lineHeight: 1 }}>×</button>
          </div>
          <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: 14, background: '#f7f7fb' }}>
            {messages.map((m, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: 10 }}>
                <div
                  style={{
                    maxWidth: '80%',
                    padding: '9px 12px',
                    borderRadius: 12,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    fontSize: 14,
                    lineHeight: 1.45,
                    background: m.role === 'user' ? accent : '#fff',
                    color: m.role === 'user' ? '#fff' : '#1a1a1a',
                    border: m.role === 'user' ? 'none' : '1px solid #e5e5ef',
                  }}
                >
                  {m.content}
                  {m.token && (
                    <div style={{ marginTop: 8 }}>
                      <button onClick={() => confirm(m.token as string)} disabled={loading} style={{ background: accent, color: '#fff', border: 'none', borderRadius: 8, padding: '6px 12px', cursor: 'pointer', fontSize: 13 }}>
                        Xác nhận
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && <div style={{ color: '#888', fontSize: 13, padding: '2px 4px' }}>Đang soạn…</div>}
          </div>
          <div style={{ display: 'flex', padding: 10, borderTop: '1px solid #ececf3', background: '#fff' }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') send(); }}
              placeholder="Nhập tin nhắn…"
              maxLength={1000}
              style={{ flex: 1, border: '1px solid #ddd', borderRadius: 8, padding: '9px 11px', fontSize: 14, outline: 'none' }}
            />
            <button onClick={send} disabled={loading || !input.trim()} style={{ marginLeft: 8, background: accent, color: '#fff', border: 'none', borderRadius: 8, padding: '0 16px', cursor: 'pointer', fontWeight: 600 }}>
              Gửi
            </button>
          </div>
        </div>
      )}
      <button
        onClick={() => setOpen(o => !o)}
        aria-label="Mở trợ lý mua sắm"
        style={{
          width: 58,
          height: 58,
          borderRadius: '50%',
          background: accent,
          color: '#fff',
          border: 'none',
          boxShadow: '0 6px 20px rgba(0,0,0,0.3)',
          cursor: 'pointer',
          fontSize: 26,
          float: 'right',
        }}
      >
        {open ? '×' : '💬'}
      </button>
    </div>
  );
};

export default CopilotWidget;
