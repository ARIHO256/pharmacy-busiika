import React, { useCallback, useEffect, useState } from 'react'
import client from '../../../api/client'
import { servicesApi } from '../../../api/endpoints'
import { Badge, Button, Card, Input, Modal, Select, Spinner, Table } from '../../../components/ui'
import { fmtD, statusColor, ugx } from './helpers'

export default function Hospitals() {
  const [tab, setTab] = useState('browse') // browse | bookings
  const [hospitals, setHospitals] = useState(null)
  const [expanded, setExpanded] = useState(null) // hospital id currently expanded
  const [services, setServices] = useState({}) // hospitalId -> services[]
  const [beds, setBeds] = useState({}) // hospitalId -> beds[]
  const [detailLoading, setDetailLoading] = useState(false)
  const [bookOpen, setBookOpen] = useState(false)
  const [bookHospital, setBookHospital] = useState(null)
  const [bookServiceId, setBookServiceId] = useState('')
  const [bookDate, setBookDate] = useState('')
  const [booking, setBooking] = useState(false)
  const [bookings, setBookings] = useState(null)
  const [notice, setNotice] = useState(null)

  useEffect(() => {
    servicesApi
      .providers('hospitals')
      .then(({ data }) => setHospitals(data))
      .catch(() => setHospitals([]))
  }, [])

  const toggleExpand = async (h) => {
    if (expanded === h.id) {
      setExpanded(null)
      return
    }
    setExpanded(h.id)
    setDetailLoading(true)
    try {
      const [svcRes, bedRes] = await Promise.all([
        servicesApi.hospitalServices({ hospital: h.id }),
        client.get('/services/beds/', { params: { hospital: h.id } }),
      ])
      setServices((s) => ({ ...s, [h.id]: svcRes.data }))
      setBeds((b) => ({ ...b, [h.id]: bedRes.data }))
    } catch {
      setServices((s) => ({ ...s, [h.id]: [] }))
      setBeds((b) => ({ ...b, [h.id]: [] }))
    } finally {
      setDetailLoading(false)
    }
  }

  const openBook = (h) => {
    setBookHospital(h)
    setBookServiceId('')
    setBookDate('')
    setBookOpen(true)
    if (!services[h.id]) {
      servicesApi
        .hospitalServices({ hospital: h.id })
        .then(({ data }) => setServices((s) => ({ ...s, [h.id]: data })))
        .catch(() => setServices((s) => ({ ...s, [h.id]: [] })))
    }
  }

  const confirmBooking = async (e) => {
    e.preventDefault()
    if (!bookHospital || !bookDate) return
    setBooking(true)
    try {
      await servicesApi.bookHospital({
        hospital_id: bookHospital.id,
        service_id: bookServiceId || null,
        date: bookDate,
      })
      setNotice({ type: 'success', text: `Booking at ${bookHospital.org_name} submitted.` })
      setBookOpen(false)
    } catch (err) {
      setNotice({ type: 'error', text: err?.response?.data?.detail || 'Booking failed' })
      setBookOpen(false)
    } finally {
      setBooking(false)
    }
  }

  const loadBookings = useCallback(async () => {
    setBookings(null)
    try {
      const { data } = await client.get('/services/hospital-bookings/')
      setBookings(data)
    } catch {
      setBookings([])
    }
  }, [])

  useEffect(() => {
    if (tab === 'bookings') loadBookings()
  }, [tab, loadBookings])

  const bedBoard = (hospitalId) => {
    const list = beds[hospitalId] || []
    if (detailLoading && expanded === hospitalId) return <Spinner label="Loading beds…" />
    if (!list.length)
      return <div className="text-xs text-slate-400 py-3">No bed information published.</div>
    const wards = list.reduce((acc, b) => {
      ;(acc[b.ward] = acc[b.ward] || []).push(b)
      return acc
    }, {})
    return (
      <div className="space-y-3">
        {Object.entries(wards).map(([ward, wardBeds]) => (
          <div key={ward}>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
              {ward}
            </p>
            <div className="flex flex-wrap gap-2">
              {wardBeds.map((b) => (
                <span
                  key={b.id}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium border ${
                    b.is_occupied
                      ? 'bg-rose-50 text-rose-700 border-rose-200'
                      : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  }`}
                >
                  {b.label} · {b.is_occupied ? 'Occupied' : 'Free'}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    )
  }

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
          <button className="ml-3 text-lg leading-none" onClick={() => setNotice(null)}>
            &times;
          </button>
        </div>
      )}

      <div className="flex gap-2">
        <Button variant={tab === 'browse' ? 'primary' : 'outline'} onClick={() => setTab('browse')}>
          Hospitals
        </Button>
        <Button
          variant={tab === 'bookings' ? 'primary' : 'outline'}
          onClick={() => setTab('bookings')}
        >
          My Bookings
        </Button>
      </div>

      {tab === 'browse' && (
        <>
          {hospitals === null ? (
            <Spinner label="Loading hospitals…" />
          ) : hospitals.length === 0 ? (
            <Card>
              <div className="text-sm text-slate-400 text-center py-8">
                No verified hospitals available right now.
              </div>
            </Card>
          ) : (
            <div className="space-y-4">
              {hospitals.map((h) => (
                <Card key={h.id}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h4 className="font-semibold text-slate-800">{h.org_name}</h4>
                      {h.address && <p className="text-xs text-slate-500 mt-0.5">{h.address}</p>}
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" onClick={() => toggleExpand(h)}>
                        {expanded === h.id ? 'Hide details' : 'Services & beds'}
                      </Button>
                      <Button onClick={() => openBook(h)}>Book</Button>
                    </div>
                  </div>

                  {expanded === h.id && (
                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                          Services
                        </p>
                        {detailLoading ? (
                          <Spinner label="Loading services…" />
                        ) : (
                          <Table
                            empty="No services listed."
                            columns={[
                              { key: 'name', label: 'Service' },
                              { key: 'price', label: 'Price', render: (r) => ugx(r.price) },
                            ]}
                            rows={services[h.id] || []}
                          />
                        )}
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                          Bed availability
                        </p>
                        {bedBoard(h.id)}
                      </div>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'bookings' && (
        <Card title="My Bookings">
          {bookings === null ? (
            <Spinner label="Loading bookings…" />
          ) : (
            <Table
              empty="No hospital bookings yet."
              columns={[
                { key: 'id', label: '#', render: (r) => `#${r.id}` },
                { key: 'hospital_name', label: 'Hospital' },
                {
                  key: 'service_name',
                  label: 'Service',
                  render: (r) => r.service_name || '—',
                },
                { key: 'date', label: 'Date', render: (r) => fmtD(r.date) },
                {
                  key: 'status',
                  label: 'Status',
                  render: (r) => <Badge color={statusColor(r.status)}>{r.status}</Badge>,
                },
              ]}
              rows={bookings}
            />
          )}
        </Card>
      )}

      {/* booking modal */}
      <Modal open={bookOpen} onClose={() => setBookOpen(false)} title="Book Hospital Service">
        {bookHospital && (
          <form onSubmit={confirmBooking} className="space-y-4">
            <p className="text-sm text-slate-700">
              <span className="text-slate-500">Hospital: </span>
              <span className="font-medium">{bookHospital.org_name}</span>
            </p>
            <Select
              label="Service (optional)"
              value={bookServiceId}
              onChange={(e) => setBookServiceId(e.target.value)}
            >
              <option value="">General visit</option>
              {(services[bookHospital.id] || []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} — {ugx(s.price)}
                </option>
              ))}
            </Select>
            <Input
              label="Date"
              type="date"
              value={bookDate}
              onChange={(e) => setBookDate(e.target.value)}
              required
            />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setBookOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={booking || !bookDate}>
                {booking ? 'Booking…' : 'Confirm Booking'}
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}
