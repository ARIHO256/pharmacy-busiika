import React, { useEffect, useState } from 'react'
import { prescriptionApi, servicesApi } from '../../../api/endpoints'
import { Badge, Button, Card, Modal, Select, Spinner, Table } from '../../../components/ui'
import { fmtDT } from './helpers'

export default function Prescriptions() {
  const [prescriptions, setPrescriptions] = useState(null)
  const [detail, setDetail] = useState(null) // fetched detail object
  const [detailOpen, setDetailOpen] = useState(false)
  const [sendOpen, setSendOpen] = useState(false)
  const [pharmacies, setPharmacies] = useState([])
  const [pharmacyId, setPharmacyId] = useState('')
  const [sending, setSending] = useState(false)
  const [notice, setNotice] = useState(null) // {type:'success'|'error', text}

  const load = async () => {
    try {
      const { data } = await prescriptionApi.list()
      setPrescriptions(data)
    } catch {
      setPrescriptions([])
    }
  }

  useEffect(() => {
    load()
  }, [])

  const openDetail = async (rx) => {
    setDetail(null)
    setDetailOpen(true)
    try {
      const { data } = await prescriptionApi.detail(rx.id)
      setDetail(data)
    } catch {
      setDetail({ ...rx, items: [] })
    }
  }

  const openSend = async () => {
    setSendOpen(true)
    setPharmacyId('')
    try {
      const { data } = await servicesApi.providers('pharmacies')
      setPharmacies(data)
    } catch {
      setPharmacies([])
    }
  }

  const sendToPharmacy = async (e) => {
    e.preventDefault()
    if (!pharmacyId || !detail) return
    setSending(true)
    try {
      await prescriptionApi.sendToPharmacy(detail.id, pharmacyId)
      setNotice({ type: 'success', text: 'Prescription sent to pharmacy successfully.' })
      setSendOpen(false)
    } catch (err) {
      setNotice({
        type: 'error',
        text: err?.response?.data?.detail || 'Failed to send prescription',
      })
    } finally {
      setSending(false)
    }
  }

  if (prescriptions === null) return <Spinner label="Loading prescriptions…" />

  return (
    <div className="space-y-4">
      {notice && (
        <div
          className={`rounded-lg px-4 py-3 text-sm flex items-center justify-between ${
            notice.type === 'success'
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              : 'bg-rose-50 text-rose-700 border border-rose-200'
          }`}
        >
          <span>{notice.text}</span>
          {notice.type === 'success' && <Badge color="green">Sent</Badge>}
          <button className="ml-3 text-lg leading-none" onClick={() => setNotice(null)}>
            &times;
          </button>
        </div>
      )}

      <Card title="My Prescriptions">
        <Table
          empty="No prescriptions yet. Prescriptions from your doctor will appear here."
          columns={[
            { key: 'id', label: '#', render: (r) => `#${r.id}` },
            { key: 'doctor_name', label: 'Doctor' },
            {
              key: 'item_count',
              label: 'Items',
              render: (r) => `${r.item_count} medicine${r.item_count === 1 ? '' : 's'}`,
            },
            { key: 'created_at', label: 'Date', render: (r) => fmtDT(r.created_at) },
            {
              key: 'actions',
              label: '',
              render: (r) => (
                <Button variant="outline" onClick={() => openDetail(r)}>
                  View
                </Button>
              ),
            },
          ]}
          rows={prescriptions}
        />
      </Card>

      {/* detail modal */}
      <Modal open={detailOpen} onClose={() => setDetailOpen(false)} title="Prescription Details" wide>
        {detail === null ? (
          <Spinner />
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-slate-500">Doctor</span>
                <p className="font-medium text-slate-800">{detail.doctor_name}</p>
              </div>
              <div>
                <span className="text-slate-500">Date</span>
                <p className="font-medium text-slate-800">{fmtDT(detail.created_at)}</p>
              </div>
            </div>
            {detail.notes && (
              <div className="text-sm">
                <span className="text-slate-500">Notes</span>
                <p className="text-slate-700">{detail.notes}</p>
              </div>
            )}
            <Table
              empty="No items on this prescription."
              columns={[
                { key: 'medicine_name', label: 'Medicine' },
                { key: 'dosage', label: 'Dosage' },
                { key: 'frequency', label: 'Frequency' },
                { key: 'duration', label: 'Duration' },
                { key: 'quantity', label: 'Qty' },
              ]}
              rows={detail.items || []}
            />
            <div className="flex justify-end">
              <Button onClick={openSend}>Send to Pharmacy</Button>
            </div>
          </div>
        )}
      </Modal>

      {/* send-to-pharmacy modal */}
      <Modal open={sendOpen} onClose={() => setSendOpen(false)} title="Send to Pharmacy">
        <form onSubmit={sendToPharmacy} className="space-y-4">
          <Select
            label="Choose a pharmacy"
            value={pharmacyId}
            onChange={(e) => setPharmacyId(e.target.value)}
            required
          >
            <option value="">Select pharmacy…</option>
            {pharmacies.map((p) => (
              <option key={p.id} value={p.id}>
                {p.org_name}
                {p.address ? ` — ${p.address}` : ''}
              </option>
            ))}
          </Select>
          {pharmacies.length === 0 && (
            <p className="text-xs text-slate-400">No verified pharmacies available right now.</p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setSendOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={sending || !pharmacyId}>
              {sending ? 'Sending…' : 'Send'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
