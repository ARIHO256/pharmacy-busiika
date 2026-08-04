#!/usr/bin/env python3
"""Small dependency-free concurrency smoke test for health/readiness endpoints."""
import argparse, concurrent.futures, statistics, time, urllib.request

def hit(url):
    started=time.perf_counter()
    with urllib.request.urlopen(url, timeout=10) as response:
        response.read()
        if response.status != 200: raise RuntimeError(response.status)
    return (time.perf_counter()-started)*1000

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base',default='http://127.0.0.1:4010');parser.add_argument('--requests',type=int,default=100);parser.add_argument('--concurrency',type=int,default=10);args=parser.parse_args()
    urls=[f"{args.base}/healthz" if index%2==0 else f"{args.base}/readyz" for index in range(args.requests)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool: durations=list(pool.map(hit,urls))
    ordered=sorted(durations);p95=ordered[max(0,int(len(ordered)*.95)-1)]
    print(f"HTTP load smoke: {len(durations)} requests passed; mean={statistics.mean(durations):.1f}ms p95={p95:.1f}ms max={max(durations):.1f}ms")
if __name__=='__main__':main()
