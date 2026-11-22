import { useState } from 'react'
import { interoperabilityApi } from '../../api/endpoints'
import { Alert, Card, Input, Spinner, Table } from '../../components/ui'
import { useRemote } from '../staff/shared'

const system = 'https://www.nda.or.ug/drug-register/'
const archive = 'https://www.nda.or.ug/wp-content/uploads/2024/06/NATIONAL-DRUG-REGISTER-OF-UGANDA-HUMAN-MEDICINES-JUNE-2024.pdf'

export default function MedicineRegister() {
  const register = useRemote(() => interoperabilityApi.terminology({
    system, category: 'registered_medicine_reference', limit: 200,
  }), [])
  const [query, setQuery] = useState('')
  const search = query.trim().toLowerCase()
  const rows = (register.data || []).filter((item) =>
    [item.display, item.code, item.metadata?.ingredient, item.metadata?.strength].some((value) =>
      value?.toLowerCase().includes(search),
    ),
  )

  return <Card title="Uganda medicine register" icon="pill"
    subtitle="National Drug Authority human medicines · June 2024 snapshot"
    actions={<a href={archive} target="_blank" rel="noreferrer" className="text-sm font-semibold text-primary-700 hover:underline">Open source register</a>}>
    <div className="space-y-4">
      <Alert>Reference records from a published register. Check the current NDA register for registration status. Stock and prices are managed in Medicine Inventory.</Alert>
      {register.loading ? <Spinner label="Loading medicine register…" /> : register.error ? <Alert tone="danger">{register.error}</Alert> : <>
        <Input label="Find a registered product" type="search" placeholder="Product, ingredient, strength or registration number"
          value={query} onChange={(event) => setQuery(event.target.value)} />
        <p role="status" className="text-sm text-slate-600">{rows.length} of {register.data?.length || 0} reference records</p>
        <Table rows={rows} empty={search ? 'No products match your search' : 'No reference records have been imported'} columns={[
          { key: 'display', label: 'Product' },
          { key: 'id', label: 'Reference' },
          { key: 'code', label: 'NDA registration number' },
          { key: 'ingredient', label: 'Active ingredient', render: (row) => row.metadata?.ingredient },
          { key: 'strength', label: 'Strength', render: (row) => row.metadata?.strength },
          { key: 'dosage_form', label: 'Dosage form', render: (row) => row.metadata?.dosage_form },
          { key: 'pack_size', label: 'Pack size', render: (row) => row.metadata?.pack_size },
        ]} />
      </>}
    </div>
  </Card>
}
