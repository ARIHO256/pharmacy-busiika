import { useEffect, useRef, useState } from 'react'
import { chatApi } from '../../api/endpoints'
import { Button, Card, Spinner } from '../../components/ui'
import { useAuth } from '../../auth/AuthContext'

const convoTitle = (c) => c.other_party_name || c.patient_name || `Conversation #${c.id}`

export default function Consult() {
  const { user } = useAuth()
  const [conversations, setConversations] = useState(null)
  const [active, setActive] = useState(null)
  const [messages, setMessages] = useState(null)
  const [text, setText] = useState('')
  const [file, setFile] = useState(null)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef(null)
  const fileRef = useRef(null)

  useEffect(() => {
    chatApi.conversations().then((r) => {
      const list = r.data || []
      setConversations(list)
      if (list.length) setActive(list[0])
    }).catch(() => setConversations([]))
  }, [])

  // Poll messages every 5s for the active conversation
  useEffect(() => {
    if (!active) return undefined
    let cancelled = false
    const load = () =>
      chatApi.messages(active.id).then((r) => {
        if (!cancelled) setMessages(r.data || [])
      }).catch(() => { if (!cancelled) setMessages([]) })
    setMessages(null)
    load()
    const t = setInterval(load, 5000)
    return () => { cancelled = true; clearInterval(t) }
  }, [active?.id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages?.length])

  async function send(e) {
    e.preventDefault()
    if (!text.trim() && !file) return
    setSending(true)
    setError('')
    try {
      const fd = new FormData()
      if (text.trim()) fd.append('text', text.trim())
      if (file) fd.append('attachment', file)
      await chatApi.send(active.id, fd)
      setText('')
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
      const r = await chatApi.messages(active.id)
      setMessages(r.data || [])
    } catch (err) {
      setError(err.response?.data?.detail || 'Message could not be sent')
    } finally {
      setSending(false)
    }
  }

  if (!conversations) return <Spinner label="Loading conversations…" />

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 h-[calc(100vh-9rem)] min-h-[480px]">
      {/* Conversation list */}
      <Card title="Conversations" className="md:col-span-1 overflow-hidden flex flex-col [&>div:last-child]:!p-0 [&>div:last-child]:overflow-y-auto">
        {conversations.length === 0 ? (
          <p className="text-sm text-slate-400 p-5">No conversations yet.</p>
        ) : (
          <ul>
            {conversations.map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => setActive(c)}
                  className={`w-full text-left px-5 py-3.5 border-b border-slate-50 hover:bg-slate-50 transition ${
                    active?.id === c.id ? 'bg-primary-50' : ''
                  }`}
                >
                  <div className="text-sm font-medium text-slate-700">{convoTitle(c)}</div>
                  {c.last_message?.text && <div className="text-xs text-slate-400 truncate mt-0.5">{c.last_message.text}</div>}
                  {!!c.unread_count && (
                    <span className="inline-block mt-1 px-2 py-0.5 rounded-full bg-primary-600 text-white text-[10px] font-medium">
                      {c.unread_count} new
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Thread */}
      <Card
        title={active ? convoTitle(active) : 'Select a conversation'}
        className="md:col-span-2 flex flex-col overflow-hidden [&>div:last-child]:flex-1 [&>div:last-child]:flex [&>div:last-child]:flex-col [&>div:last-child]:!p-0"
      >
        {!active ? (
          <div className="flex-1 flex items-center justify-center text-sm text-slate-400">Pick a conversation on the left.</div>
        ) : !messages ? (
          <Spinner label="Loading messages…" />
        ) : (
          <>
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
              {messages.length === 0 && (
                <p className="text-sm text-slate-400 text-center py-8">No messages yet — say hello.</p>
              )}
              {messages.map((m) => {
                const mine = m.sender === user?.id || m.sender_id === user?.id || m.is_mine
                return (
                  <div key={m.id} className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm ${
                        mine ? 'bg-primary-600 text-white rounded-br-sm' : 'bg-slate-100 text-slate-700 rounded-bl-sm'
                      }`}
                    >
                      {m.text && <p className="whitespace-pre-wrap break-words">{m.text}</p>}
                      {m.attachment && (
                        <a
                          href={m.attachment}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={`block mt-1 text-xs underline ${mine ? 'text-primary-100' : 'text-primary-600'}`}
                        >
                          📎 Attachment
                        </a>
                      )}
                      <div className={`text-[10px] mt-1 ${mine ? 'text-primary-200' : 'text-slate-400'}`}>
                        {m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                      </div>
                    </div>
                  </div>
                )
              })}
              <div ref={bottomRef} />
            </div>

            <form onSubmit={send} className="border-t border-slate-100 px-4 py-3">
              {error && <p className="text-xs text-rose-600 mb-2">{error}</p>}
              <div className="flex items-center gap-2">
                <label className="cursor-pointer text-slate-400 hover:text-slate-600 px-2 text-lg" title="Attach file">
                  📎
                  <input
                    ref={fileRef}
                    type="file"
                    className="hidden"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                  />
                </label>
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Type a message…"
                  className="flex-1 px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
                <Button type="submit" disabled={sending || (!text.trim() && !file)}>
                  {sending ? '…' : 'Send'}
                </Button>
              </div>
              {file && (
                <div className="mt-2 text-xs text-slate-500 flex items-center gap-2">
                  <span className="truncate">📎 {file.name}</span>
                  <button type="button" className="text-rose-500" onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = '' }}>
                    remove
                  </button>
                </div>
              )}
            </form>
          </>
        )}
      </Card>
    </div>
  )
}
