import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { appointmentApi, authApi, reviewApi } from '../../api/endpoints'
import { Button, Card, Input, Modal, Select, Spinner, Stars } from '../../components/ui'
import { fmtTime, fmtUGX, todayISO } from './utils'

export default function DoctorDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [doctor, setDoctor] = useState(null)
  const [reviews, setReviews] = useState(null)
  const [dependents, setDependents] = useState([])
  const [patientId, setPatientId] = useState('')
  const [error, setError] = useState('')

  const [date, setDate] = useState(todayISO())
  const [slots, setSlots] = useState(null)
  const [slotsError, setSlotsError] = useState('')

  const [booking, setBooking] = useState(null) // selected slot
  const [type, setType] = useState('offline')
  const [reason, setReason] = useState('')
  const [consentAcknowledged, setConsentAcknowledged] = useState(false)
  const [saving, setSaving] = useState(false)
  const [bookError, setBookError] = useState('')

  useEffect(() => {
    Promise.all([authApi.doctor(id), reviewApi.forDoctor(id), authApi.dependents()])
      .then(([d, r, family]) => {
        setDoctor(d.data)
        setReviews(r.data)
        setDependents((family.data || []).filter((row) => row.status === 'active' && row.can_book))
      })
      .catch(() => setError('Could not load this healthcare professional.'))
  }, [id])

  useEffect(() => {
    if (!date) return
    setSlots(null)
    setSlotsError('')
    appointmentApi
      .slots(id, date)
      .then((r) => setSlots(r.data.slots || []))
      .catch(() => setSlotsError('Could not load slots for this date.'))
  }, [id, date])

  const book = async () => {
    setSaving(true)
    setBookError('')
    try {
      await appointmentApi.book({
        doctor_id: Number(id),
        date,
        start_time: booking.start,
        type,
        reason,
        consent_acknowledged: consentAcknowledged,
        ...(patientId ? { patient_id: Number(patientId) } : {}),
      })
      navigate('/patient/appointments')
    } catch (err) {
      setBookError(err.response?.data?.detail || 'Booking failed. The slot may have just been taken.')
    } finally {
      setSaving(false)
    }
  }

  if (error) return <Card className="text-sm text-rose-600">{error}</Card>
  if (!doctor || !reviews) return <Spinner label="Loading professional profile…" />

  return (
    <div className="space-y-6">
      <Link to="/patient/doctors" className="text-sm text-primary-600 hover:underline">
        ← Back to healthcare professionals
      </Link>

      <Card>
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-800">
              {['doctor', 'dentist'].includes(doctor.role) ? 'Dr. ' : ''}{doctor.first_name} {doctor.last_name}
            </h2>
            <div className="text-primary-600 text-sm mt-1">{doctor.specialization || 'General'}</div>
            <div className="mt-3 text-sm text-slate-500 space-y-1">
              <div>🏥 {doctor.hospital || 'Independent practice'}</div>
              <div>⏳ {doctor.experience_years || 0} years experience</div>
              <div className="font-medium text-slate-700">{fmtUGX(doctor.fees)} per consultation</div>
            </div>
            <div className="mt-2">
              <Stars value={doctor.average_rating} />
            </div>
          </div>
          <span className="text-5xl">🩺</span>
        </div>
        {doctor.bio && <p className="mt-4 text-sm text-slate-600 leading-relaxed">{doctor.bio}</p>}
      </Card>

      <Card title="Book an appointment">
        <Input
          label="Choose a date"
          type="date"
          min={todayISO()}
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="max-w-xs"
        />
        <div className="mt-4">
          {slotsError ? (
            <p className="text-sm text-rose-600">{slotsError}</p>
          ) : !slots ? (
            <Spinner label="Loading available slots…" />
          ) : slots.length === 0 ? (
            <p className="text-sm text-slate-400 py-4">No free slots on this date. Try another day.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {slots.map((s) => (
                <button
                  key={s.start}
                  onClick={() => {
                    setBooking(s)
                    setType('offline')
                    setReason('')
                    setConsentAcknowledged(false)
                    setPatientId('')
                    setBookError('')
                  }}
                  className="px-3 py-1.5 rounded-lg border border-primary-200 text-primary-700 text-sm hover:bg-primary-600 hover:text-white hover:border-primary-600 transition"
                >
                  {fmtTime(s.start)} – {fmtTime(s.end)}
                </button>
              ))}
            </div>
          )}
        </div>
      </Card>

      <Card title={`Reviews (${reviews.length})`}>
        {reviews.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-6">No reviews yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {reviews.map((r) => (
              <li key={r.id} className="py-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-700">{r.patient}</span>
                  <Stars value={r.rating} />
                </div>
                {r.comment && <p className="text-sm text-slate-500 mt-1">{r.comment}</p>}
                <div className="text-xs text-slate-400 mt-1">{String(r.created_at).slice(0, 10)}</div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Modal open={!!booking} onClose={() => setBooking(null)} title="Confirm booking">
        {booking && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              {['doctor', 'dentist'].includes(doctor.role) ? 'Dr. ' : ''}{doctor.first_name} {doctor.last_name} · {date} · {fmtTime(booking.start)} –{' '}
              {fmtTime(booking.end)}
            </p>
            <Select label="Patient receiving care" value={patientId} onChange={(e) => setPatientId(e.target.value)}>
              <option value="">Myself</option>
              {dependents.map((dependent) => <option key={dependent.id} value={dependent.patient_id}>{dependent.patient_name} · {dependent.relationship.replaceAll('_', ' ')}</option>)}
            </Select>
            <Select label="Consultation type" value={type} onChange={(e) => setType(e.target.value)}>
              <option value="offline">In person (offline)</option>
              <option value="online">Video call (online)</option>
            </Select>
            <label className="block">
              <span className="block text-sm font-medium text-slate-600 mb-1">Reason for visit</span>
              <textarea
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                rows={3}
                placeholder="Briefly describe your symptoms or reason…"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            <label className="flex items-start gap-3 rounded-xl border border-primary-100 bg-primary-50 p-3 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={consentAcknowledged}
                onChange={(e) => setConsentAcknowledged(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
              />
              <span>
                I confirm that I am authorized to consent for {patientId ? 'the selected dependent' : 'myself'} and allow this healthcare professional to access the minimum health information needed for this {type === 'online' ? 'telemedicine' : 'clinical'} consultation.
              </span>
            </label>
            {bookError && <p className="text-sm text-rose-600">{bookError}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setBooking(null)}>
                Back
              </Button>
              <Button onClick={book} disabled={saving || !consentAcknowledged}>
                {saving ? 'Booking…' : `Book · ${fmtUGX(doctor.fees)}`}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
