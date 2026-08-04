import React, { useCallback, useEffect, useState } from 'react'
import { servicesApi } from '../../../api/endpoints'
import { Alert, Badge, Button, Card, Modal, Select, Spinner, Table } from '../../../components/ui'
import { fmtDT, statusColor, ugx } from './helpers'

export default function LabTests() {
  const [tab, setTab] = useState('book') // book | orders
  const [labs, setLabs] = useState([])
  const [labId, setLabId] = useState('')
  const [tests, setTests] = useState(null)
  const [bookTest, setBookTest] = useState(null) // test being booked
  const [booking, setBooking] = useState(false)
  const [orders, setOrders] = useState(null)
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
    if (tab === 'book') loadTests()
  }, [tab, loadTests])

  const loadOrders = useCallback(async () => {
    setOrders(null)
    try {
      const { data } = await servicesApi.myLabOrders()
      setOrders(data)
    } catch {
      setOrders([])
    }
  }, [])

  useEffect(() => {
    if (tab === 'orders') loadOrders()
  }, [tab, loadOrders])

  const confirmBooking = async () => {
    if (!bookTest) return
    setBooking(true)
    try {
      await servicesApi.bookLab({ lab_id: bookTest.lab, test_id: bookTest.id })
      setNotice({ type: 'success', text: `${bookTest.name} booked successfully.` })
      setBookTest(null)
    } catch (err) {
      setNotice({ type: 'error', text: err?.response?.data?.detail || 'Booking failed' })
      setBookTest(null)
    } finally {
      setBooking(false)
    }
  }

  const labName = (id) => labs.find((l) => l.id === id)?.org_name || `Lab #${id}`

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

      {orders?.some?.((o) => o.has_critical_result) && (
        <Alert tone="danger" title="Critical result available">A laboratory result needs prompt clinical review. Contact your doctor or an appropriate emergency service if you feel unwell.</Alert>
      )}

      <div className="flex gap-2">
        <Button variant={tab === 'book' ? 'primary' : 'outline'} onClick={() => setTab('book')}>
          Book a Test
        </Button>
        <Button variant={tab === 'orders' ? 'primary' : 'outline'} onClick={() => setTab('orders')}>
          My Lab Orders
        </Button>
      </div>

      {tab === 'book' && (
        <>
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
              {tests.map((t) => (
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
                    <Button className="w-full" onClick={() => setBookTest(t)}>
                      Book this test
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'orders' && (
        <Card title="My Lab Orders">
          {orders === null ? (
            <Spinner label="Loading lab orders…" />
          ) : (
            <Table
              empty="No lab orders yet. Book a test to get started."
              columns={[
                { key: 'id', label: '#', render: (r) => `#${r.id}` },
                { key: 'test_name', label: 'Test' },
                { key: 'lab_name', label: 'Lab' },
                {
                  key: 'status',
                  label: 'Status',
                  render: (r) => <Badge color={statusColor(r.status)}>{r.status}</Badge>,
                },
                { key: 'created_at', label: 'Booked', render: (r) => fmtDT(r.created_at) },
                {
                  key: 'result_file',
                  label: 'Result',
                  render: (r) =>
                    r.status === 'completed' ? (
                      <div className="space-y-1">
                        {(r.results || []).map((result) => (
                          <div key={result.id} className={`rounded-lg px-2 py-1 text-xs ${result.interpretation === 'critical' ? 'bg-rose-50 text-rose-700' : 'bg-slate-50 text-slate-700'}`}>
                            <strong>{result.name}:</strong> {result.value_text || `${result.value_numeric ?? ''} ${result.unit || ''}`.trim()}
                            <span className="ml-1 opacity-70">({result.interpretation})</span>
                          </div>
                        ))}
                        {r.result_file && <a href={r.result_file} target="_blank" rel="noreferrer" className="text-primary-600 underline text-xs">Original report</a>}
                        {!r.result_file && !(r.results || []).length && <span className="text-xs text-slate-400">No result content</span>}
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400">Pending</span>
                    ),
                },
              ]}
              rows={orders}
            />
          )}
        </Card>
      )}

      {/* booking modal */}
      <Modal open={!!bookTest} onClose={() => setBookTest(null)} title="Confirm Booking">
        {bookTest && (
          <div className="space-y-4">
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
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setBookTest(null)}>
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
