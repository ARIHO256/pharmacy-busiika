import { usePharmacyPermissions } from './PharmacyPermissions'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Table, Textarea } from '../../components/ui'
import { errMsg, fmtDate, LoadingOrError, money, useApi } from './shared'

export default function ShiftClosing() {
  const allows = usePharmacyPermissions()
  const { user } = useAuth()
  const shifts = useApi(() => servicesApi.pharmacyShifts())
  const [cash, setCash] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const active = shifts.data?.find((shift) => shift.status === 'open' && shift.cashier === user?.id)
  const base = user?.role === 'pharmacy' ? '/pharmacy' : '/pharmacist'

  async function submit(event) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      if (active) await servicesApi.closePharmacyShift(active.id, { closing_cash: Number(cash), notes })
      else await servicesApi.openPharmacyShift({ opening_float: Number(cash) })
      setCash('')
      setNotes('')
      shifts.reload()
    } catch (failure) {
      setError(errMsg(failure))
    } finally {
      setBusy(false)
    }
  }

  return <LoadingOrError loading={shifts.loading} error={shifts.error}>
    <div className="space-y-5">
      {allows('shift_manage') && <Card title={active ? 'Close your shift' : 'Open a shift'}>
        <form className="max-w-lg space-y-4" onSubmit={submit}>
          {error && <Alert tone="danger">{error}</Alert>}
          {active && <p>Expected cash <strong>{money(active.expected_cash)}</strong></p>}
          <Input required min="0" type="number" label={active ? 'Cash counted at closing' : 'Opening cash float'}
            value={cash} onChange={(event) => setCash(event.target.value)} />
          {active && <Textarea label="Notes on any difference" maxLength={2000} value={notes} onChange={(event) => setNotes(event.target.value)} />}
          <Button type="submit" disabled={busy}>{busy ? 'Saving…' : active ? 'Close and reconcile' : 'Open shift'}</Button>
        </form>
      </Card>}
      <Card title="Recent shifts" actions={user?.role !== 'cashier' && allows('stocktake') && <Link className="text-primary-700 underline" to={`${base}/stocktake`}>Open physical stocktake</Link>}>
        <Table rows={shifts.data || []} empty="No shifts yet" columns={[
          { key: 'cashier_name', label: 'Staff member' },
          { key: 'opened_at', label: 'Opened', render: (row) => fmtDate(row.opened_at) },
          { key: 'status', label: 'Status' },
          { key: 'expected_cash', label: 'Expected cash', render: (row) => money(row.expected_cash) },
          { key: 'closing_cash', label: 'Counted cash', render: (row) => row.closing_cash == null ? '—' : money(row.closing_cash) },
          { key: 'variance', label: 'Difference', render: (row) => row.status === 'closed' ? money(row.variance) : '—' },
          { key: 'notes', label: 'Notes' },
        ]} />
      </Card>
    </div>
  </LoadingOrError>
}
