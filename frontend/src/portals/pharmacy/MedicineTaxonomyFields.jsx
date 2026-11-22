import { Alert, Input, Select } from '../../components/ui'

export default function MedicineTaxonomyFields({ catalog, selection, setSelection }) {
  if (catalog.error) return <Alert tone="warning">Medicine categories could not be loaded. You can save other medicine details.</Alert>
  if (catalog.loading) return <p role="status" className="text-sm text-slate-600">Loading medicine categories…</p>

  const nodes = catalog.data || []
  const subcategory = nodes.find((node) => node.node_id === selection.taxonomy_node)
  const categoryId = selection.category || subcategory?.parent || ''
  const category = nodes.find((node) => node.node_id === categoryId)
  const familyId = selection.family || category?.parent || ''
  const available = (node, current) => !node.archived || node.node_id === current
  const option = (node) => <option key={node.node_id} value={node.node_id}>{node.name}{node.archived ? ' (archived)' : ''}</option>

  return <fieldset className="space-y-3 rounded-xl border border-slate-200 p-3">
    <legend className="px-1 text-sm font-semibold text-slate-800">Catalogue classification</legend>
    <Select label="Product family" value={familyId} onChange={(event) => {
      setSelection({ family: event.target.value, category: '', taxonomy_node: '', product_attributes: {} })
    }}>
      <option value="">Select a family</option>
      {nodes.filter((node) => node.level === 2 && available(node, familyId)).map(option)}
    </Select>
    <Select label="Category" disabled={!familyId} required={Boolean(familyId)} value={categoryId} onChange={(event) => {
      setSelection({ family: familyId, category: event.target.value, taxonomy_node: '', product_attributes: {} })
    }}>
      <option value="">Select a category</option>
      {nodes.filter((node) => node.level === 3 && node.parent === familyId && available(node, categoryId)).map(option)}
    </Select>
    <Select label="Subcategory" disabled={!categoryId} required={Boolean(categoryId)} value={selection.taxonomy_node} onChange={(event) => {
      setSelection({ family: familyId, category: categoryId, taxonomy_node: event.target.value, product_attributes: {} })
    }}>
      <option value="">Select a subcategory</option>
      {nodes.filter((node) => node.level === 4 && node.parent === categoryId && available(node, selection.taxonomy_node)).map(option)}
    </Select>
    {Boolean(subcategory?.attribute_fields?.length) && <div className="grid gap-3 border-t border-slate-200 pt-3 sm:grid-cols-2">
      {subcategory.attribute_fields.map((field) => <Input key={field.key} label={field.label}
        type={field.type === 'integer' ? 'number' : 'text'}
        min={field.min} max={field.type === 'integer' ? 1000000 : undefined}
        maxLength={field.type === 'text' ? 250 : undefined}
        value={Object.hasOwn(selection.product_attributes, field.key) ? selection.product_attributes[field.key] : ''}
        onChange={(event) => setSelection({
          product_attributes: { ...selection.product_attributes, [field.key]: event.target.value },
        })} />)}
    </div>}
    {subcategory && <p className="text-sm text-slate-600">Changing the subcategory clears these product details.</p>}
    {!familyId && <p className="text-sm text-slate-600">Leave blank if the catalogue has no suitable category.</p>}
  </fieldset>
}
