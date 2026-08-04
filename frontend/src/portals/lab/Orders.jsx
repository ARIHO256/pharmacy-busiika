import { useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Table } from '../../components/ui'
import { errMsg, ErrorNote, fmtDate, LoadingOrError, StatusBadge, useApi } from '../pharmacy/shared'

const nextStep = {
  booked: { status: 'sample_collected', label: 'Collect sample' },
  ready_for_collection: { status: 'sample_collected', label: 'Collect sample' },
  sample_collected: { status: 'sample_received', label: 'Receive specimen' },
  sample_received: { status: 'processing', label: 'Start processing' },
}

export default function Orders() {
  const { data: orders, loading, error, reload } = useApi(() => servicesApi.labOrdersManage())
  const [updating, setUpdating] = useState(null)
  const [resultModal, setResultModal] = useState(null) // order being completed / edited
  const [file, setFile] = useState(null)
  const [notes, setNotes] = useState('')
  const [structured, setStructured] = useState({ name: '', value_numeric: '', value_text: '', unit: '', reference_low: '', reference_high: '', interpretation: 'unknown', status: 'final' })
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  const advance = async (order, status) => {
    setUpdating(order.id)
    try {
      const fd = new FormData()
      fd.append('status', status)
      await servicesApi.updateLabOrder(order.id, fd)
      reload()
    } catch (e) {
      alert(errMsg(e))
    } finally {
      setUpdating(null)
    }
  }

  const openComplete = (order) => {
    setResultModal(order)
    setFile(null)
    setNotes(order.result_notes || '')
    setStructured({ name: order.test_name || '', value_numeric: '', value_text: '', unit: '', reference_low: '', reference_high: '', interpretation: 'unknown', status: 'final' })
    setSaveError('')
  }

  const saveResult = async (e) => {
    e.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      const fd = new FormData()
      fd.append('status', 'awaiting_validation')
      if (file) fd.append('result_file', file)
      fd.append('result_notes', notes)
      await servicesApi.updateLabOrder(resultModal.id, fd)
      if (structured.name && (structured.value_numeric !== '' || structured.value_text.trim())) {
        const payload = { ...structured }
        for (const key of ['value_numeric', 'reference_low', 'reference_high']) {
          if (payload[key] === '') payload[key] = null
        }
        await servicesApi.publishLabResult(resultModal.id, { ...payload, release: true })
      }
      setResultModal(null)
      reload()
    } catch (err) {
      setSaveError(errMsg(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      <Card title="Lab orders">
        <Table
          empty="No lab orders yet"
          columns={[
            { key: 'id', label: 'Order', render: (o) => <span className="font-medium text-slate-800">#{o.id}</span> },
            { key: 'patient_name', label: 'Patient' },
            { key: 'test_name', label: 'Test' },
            { key: 'referring_doctor_name', label: 'Referred by', render: (o) => o.referring_doctor_name || 'Self requested' },
            { key: 'created_at', label: 'Booked', render: (o) => fmtDate(o.created_at) },
            { key: 'status', label: 'Status', render: (o) => <StatusBadge status={o.status} /> },
            {
              key: 'result_file',
              label: 'Result',
              render: (o) =>
                o.result_file ? (
                  <a href={o.result_file} target="_blank" rel="noreferrer" className="text-primary-600 hover:underline">
                    Download
                  </a>
                ) : (
                  <span className="text-slate-300">—</span>
                ),
            },
            {
              key: 'actions',
              label: 'Update',
              render: (o) => (
                <div className="flex gap-2">
                  {nextStep[o.status] && (
                    <Button
                      variant="outline"
                      disabled={updating === o.id}
                      onClick={() => advance(o, nextStep[o.status].status)}
                    >
                      {nextStep[o.status].label}
                    </Button>
                  )}
                  {(['processing', 'awaiting_validation', 'validated', 'completed', 'amended'].includes(o.status)) && (
                    <Button onClick={() => openComplete(o)}>
                      {o.result_released ? 'Amend result' : 'Enter & release result'}
                    </Button>
                  )}
                </div>
              ),
            },
          ]}
          rows={orders || []}
        />
      </Card>

      <Modal
        open={!!resultModal}
        onClose={() => setResultModal(null)}
        title={`Result for order #${resultModal?.id} — ${resultModal?.test_name || ''}`}
      >
        <form onSubmit={saveResult} className="space-y-4">
          <ErrorNote error={saveError} />
          <Input
            label="Result file (PDF / image)"
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <Alert tone="info" title="Structured result">Structured values can be searched, trended and safely interpreted; the PDF remains available as the original report.</Alert>
          <Input label="Result name" value={structured.name} onChange={(e) => setStructured({ ...structured, name: e.target.value })} />
          <div className="grid grid-cols-2 gap-3">
            <Input label="Numeric value" type="number" step="any" value={structured.value_numeric} onChange={(e) => setStructured({ ...structured, value_numeric: e.target.value, value_text: e.target.value ? '' : structured.value_text })} />
            <Input label="Unit" value={structured.unit} onChange={(e) => setStructured({ ...structured, unit: e.target.value })} placeholder="e.g. mmol/L" />
          </div>
          <Input label="Text value (when not numeric)" value={structured.value_text} onChange={(e) => setStructured({ ...structured, value_text: e.target.value, value_numeric: e.target.value ? '' : structured.value_numeric })} />
          <div className="grid grid-cols-2 gap-3">
            <Input label="Reference low" type="number" step="any" value={structured.reference_low} onChange={(e) => setStructured({ ...structured, reference_low: e.target.value })} />
            <Input label="Reference high" type="number" step="any" value={structured.reference_high} onChange={(e) => setStructured({ ...structured, reference_high: e.target.value })} />
          </div>
          <Select label="Interpretation" value={structured.interpretation} onChange={(e) => setStructured({ ...structured, interpretation: e.target.value })}>
            <option value="unknown">Not interpreted</option><option value="normal">Normal</option><option value="high">High</option><option value="low">Low</option><option value="abnormal">Abnormal</option><option value="critical">Critical</option>
          </Select>
          <label className="block">
            <span className="block text-sm font-medium text-slate-600 mb-1">Result notes</span>
            <textarea
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              rows={4}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Summary of findings for the patient…"
            />
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" type="button" onClick={() => setResultModal(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : 'Validate and release result'}
            </Button>
          </div>
        </form>
      </Modal>
    </LoadingOrError>
  )
}
