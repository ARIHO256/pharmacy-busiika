import { useCallback, useEffect, useState } from 'react'
import client from '../../api/client'
import { appointmentApi, chatApi, paymentApi, reviewApi } from '../../api/endpoints'
import { Badge, Button, Card, Input, Modal, Select, Spinner, Table } from '../../components/ui'
import { APPT_STATUS_COLORS, fmtTime, fmtUGX } from './utils'

export default function Appointments() {
  const allowMockPayments = String(import.meta.env.VITE_ALLOW_MOCK_PAYMENTS || '').toLowerCase() === 'true'
  const [appointments, setAppointments] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const [payFor, setPayFor] = useState(null)
  const [method, setMethod] = useState('mobile_money')
  const [gateway, setGateway] = useState('mtn_momo')
  const [phone, setPhone] = useState('')
  const [paying, setPaying] = useState(false)
  const [payError, setPayError] = useState('')

  const [rateFor, setRateFor] = useState(null)
  const [rating, setRating] = useState(5)
  const [comment, setComment] = useState('')
  const [savingReview, setSavingReview] = useState(false)
  const [reviewError, setReviewError] = useState('')

  const [busyId, setBusyId] = useState(null)

  const load = useCallback(() => {
    appointmentApi
      .list()
      .then((r) =>
        setAppointments(
          [...r.data].sort((a, b) => `${b.date}T${b.start_time}`.localeCompare(`${a.date}T${a.start_time}`))
        )
      )
      .catch(() => setError('Could not load appointments.'))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const cancel = async (a) => {
    if (!window.confirm(`Cancel your appointment with Dr. ${a.doctor_name} on ${a.date}?`)) return
    setBusyId(a.id)
    setNotice('')
    try {
      await appointmentApi.act(a.id, 'cancel')
      setNotice('Appointment cancelled.')
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not cancel this appointment.')
    } finally {
      setBusyId(null)
    }
  }

  const joinVideo = async (a) => {
    setBusyId(a.id)
    try {
      const { data } = await chatApi.videoRoom(a.id)
      window.open(data.url, '_blank', 'noopener,noreferrer')
    } catch (err) {
      setError(err.response?.data?.detail || 'Video room is not available yet.')
    } finally {
      setBusyId(null)
    }
  }

  const pay = async () => {
    setPaying(true)
    setPayError('')
    try {
      const { data } = await paymentApi.initiate({
        appointment_id: payFor.id,
        method,
        phone: phone || undefined,
        gateway,
      })
      if (data.mock && !allowMockPayments && !data.simulated) {
        throw new Error('Mock payments are disabled in this build.')
      }
      if (data.mock && data.checkout_url) {
        await client.post(data.checkout_url.replace(/^\/api/, ''))
        setPayFor(null)
        setNotice(
          data.simulated
            ? 'Payment simulated successfully (demo gateway) — your appointment is confirmed.'
            : 'Payment successful — your appointment is confirmed.'
        )
        load()
      } else if (data.checkout_url) {
        setNotice(`Opening secure ${data.gateway} checkout for invoice ${data.invoice_number}.`)
        window.location.assign(data.checkout_url)
      } else {
        setPayFor(null)
        setNotice(data.instructions || `Payment request sent through ${data.gateway}. Approve it on your phone. Invoice ${data.invoice_number} will update automatically after confirmation.`)
        window.setTimeout(async () => {
          try {
            const response = await paymentApi.status(data.invoice_number)
            if (response.data.status === 'paid') {
              setNotice('Payment confirmed — your appointment is ready.')
              load()
            }
          } catch { /* webhook remains the source of truth */ }
        }, 8000)
      }
    } catch (err) {
      setPayError(err.response?.data?.detail || 'Payment failed. Please try again.')
    } finally {
      setPaying(false)
    }
  }

  const submitReview = async () => {
    setSavingReview(true)
    setReviewError('')
    try {
      await reviewApi.add(rateFor.id, { rating, comment })
      setRateFor(null)
      setNotice('Thank you for your review!')
    } catch (err) {
      setReviewError(err.response?.data?.detail || 'Could not submit your review.')
    } finally {
      setSavingReview(false)
    }
  }

  if (error && !appointments) return <Card className="text-sm text-rose-600">{error}</Card>
  if (!appointments) return <Spinner label="Loading appointments…" />

  const columns = [
    {
      key: 'patient',
      label: 'Patient',
      render: (a) => <div><div className="font-medium text-slate-800">{a.patient_name}</div>{a.booked_by && a.booked_by !== a.patient && <div className="text-xs text-slate-400">Booked by caregiver</div>}</div>,
    },
    {
      key: 'doctor',
      label: 'Doctor',
      render: (a) => (
        <div>
          <div className="font-medium text-slate-800">Dr. {a.doctor_name}</div>
          <div className="text-xs text-slate-400">{a.doctor_specialization || 'General'}</div>
        </div>
      ),
    },
    {
      key: 'when',
      label: 'When',
      render: (a) => (
        <span>
          {a.date} · {fmtTime(a.start_time)}–{fmtTime(a.end_time)}
        </span>
      ),
    },
    {
      key: 'type',
      label: 'Type',
      render: (a) => (a.type === 'online' ? '🎥 Online' : '🏥 In person'),
    },
    {
      key: 'status',
      label: 'Status',
      render: (a) => <Badge color={APPT_STATUS_COLORS[a.status] || 'slate'}>{a.status}</Badge>,
    },
    {
      key: 'reason',
      label: 'Reason',
      render: (a) => <span className="text-slate-500">{a.reason || '—'}</span>,
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (a) => (
        <div className="flex flex-wrap gap-2">
          {a.status === 'pending' && (
            <>
              <Button
                className="px-3 py-1 text-xs"
                onClick={() => {
                  setPayFor(a)
                  setMethod('mobile_money')
                  setGateway('mtn_momo')
                  setPhone('')
                  setPayError('')
                }}
              >
                Pay
              </Button>
              <Button
                variant="outline"
                className="px-3 py-1 text-xs"
                disabled={busyId === a.id}
                onClick={() => cancel(a)}
              >
                Cancel
              </Button>
            </>
          )}
          {a.status === 'confirmed' && (
            <>
              {a.type === 'online' && (
                <Button
                  className="px-3 py-1 text-xs"
                  disabled={busyId === a.id}
                  onClick={() => joinVideo(a)}
                >
                  Join Video
                </Button>
              )}
              <Button
                variant="outline"
                className="px-3 py-1 text-xs"
                disabled={busyId === a.id}
                onClick={() => cancel(a)}
              >
                Cancel
              </Button>
            </>
          )}
          {a.status === 'completed' && (
            <>
              <span className="text-xs text-slate-400 self-center">💊 Prescription in Prescriptions</span>
              <Button
                variant="outline"
                className="px-3 py-1 text-xs"
                onClick={() => {
                  setRateFor(a)
                  setRating(5)
                  setComment('')
                  setReviewError('')
                }}
              >
                Rate
              </Button>
            </>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      {notice && <Card className="text-sm text-emerald-700 bg-emerald-50 border-emerald-200">{notice}</Card>}
      {error && <Card className="text-sm text-rose-600">{error}</Card>}

      <Card title="My appointments">
        <Table columns={columns} rows={appointments} empty="No appointments yet — find a doctor to book one." />
      </Card>

      <Modal open={!!payFor} onClose={() => setPayFor(null)} title="Pay for appointment">
        {payFor && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              Dr. {payFor.doctor_name} · {payFor.date} · {fmtTime(payFor.start_time)}
            </p>
            <Select label="Payment method" value={method} onChange={(e) => {
              const next = e.target.value
              setMethod(next)
              setGateway(next === 'mobile_money' ? 'mtn_momo' : next === 'card' ? 'flutterwave' : allowMockPayments ? 'mock' : 'mtn_momo')
            }}>
              <option value="mobile_money">Mobile Money</option>
              <option value="card">Card</option>
              {allowMockPayments && <option value="wallet">Development wallet</option>}
            </Select>
            <Select label="Payment provider" value={gateway} onChange={(e) => setGateway(e.target.value)}>
              {method === 'mobile_money' && <>
                <option value="mtn_momo">MTN Mobile Money</option>
                <option value="airtel_money">Airtel Money</option>
                <option value="flutterwave">Flutterwave Mobile Money</option>
              </>}
              {method === 'card' && <>
                <option value="flutterwave">Flutterwave Card</option>
                <option value="paystack">Paystack Card</option>
              </>}
              {method === 'wallet' && allowMockPayments && <option value="mock">Development-only mock gateway</option>}
            </Select>
            {method === 'mobile_money' && (
              <Input
                label="Phone number"
                placeholder="e.g. 0772 123 456"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            )}
            {payError && <p className="text-sm text-rose-600">{payError}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setPayFor(null)}>
                Cancel
              </Button>
              <Button onClick={pay} disabled={paying}>
                {paying ? 'Processing…' : 'Pay now'}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal open={!!rateFor} onClose={() => setRateFor(null)} title="Rate your visit">
        {rateFor && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              Dr. {rateFor.doctor_name} · {rateFor.date}
            </p>
            <div>
              <span className="block text-sm font-medium text-slate-600 mb-1">Rating</span>
              <div className="flex gap-1">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setRating(n)}
                    className={`text-2xl transition ${n <= rating ? 'text-amber-400' : 'text-slate-200'}`}
                    aria-label={`${n} star${n > 1 ? 's' : ''}`}
                  >
                    ★
                  </button>
                ))}
              </div>
            </div>
            <label className="block">
              <span className="block text-sm font-medium text-slate-600 mb-1">Comment</span>
              <textarea
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                rows={3}
                placeholder="How was your experience?"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
            </label>
            {reviewError && <p className="text-sm text-rose-600">{reviewError}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setRateFor(null)}>
                Cancel
              </Button>
              <Button onClick={submitReview} disabled={savingReview}>
                {savingReview ? 'Submitting…' : 'Submit review'}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
