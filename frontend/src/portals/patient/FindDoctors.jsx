import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../../api/endpoints'
import { Button, Card, Input, Spinner, Stars } from '../../components/ui'
import { fmtUGX } from './utils'

export default function FindDoctors() {
  const [doctors, setDoctors] = useState(null)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [minFee, setMinFee] = useState('')
  const [maxFee, setMaxFee] = useState('')

  const load = (params = {}) => {
    setDoctors(null)
    setError('')
    const q = {}
    if (params.search) q.search = params.search
    if (params.min_fee) q.min_fee = params.min_fee
    if (params.max_fee) q.max_fee = params.max_fee
    authApi
      .doctors(q)
      .then((r) => setDoctors(r.data))
      .catch(() => setError('Could not load doctors. Please try again.'))
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const apply = (e) => {
    e?.preventDefault()
    load({ search: search.trim(), min_fee: minFee, max_fee: maxFee })
  }

  return (
    <div className="space-y-6">
      <Card>
        <form onSubmit={apply} className="flex flex-col sm:flex-row gap-3 sm:items-end">
          <Input
            label="Search"
            placeholder="Name or specialization…"
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
        <Spinner label="Finding doctors…" />
      ) : doctors?.length === 0 ? (
        <Card className="text-sm text-slate-400 text-center py-10">
          No doctors match your search. Try adjusting the filters.
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
                    Dr. {d.first_name} {d.last_name}
                  </div>
                  <div className="text-sm text-primary-600">{d.specialization || 'General'}</div>
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
