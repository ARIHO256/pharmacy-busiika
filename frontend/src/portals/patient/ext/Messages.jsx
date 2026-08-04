import React, { useCallback, useEffect, useRef, useState } from 'react'
import { chatApi } from '../../../api/endpoints'
import { useAuth } from '../../../auth/AuthContext'
import { Button, Card, Spinner, Badge } from '../../../components/ui'
import { fmtDT } from './helpers'

export default function Messages() {
  const { user } = useAuth()
  const [conversations, setConversations] = useState(null)
  const [active, setActive] = useState(null) // conversation object
  const [messages, setMessages] = useState([])
  const [loadingThread, setLoadingThread] = useState(false)
  const [text, setText] = useState('')
  const [file, setFile] = useState(null)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef(null)
  const fileRef = useRef(null)

  const loadConversations = useCallback(async () => {
    try {
      const { data } = await chatApi.conversations()
      setConversations(data)
    } catch {
      setConversations([])
    }
  }, [])

  useEffect(() => {
    loadConversations()
  }, [loadConversations])

  const loadMessages = useCallback(async (conv) => {
    try {
      const { data } = await chatApi.messages(conv.id)
      setMessages(data)
    } catch {
      setMessages([])
    }
  }, [])

  const openConversation = async (conv) => {
    setActive(conv)
    setLoadingThread(true)
    await loadMessages(conv)
    setLoadingThread(false)
    loadConversations() // refresh unread counts (server marks read on GET)
  }

  // poll messages every 5s while a thread is open
  useEffect(() => {
    if (!active) return undefined
    const t = setInterval(() => {
      loadMessages(active)
      loadConversations()
    }, 5000)
    return () => clearInterval(t)
  }, [active, loadMessages, loadConversations])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (e) => {
    e.preventDefault()
    if (!active || (!text.trim() && !file)) return
    setSending(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('text', text)
      if (file) fd.append('attachment', file)
      await chatApi.send(active.id, fd)
      setText('')
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
      await loadMessages(active)
      loadConversations()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to send message')
    } finally {
      setSending(false)
    }
  }

  if (conversations === null) return <Spinner label="Loading conversations…" />

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* conversation list */}
      <Card title="Conversations" className="md:col-span-1">
        {conversations.length === 0 ? (
          <div className="text-sm text-slate-400 text-center py-8">
            No conversations yet. Book an appointment with a doctor to start chatting.
          </div>
        ) : (
          <ul className="divide-y divide-slate-100 -m-2">
            {conversations.map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => openConversation(c)}
                  className={`w-full text-left px-3 py-3 rounded-lg transition ${
                    active?.id === c.id ? 'bg-primary-50' : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-sm text-slate-800 truncate">
                      {c.other_party_name}
                    </span>
                    {c.unread_count > 0 && (
                      <Badge color="green">{c.unread_count}</Badge>
                    )}
                  </div>
                  <div className="text-xs text-slate-400 truncate mt-0.5">
                    {c.last_message?.text || 'No messages yet'}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* thread */}
      <Card
        title={active ? active.other_party_name : 'Chat'}
        className="md:col-span-2"
      >
        {!active ? (
          <div className="text-sm text-slate-400 text-center py-16">
            Select a conversation to view messages.
          </div>
        ) : loadingThread ? (
          <Spinner label="Loading messages…" />
        ) : (
          <div className="flex flex-col h-[60vh]">
            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {messages.length === 0 && (
                <div className="text-sm text-slate-400 text-center py-8">
                  No messages yet — say hello!
                </div>
              )}
              {messages.map((m) => {
                const mine = m.sender === user?.id
                return (
                  <div key={m.id} className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[75%] rounded-xl px-4 py-2 text-sm shadow-sm ${
                        mine
                          ? 'bg-primary-600 text-white'
                          : 'bg-slate-100 text-slate-800'
                      }`}
                    >
                      {m.text && <p className="whitespace-pre-wrap">{m.text}</p>}
                      {m.attachment && (
                        <a
                          href={m.attachment}
                          target="_blank"
                          rel="noreferrer"
                          className={`block mt-1 text-xs underline ${mine ? 'text-primary-100' : 'text-primary-600'}`}
                        >
                          📎 Attachment
                        </a>
                      )}
                      <div className={`text-[10px] mt-1 ${mine ? 'text-primary-100' : 'text-slate-400'}`}>
                        {fmtDT(m.created_at)}
                      </div>
                    </div>
                  </div>
                )
              })}
              <div ref={bottomRef} />
            </div>

            {error && <p className="text-xs text-rose-600 mt-2">{error}</p>}

            <form onSubmit={send} className="mt-3 flex items-center gap-2">
              <input
                ref={fileRef}
                type="file"
                className="hidden"
                id="msg-attachment"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              <label
                htmlFor="msg-attachment"
                className="cursor-pointer px-3 py-2 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 text-sm"
                title="Attach a file"
              >
                📎
              </label>
              {file && (
                <span className="text-xs text-slate-500 max-w-[120px] truncate">{file.name}</span>
              )}
              <input
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Type a message…"
                className="flex-1 px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
              <Button type="submit" disabled={sending || (!text.trim() && !file)}>
                {sending ? 'Sending…' : 'Send'}
              </Button>
            </form>
          </div>
        )}
      </Card>
    </div>
  )
}
