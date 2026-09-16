"""Free SEC data collector with conservative request pacing and identification."""
from __future__ import annotations
import asyncio
from datetime import date
import httpx
from .services import upsert_company

BASE="https://data.sec.gov"

def _latest_usd(facts:dict, names:list[str]):
    for name in names:
        units=facts.get("us-gaap",{}).get(name,{}).get("units",{}).get("USD",[])
        annual=[x for x in units if x.get("form") in {"10-K","10-Q"} and x.get("val") is not None]
        if annual:
            annual.sort(key=lambda x:x.get("end",""),reverse=True); return float(annual[0]["val"])
    return None

async def import_ciks(ciks:list[str],identity:str):
    """Retrieve public submissions/company facts for specific CIK identifiers."""
    if "@" not in identity: raise ValueError("Use an identifying email in the SEC User-Agent")
    headers={"User-Agent":f"Mensana Opportunity Radar {identity}","Accept-Encoding":"gzip, deflate"}
    results=[]
    async with httpx.AsyncClient(headers=headers,timeout=30,follow_redirects=True) as client:
        for raw in ciks[:50]:
            cik="".join(filter(str.isdigit,raw)).zfill(10)
            try:
                sub=(await client.get(f"{BASE}/submissions/CIK{cik}.json")); sub.raise_for_status()
                facts=(await client.get(f"{BASE}/api/xbrl/companyfacts/CIK{cik}.json")); facts.raise_for_status()
                s,f=sub.json(),facts.json(); us=f.get("facts",{})
                revenue=_latest_usd(us,["RevenueFromContractWithCustomerExcludingAssessedTax","Revenues","SalesRevenueNet"])
                phone=s.get("phone") or None
                payload={"legal_name":s.get("name") or f.get("entityName"),"country":"US","industry":s.get("sicDescription") or "Unknown","website":s.get("website") or None,"phone":phone,"phone_type":"Main office" if phone else None,"phone_source":"SEC submissions profile" if phone else None,"phone_verified_at":str(date.today()) if phone else None,"ticker":(s.get("tickers") or [None])[0],"cik":cik,"revenue":revenue,"source_url":f"https://www.sec.gov/edgar/browse/?CIK={cik}"}
                company_id,created=upsert_company(payload); results.append({"cik":cik,"company_id":company_id,"created":created,"name":payload["legal_name"]})
            except Exception as exc: results.append({"cik":cik,"error":str(exc)[:200]})
            await asyncio.sleep(.15) # Well below the SEC's published request ceiling.
    return results
