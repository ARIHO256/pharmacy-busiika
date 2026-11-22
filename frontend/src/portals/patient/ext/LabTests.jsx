import React, { useCallback, useEffect, useState } from 'react'
import { servicesApi } from '../../../api/endpoints'
import { Alert, Badge, Button, Card, Modal, Select, Spinner } from '../../../components/ui'
import { fmtDT, statusColor, ugx } from './helpers'

const closedOrderStatuses = new Set(['completed', 'amended', 'cancelled'])
const statusLabel = (status) => status === 'booked' ? 'Booked' : status.replaceAll('_', ' ')

export default function LabTests() {
  const [viewTest, setViewTest] = useState(null)
  const [labs, setLabs] = useState([])
  const [labId, setLabId] = useState('')
  const [tests, setTests] = useState(null)
  const [bookTest, setBookTest] = useState(null) // test being booked
  const [booking, setBooking] = useState(false)
  const [orders, setOrders] = useState(null)
  const [bookingError, setBookingError] = useState('')
  const [ordersError, setOrdersError] = useState(false)
  const [notice, setNotice] = useState(null)

  useEffect(() => {
    servicesApi
      .providers('labs')
      .then(({ data }) => setLabs(data))
      .catch(() => {})
  }, [])

  const loadTests = useCallback(async () => {
    setTests(null)
    try {
      const params = labId ? { lab: labId } : {}
      const { data } = await servicesApi.labTests(params)
      setTests(data)
    } catch {
      setTests([])
    }
  }, [labId])

  useEffect(() => {
    loadTests()
  }, [loadTests])

  const loadOrders = useCallback(async () => {
    setOrdersError(false)
    try {
      const { data } = await servicesApi.myLabOrders()
      setOrders(data)
    } catch {
      setOrdersError(true)
      setOrders((current) => current ?? [])
    }
  }, [])

  useEffect(() => {
    loadOrders()
  }, [loadOrders])

  const confirmBooking = async () => {
    if (!bookTest || booking) return
    setBookingError('')
    setBooking(true)
    try {
      const { data: order } = await servicesApi.bookLab({ lab_id: bookTest.lab, test_id: bookTest.id })
      setOrders((current) => [order, ...(current || []).filter((item) => item.id !== order.id)])
      setNotice({ type: 'success', text: `${bookTest.name} booked successfully.` })
      setBookTest(null)
    } catch (err) {
      setBookingError(err?.response?.data?.detail || 'Booking failed. Please try again.')
    } finally {
      setBooking(false)
    }
  }

  const bookingsByTest = new Map()
  for (const order of orders || []) {
    const key = `${order.lab}:${order.test}`
    const bookings = bookingsByTest.get(key) || []
    bookings.push(order)
    bookingsByTest.set(key, bookings)
  }
  const viewedBookings = viewTest ? bookingsByTest.get(`${viewTest.lab}:${viewTest.id}`) || [] : []

  const labName = (id) => labs.find((l) => l.id === id)?.org_name || `Lab #${id}`

  return (
    <div className="space-y-4">
      {notice && (
        <div
          role="status"
          className={`rounded-lg px-4 py-3 text-sm flex items-center justify-between ${
            notice.type === 'success'
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              : 'bg-rose-50 text-rose-700 border border-rose-200'
          }`}
        >
          <span>{notice.text}</span>
          <button className="ml-3 text-lg leading-none" aria-label="Dismiss booking confirmation" onClick={() => setNotice(null)}>
            &times;
          </button>
        </div>
      )}

      {orders?.some?.((o) => o.has_critical_result) && (
        <Alert tone="danger" title="Critical result available">A laboratory result needs prompt clinical review. Contact your doctor or an appropriate emergency service if you feel unwell.</Alert>
      )}

      {ordersError && <Alert tone="warning">Could not check existing bookings. <button type="button" className="underline" onClick={loadOrders}>Retry</button></Alert>}
      <Card>
        <Select
          label="Choose a lab"
          value={labId}
          onChange={(e) => setLabId(e.target.value)}
        >
          <option value="">All labs</option>
          {labs.map((l) => (
            <option key={l.id} value={l.id}>
              {l.org_name}
              {l.address ? ` — ${l.address}` : ''}
            </option>
          ))}
        </Select>
      </Card>

      {tests === null ? (
        <Spinner label="Loading tests…" />
      ) : tests.length === 0 ? (
        <Card>
          <div className="text-sm text-slate-400 text-center py-8">
            No tests available for the selected lab.
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {tests.map((t) => {
            const bookings = bookingsByTest.get(`${t.lab}:${t.id}`) || []
            const activeOrder = bookings.find((order) => !order.result_released && !closedOrderStatuses.has(order.status))
            return (
              <Card key={t.id}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h4 className="font-semibold text-slate-800">{t.name}</h4>
                    <p className="text-xs text-slate-500 mt-0.5">{labName(t.lab)}</p>
                  </div>
                  <span className="text-sm font-bold text-primary-600 whitespace-nowrap">
                    {ugx(t.price)}
                  </span>
                </div>
                {t.description && (
                  <p className="text-xs text-slate-500 line-clamp-2 mt-2">{t.description}</p>
                )}
                {t.sample_type && (
                  <div className="mt-2">
                    <Badge color="slate">Sample: {t.sample_type}</Badge>
                  </div>
                )}
                <div className="mt-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {activeOrder && <Badge color={statusColor(activeOrder.status)}>{statusLabel(activeOrder.status)}</Badge>}
                    {bookings.length > 0 && <Button variant="outline" onClick={() => setViewTest(t)}>
                      {bookings.length === 1 ? `View booking #${bookings[0].id}` : 'View bookings'}
                    </Button>}
                    {!activeOrder && <Button className={bookings.length ? undefined : 'w-full'} disabled={orders === null || ordersError}
                      onClick={() => { setBookingError(''); setBookTest(t) }}>Book this test</Button>}
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}
      <Modal open={Boolean(viewTest)} onClose={() => setViewTest(null)} title={viewTest ? `Bookings for ${viewTest.name}` : 'Lab booking'}>
        <div className="space-y-4">
          {viewedBookings.map((order) => (
            <Card key={order.id} title={`Booking #${order.id}`} subtitle={fmtDT(order.created_at)}
              actions={<Badge color={statusColor(order.status)}>{statusLabel(order.status)}</Badge>}>
              <p className="text-sm text-slate-600">{order.lab_name}</p>
              {order.result_released && <div className="mt-2 space-y-2 text-sm">
                {(order.results || []).map((result) => <p key={result.id}>
                  <strong>{result.name}:</strong> {result.value_text || `${result.value_numeric ?? ''} ${result.unit || ''}`.trim()}
                  {result.is_superseded && <span className="text-slate-500"> · Superseded</span>}
                </p>)}
                {order.result_file && <a href={order.result_file} target="_blank" rel="noreferrer" className="text-primary-700 underline">Open laboratory report</a>}
                {!order.result_file && !order.results?.length && order.result_notes && <p>{order.result_notes}</p>}
              </div>}
            </Card>
          ))}
        </div>
      </Modal>

      {/* booking modal */}
      <Modal open={!!bookTest} onClose={() => { if (!booking) setBookTest(null) }} title="Confirm Booking">
        {bookTest && (
          <div className="space-y-4">
            {bookingError && <Alert tone="danger">{bookingError}</Alert>}
            <div className="text-sm space-y-1">
              <p>
                <span className="text-slate-500">Test: </span>
                <span className="font-medium text-slate-800">{bookTest.name}</span>
              </p>
              <p>
                <span className="text-slate-500">Lab: </span>
                <span className="font-medium text-slate-800">{labName(bookTest.lab)}</span>
              </p>
              <p>
                <span className="text-slate-500">Price: </span>
                <span className="font-bold text-primary-600">{ugx(bookTest.price)}</span>
              </p>
              {bookTest.sample_type && (
                <p>
                  <span className="text-slate-500">Sample: </span>
                  <span className="text-slate-700">{bookTest.sample_type}</span>
                </p>
              )}
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <h4 className="text-sm font-semibold text-slate-800">Test description</h4>
              <p className="mt-1 whitespace-pre-line text-sm text-slate-600">{bookTest.description?.trim() || 'The laboratory has not supplied a description for this test.'}</p>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" disabled={booking} onClick={() => setBookTest(null)}>
                Cancel
              </Button>
              <Button onClick={confirmBooking} disabled={booking}>
                {booking ? 'Booking…' : 'Confirm Booking'}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
