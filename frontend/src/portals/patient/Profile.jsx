import { useEffect, useState } from 'react'
import client from '../../api/client'
import { authApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import { Button, Card, Input, Select, Spinner } from '../../components/ui'

const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

export default function Profile() {
  const { setUser } = useAuth()
  const [account, setAccount] = useState(null)
  const [profile, setProfile] = useState(null)
  const [error, setError] = useState('')
  const [accountMsg, setAccountMsg] = useState('')
  const [profileMsg, setProfileMsg] = useState('')
  const [savingAccount, setSavingAccount] = useState(false)
  const [savingProfile, setSavingProfile] = useState(false)

  useEffect(() => {
    Promise.all([authApi.me(), client.get('/auth/me/profile/')])
      .then(([me, prof]) => {
        setAccount({
          first_name: me.data.first_name || '',
          last_name: me.data.last_name || '',
          phone: me.data.phone || '',
        })
        const p = prof.data || {}
        setProfile({
          dob: p.dob || '',
          gender: p.gender || '',
          blood_group: p.blood_group || '',
          allergies: p.allergies || '',
          medical_history: p.medical_history || '',
          emergency_contact: p.emergency_contact || '',
          address: p.address || '',
        })
      })
      .catch(() => setError('Could not load your profile.'))
  }, [])

  const saveAccount = async (e) => {
    e.preventDefault()
    setSavingAccount(true)
    setAccountMsg('')
    try {
      const { data } = await authApi.updateMe(account)
      setUser(data)
      setAccountMsg('Account details saved.')
    } catch {
      setAccountMsg('Could not save account details.')
    } finally {
      setSavingAccount(false)
    }
  }

  const saveProfile = async (e) => {
    e.preventDefault()
    setSavingProfile(true)
    setProfileMsg('')
    try {
      // DRF DateField rejects ""; send null when dob is blank
      await authApi.updateProfile({ ...profile, dob: profile.dob || null })
      setProfileMsg('Medical profile saved.')
    } catch {
      setProfileMsg('Could not save medical profile.')
    } finally {
      setSavingProfile(false)
    }
  }

  if (error) return <Card className="text-sm text-rose-600">{error}</Card>
  if (!account || !profile) return <Spinner label="Loading your profile…" />

  const setP = (k) => (e) => setProfile({ ...profile, [k]: e.target.value })

  return (
    <div className="space-y-6 max-w-3xl">
      <Card title="Account details">
        <form onSubmit={saveAccount} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="First name"
              value={account.first_name}
              onChange={(e) => setAccount({ ...account, first_name: e.target.value })}
            />
            <Input
              label="Last name"
              value={account.last_name}
              onChange={(e) => setAccount({ ...account, last_name: e.target.value })}
            />
          </div>
          <Input
            label="Phone"
            placeholder="e.g. 0772 123 456"
            value={account.phone}
            onChange={(e) => setAccount({ ...account, phone: e.target.value })}
          />
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={savingAccount}>
              {savingAccount ? 'Saving…' : 'Save account'}
            </Button>
            {accountMsg && <span className="text-sm text-slate-500">{accountMsg}</span>}
          </div>
        </form>
      </Card>

      <Card title="Medical profile">
        <form onSubmit={saveProfile} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Input label="Date of birth" type="date" value={profile.dob} onChange={setP('dob')} />
            <Select label="Gender" value={profile.gender} onChange={setP('gender')}>
              <option value="">—</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
            </Select>
            <Select label="Blood group" value={profile.blood_group} onChange={setP('blood_group')}>
              <option value="">—</option>
              {BLOOD_GROUPS.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </Select>
          </div>
          <label className="block">
            <span className="block text-sm font-medium text-slate-600 mb-1">Allergies</span>
            <textarea
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              rows={2}
              placeholder="e.g. Penicillin, peanuts…"
              value={profile.allergies}
              onChange={setP('allergies')}
            />
          </label>
          <label className="block">
            <span className="block text-sm font-medium text-slate-600 mb-1">Medical history</span>
            <textarea
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              rows={3}
              placeholder="Chronic conditions, past surgeries…"
              value={profile.medical_history}
              onChange={setP('medical_history')}
            />
          </label>
          <Input
            label="Emergency contact"
            placeholder="Name & phone number"
            value={profile.emergency_contact}
            onChange={setP('emergency_contact')}
          />
          <Input
            label="Address"
            placeholder="Village / town, district"
            value={profile.address}
            onChange={setP('address')}
          />
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={savingProfile}>
              {savingProfile ? 'Saving…' : 'Save medical profile'}
            </Button>
            {profileMsg && <span className="text-sm text-slate-500">{profileMsg}</span>}
          </div>
        </form>
      </Card>
    </div>
  )
}
