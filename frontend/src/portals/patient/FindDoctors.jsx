import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../../api/endpoints'
import { Badge, Button, Card, Input, Select, Spinner, Stars } from '../../components/ui'
import { fmtUGX } from './utils'

export default function FindDoctors() {
  const [doctors, setDoctors] = useState(null)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [minFee, setMinFee] = useState('')
  const [maxFee, setMaxFee] = useState('')
  const [role, setRole] = useState('')

  const load = (params = {}) => {
    setDoctors(null)
    setError('')
    const q = {}
    if (params.search) q.search = params.search
    if (params.min_fee) q.min_fee = params.min_fee
    if (params.max_fee) q.max_fee = params.max_fee
    if (params.role) q.role = params.role
    authApi
      .doctors(q)
      .then((r) => setDoctors(r.data))
      .catch(() => setError('Could not load healthcare professionals. Please try again.'))
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const apply = (e) => {
    e?.preventDefault()
    load({ search: search.trim(), min_fee: minFee, max_fee: maxFee, role })
  }

  return (
    <div className="space-y-6">
      <Card>
        <form onSubmit={apply} className="flex flex-col sm:flex-row gap-3 sm:items-end">
          <Input
            label="Search"
            placeholder="Name, cadre, specialty or workplace…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1"
          />
          <Input
            label="Min fee (UGX)"
            type="number"
            min="0"
            placeholder="0"
            value={minFee}
            onChange={(e) => setMinFee(e.target.value)}
            className="sm:w-36"
          />
          <Select label="Professional type" value={role} onChange={(e) => setRole(e.target.value)} className="sm:w-48">
            <option value="">All verified professionals</option>
            <option value="doctor">Doctors</option>
            <option value="clinical_officer">Clinical officers</option>
            <option value="dentist">Dentists</option>
            <option value="physiotherapist">Physiotherapists</option>
            <option value="nutritionist">Nutritionists</option>
            <option value="psychologist">Psychologists</option>
          </Select>
          <Input
            label="Max fee (UGX)"
            type="number"
            min="0"
            placeholder="Any"
            value={maxFee}
            onChange={(e) => setMaxFee(e.target.value)}
            className="sm:w-36"
          />
          <Button type="submit">Search</Button>
        </form>
      </Card>

      {error && <Card className="text-sm text-rose-600">{error}</Card>}

      {!doctors && !error ? (
        <Spinner label="Finding verified healthcare professionals…" />
      ) : doctors?.length === 0 ? (
        <Card className="text-sm text-slate-400 text-center py-10">
          No verified professionals match your search. Try adjusting the filters.
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {doctors?.map((d) => (
            <Link
              key={d.id}
              to={`/patient/doctors/${d.id}`}
              className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:border-primary-300 hover:shadow transition"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-semibold text-slate-800">
                    {['doctor', 'dentist'].includes(d.role) ? 'Dr. ' : ''}{d.first_name} {d.last_name}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <Badge color="blue">{d.role_label || d.cadre}</Badge>
                    <span className="text-sm text-primary-600">{d.specialization || d.cadre || 'General care'}</span>
                  </div>
                </div>
                <span className="text-2xl">🩺</span>
              </div>
              <div className="mt-3 text-sm text-slate-500 space-y-1">
                <div>🏥 {d.hospital || 'Independent practice'}</div>
                <div>⏳ {d.experience_years || 0} yrs experience</div>
                <div className="font-medium text-slate-700">{fmtUGX(d.fees)} per visit</div>
              </div>
              <div className="mt-3">
                <Stars value={d.average_rating} />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
