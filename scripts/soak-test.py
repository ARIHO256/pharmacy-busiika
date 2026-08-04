#!/usr/bin/env python3
"""Long-running authenticated multi-role API soak with safe persisted writes."""
from __future__ import annotations
import argparse, concurrent.futures, json, random, statistics, sys, time, urllib.request

PASSWORD="DemoPass!2026"
ACCOUNTS=[
("patient1@mydoctor.test","patient"),("dr.nakato@mydoctor.test","doctor"),("clinical.officer@mydoctor.test","clinical_officer"),
("dentist@mydoctor.test","dentist"),("physio@mydoctor.test","physiotherapist"),("nutrition@mydoctor.test","nutritionist"),
("psychology@mydoctor.test","psychologist"),("medical.director@mydoctor.test","medical_director"),("nurse@mydoctor.test","nurse"),
("midwife@mydoctor.test","midwife"),("theatre.nurse@mydoctor.test","theatre_nurse"),("reception@mydoctor.test","receptionist"),
("records@mydoctor.test","records_officer"),("cashier@mydoctor.test","cashier"),("accountant@mydoctor.test","accountant"),
("finance.manager@mydoctor.test","finance_manager"),("pharmacist.staff@mydoctor.test","pharmacist"),("storekeeper@mydoctor.test","storekeeper"),
("labtech@mydoctor.test","lab_technician"),("radiologist@mydoctor.test","radiologist"),("radiographer@mydoctor.test","radiographer"),
("anaesthetist@mydoctor.test","anaesthetist"),("manager@mydoctor.test","facility_manager"),("procurement@mydoctor.test","procurement_officer"),
("quality@mydoctor.test","quality_officer"),("compliance@mydoctor.test","compliance_officer"),("hr@mydoctor.test","hr_officer"),
("it@mydoctor.test","it_support"),("dispatcher@mydoctor.test","ambulance_dispatcher"),("paramedic@mydoctor.test","paramedic"),
("insurance.officer@mydoctor.test","insurance_officer"),("claims@mydoctor.test","claims_reviewer"),("hospital@mydoctor.test","hospital"),
("pharmacy@mydoctor.test","pharmacy"),("lab@mydoctor.test","lab"),("insurance@mydoctor.test","insurance"),
]
READS=["/journeys/dashboard/","/auth/me/","/appointments/","/communication/notifications/","/journeys/operational-actions/"]

def call(url,method="GET",payload=None,token=None,timeout=30):
    started=time.perf_counter();headers={"Content-Type":"application/json"}
    if token:headers["Authorization"]=f"Bearer {token}"
    req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,method=method,headers=headers)
    with urllib.request.urlopen(req,timeout=timeout) as response:
        body=response.read();status=response.status
    return status,(time.perf_counter()-started)*1000,body

def login(base,email):
    status,_,body=call(base+"/auth/token/","POST",{"email":email,"password":PASSWORD})
    data=json.loads(body or b"{}")
    if data.get("mfa_required"):raise RuntimeError(f"MFA required for {email}; use a non-MFA soak context")
    if status!=200 or not data.get("access"):raise RuntimeError(f"login failed for {email}")
    return data["access"]

def safe_write(base, token, sequence):
    payload={"data":{"category":"technology","severity":"low","subject":f"Soak heartbeat {sequence}","details":"Automated low-risk persistence check during production acceptance soak.","anonymous_to_facility":False}}
    return call(base+"/journeys/pages/feedback-complaint/cases/","POST",payload,token)

def main():
    p=argparse.ArgumentParser();p.add_argument("--base",default="http://127.0.0.1:4000/api");p.add_argument("--hours",type=float,default=4);p.add_argument("--concurrency",type=int,default=12);p.add_argument("--interval",type=float,default=.25);p.add_argument("--max-error-rate",type=float,default=.005);p.add_argument("--write-every",type=int,default=500);args=p.parse_args()
    tokens=[(login(args.base,email),role) for email,role in ACCOUNTS]
    patient_token=next(token for token,role in tokens if role=="patient")
    deadline=time.monotonic()+args.hours*3600;latencies=[];errors=[];count=0;writes=0;batches=0
    def hit(item):
        token,role=item;path=random.choice(READS)
        try:
            status,ms,_=call(args.base+path,token=token)
            if status>=400:raise RuntimeError(status)
            return ms,None
        except Exception as exc:return None,f"{role} {path}: {exc}"
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        while time.monotonic()<deadline:
            batches+=1
            batch=[random.choice(tokens) for _ in range(args.concurrency)]
            for ms,error in pool.map(hit,batch):
                count+=1
                if error:errors.append(error)
                else:latencies.append(ms)
            if args.write_every > 0 and batches % args.write_every == 0:
                try:
                    status,ms,body=safe_write(args.base,patient_token,writes+1)
                    count+=1;writes+=1;latencies.append(ms)
                    if status!=201: errors.append(f"safe-write returned {status}: {body[:200]!r}")
                except Exception as exc: count+=1;errors.append(f"safe-write: {exc}")
            time.sleep(args.interval)
    error_rate=len(errors)/max(count,1);p95=sorted(latencies)[max(0,int(len(latencies)*.95)-1)] if latencies else 0
    print(json.dumps({"roles":len(tokens),"requests":count,"persisted_safe_writes":writes,"errors":len(errors),"error_rate":error_rate,"mean_ms":statistics.mean(latencies) if latencies else 0,"p95_ms":p95,"max_ms":max(latencies) if latencies else 0,"sample_errors":errors[:20]},indent=2))
    return 1 if error_rate>args.max_error_rate else 0
if __name__=="__main__":sys.exit(main())
