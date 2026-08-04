import { workforceApi } from '../../api/endpoints'
import { Alert, Card, Spinner, Stat, Table } from '../../components/ui'
import { statusBadge, useRemote } from '../staff/shared'

export default function Dashboard(){
 const summary=useRemote(()=>workforceApi.summary(),[]); const visits=useRemote(()=>workforceApi.visits(),[])
 if(summary.loading||visits.loading)return <Spinner/>; if(summary.error||visits.error)return <Alert tone="danger">{summary.error||visits.error}</Alert>; const s=summary.data||{}
 return <div className="space-y-5"><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Stat label="Today's visits" value={s.today_visits||0} icon="calendar"/><Stat label="Active staff" value={s.active_staff||0} icon="users"/><Stat label="Waiting clinician" value={s.waiting_clinician||0} icon="doctor"/><Stat label="Completed today" value={s.completed||0} icon="check"/></div><div className="grid gap-5 xl:grid-cols-2"><Card title="Staff by role"><Table rows={(s.staff_by_role||[]).map((r,i)=>({id:i,...r}))} empty="No staff memberships" columns={[{key:'role',label:'Role',render:r=>r.role.replaceAll('_',' ')},{key:'count',label:'Active staff'}]}/></Card><Card title="Current care flow"><Table rows={(visits.data||[]).filter(v=>!['completed','cancelled'].includes(v.status)).slice(0,8)} empty="No active visits" columns={[{key:'queue_number',label:'Queue',render:v=><strong>#{v.queue_number||'—'}</strong>},{key:'patient_name',label:'Patient'},{key:'status',label:'Stage',render:v=>statusBadge(v.status)}]}/></Card></div></div>
}
