"""Business operations shared by the API, importer, seed script, and tests."""
from __future__ import annotations

import csv, io, json, re
from datetime import datetime, timezone
from urllib.parse import urlparse
from .database import db
from .scoring import calculate

def normalize_name(name: str) -> str:
    """Remove punctuation and common legal endings for duplicate matching."""
    cleaned = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    words = [w for w in cleaned.split() if w not in {"inc", "incorporated", "corp", "corporation", "company", "co", "ltd", "limited", "llc"}]
    return " ".join(words)

def normalize_domain(website: str | None) -> str | None:
    if not website: return None
    parsed = urlparse(website if "://" in website else "https://" + website)
    return (parsed.hostname or "").lower().removeprefix("www.") or None

def _number(value, integer=False):
    try: return int(float(value)) if integer else float(value)
    except (TypeError, ValueError): return 0

def upsert_company(payload: dict) -> tuple[int, bool]:
    """Create/update a company after resolving stable identifiers and aliases."""
    legal_name = str(payload.get("legal_name", "")).strip()
    country = str(payload.get("country", "US")).upper().strip()
    if not legal_name or country not in {"CA", "US"}: raise ValueError("legal_name and country CA/US are required")
    norm_name, domain = normalize_name(legal_name), normalize_domain(payload.get("website"))
    cik = str(payload.get("cik") or "").zfill(10) if payload.get("cik") else None
    with db() as con:
        existing = None
        if cik: existing = con.execute("SELECT id FROM companies WHERE cik=?", (cik,)).fetchone()
        if not existing and domain: existing = con.execute("SELECT id FROM companies WHERE normalized_domain=?", (domain,)).fetchone()
        if not existing: existing = con.execute("SELECT id FROM companies WHERE country=? AND normalized_name=?", (country,norm_name)).fetchone()
        fields = (legal_name,norm_name,country,payload.get("industry") or "Unknown",payload.get("website"),domain,
                  payload.get("phone"),payload.get("phone_type"),payload.get("phone_source"),payload.get("phone_verified_at"),
                  payload.get("contact_name"),payload.get("contact_role"),payload.get("email"),payload.get("ticker"),cik,
                  _number(payload.get("employee_count"),True) or None,_number(payload.get("revenue")) or None,payload.get("source_url"))
        if existing:
            company_id, created = existing["id"], False
            con.execute("""UPDATE companies SET legal_name=?,normalized_name=?,country=?,industry=?,website=COALESCE(?,website),normalized_domain=COALESCE(?,normalized_domain),phone=COALESCE(?,phone),phone_type=COALESCE(?,phone_type),phone_source=COALESCE(?,phone_source),phone_verified_at=COALESCE(?,phone_verified_at),contact_name=COALESCE(?,contact_name),contact_role=COALESCE(?,contact_role),email=COALESCE(?,email),ticker=COALESCE(?,ticker),cik=COALESCE(?,cik),employee_count=COALESCE(?,employee_count),revenue=COALESCE(?,revenue),source_url=COALESCE(?,source_url),updated_at=CURRENT_TIMESTAMP WHERE id=?""", fields+(company_id,))
        else:
            cur=con.execute("""INSERT INTO companies(legal_name,normalized_name,country,industry,website,normalized_domain,phone,phone_type,phone_source,phone_verified_at,contact_name,contact_role,email,ticker,cik,employee_count,revenue,source_url) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",fields)
            company_id, created = cur.lastrowid, True
        feature = {k: payload.get(k) for k in ("revenue_growth","margin_change","expense_growth","recent_acquisition","restructuring","management_change","efficiency_mentions","cost_mentions")}
        company = dict(con.execute("SELECT * FROM companies WHERE id=?",(company_id,)).fetchone())
        scores, signals = calculate(feature, company)
        con.execute("""INSERT INTO features(company_id,revenue_growth,margin_change,expense_growth,recent_acquisition,restructuring,management_change,efficiency_mentions,cost_mentions,financial_score,operational_score,transformation_score,nlp_score,fit_score,heuristic_score,final_score) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(company_id) DO UPDATE SET revenue_growth=excluded.revenue_growth,margin_change=excluded.margin_change,expense_growth=excluded.expense_growth,recent_acquisition=excluded.recent_acquisition,restructuring=excluded.restructuring,management_change=excluded.management_change,efficiency_mentions=excluded.efficiency_mentions,cost_mentions=excluded.cost_mentions,financial_score=excluded.financial_score,operational_score=excluded.operational_score,transformation_score=excluded.transformation_score,nlp_score=excluded.nlp_score,fit_score=excluded.fit_score,heuristic_score=excluded.heuristic_score,final_score=excluded.final_score,calculated_at=CURRENT_TIMESTAMP""",
                    (company_id,*[_number(feature.get(k), k in {"recent_acquisition","restructuring","management_change","efficiency_mentions","cost_mentions"}) for k in feature],*[scores[k] for k in ("financial_score","operational_score","transformation_score","nlp_score","fit_score","heuristic_score","final_score")]))
        con.execute("DELETE FROM signals WHERE company_id=?",(company_id,))
        con.executemany("INSERT INTO signals(company_id,category,label,points,evidence,source_url) VALUES(?,?,?,?,?,?)",[(company_id,s["category"],s["label"],s["points"],s["evidence"],payload.get("source_url")) for s in signals])
        con.execute("INSERT INTO audit_log(action,company_id,details) VALUES(?,?,?)",("COMPANY_CREATED" if created else "COMPANY_UPDATED",company_id,json.dumps({"name":legal_name})))
    return company_id, created

def list_companies(status="NEW", country=None, search=None, min_score=0):
    query="""SELECT c.*,f.final_score,f.heuristic_score,f.model_probability, CASE WHEN c.phone IS NOT NULL AND c.phone<>'' THEN 'HIGH' WHEN c.website IS NOT NULL THEN 'MEDIUM' ELSE 'LOW' END contactability FROM companies c JOIN features f ON f.company_id=c.id WHERE f.final_score>=?"""
    args=[min_score]
    if status and status != "ALL":
        if status == "HISTORY": query += " AND c.status NOT IN ('NEW','QUALIFIED','FOLLOW_UP')"
        else: query += " AND c.status=?"; args.append(status)
    if country: query += " AND c.country=?"; args.append(country)
    if search: query += " AND (c.legal_name LIKE ? OR c.industry LIKE ? OR c.ticker LIKE ?)"; args += [f"%{search}%"]*3
    query += " ORDER BY f.final_score DESC,c.legal_name"
    with db() as con: return [dict(r) for r in con.execute(query,args)]

def get_company(company_id:int):
    with db() as con:
        row=con.execute("SELECT c.*,f.* FROM companies c JOIN features f ON f.company_id=c.id WHERE c.id=?",(company_id,)).fetchone()
        if not row: return None
        result=dict(row); result["signals"]=[dict(r) for r in con.execute("SELECT * FROM signals WHERE company_id=? ORDER BY points DESC",(company_id,))]
        # ID breaks ties when two calls are saved within the same SQLite second.
        result["calls"]=[dict(r) for r in con.execute("SELECT * FROM calls WHERE company_id=? ORDER BY called_at DESC,id DESC",(company_id,))]
        return result

def _status_from_call(call) -> str:
    """Translate one active call into the company's visible workflow status."""
    if call["do_not_contact"]: return "DO_NOT_CONTACT"
    if call["follow_up_at"]: return "FOLLOW_UP"
    if call["opportunity"] == "YES": return "OPPORTUNITY"
    if call["opportunity"] == "NO": return "NO_OPPORTUNITY"
    return "CONTACTED"

def log_call(company_id:int,payload:dict):
    """Save outreach and move it out of NEW immediately, regardless of outcome."""
    opportunity=payload.get("opportunity","UNKNOWN")
    if opportunity not in {"YES","NO","UNSURE","UNKNOWN"}: raise ValueError("Invalid opportunity result")
    reached=payload.get("reached","NO_ANSWER")
    if payload.get("do_not_contact"): status="DO_NOT_CONTACT"
    elif payload.get("follow_up_at"): status="FOLLOW_UP"
    elif opportunity=="YES": status="OPPORTUNITY"
    elif opportunity=="NO": status="NO_OPPORTUNITY"
    else: status="CONTACTED"
    with db() as con:
        company=con.execute("SELECT * FROM companies WHERE id=?",(company_id,)).fetchone()
        if not company: raise ValueError("Company not found")
        con.execute("""INSERT INTO calls(company_id,reached,opportunity,opportunity_type,strength,meeting,follow_up_at,notes,phone_used,do_not_contact) VALUES(?,?,?,?,?,?,?,?,?,?)""",(company_id,reached,opportunity,payload.get("opportunity_type"),payload.get("strength"),1 if payload.get("meeting") else 0,payload.get("follow_up_at"),payload.get("notes"),company["phone"],1 if payload.get("do_not_contact") else 0))
        con.execute("UPDATE companies SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(status,company_id))
        if reached=="WRONG_NUMBER": con.execute("UPDATE companies SET phone_type='Invalid — replacement needed' WHERE id=?",(company_id,))
        con.execute("INSERT INTO audit_log(action,company_id,details) VALUES('CALL_LOGGED',?,?)",(company_id,json.dumps({"status":status,"opportunity":opportunity})))
    return status

def cancel_call(call_id:int, reason:str|None=None):
    """Void a mistaken call and restore the status implied by prior active calls.

    The row is retained for auditability, but it stops counting as call history
    or ML training data. With no earlier active calls, the company returns to NEW.
    """
    with db() as con:
        call=con.execute("SELECT * FROM calls WHERE id=?",(call_id,)).fetchone()
        if not call: raise ValueError("Call not found")
        if call["voided_at"]: raise ValueError("Call is already cancelled")
        company_id=call["company_id"]
        con.execute("UPDATE calls SET voided_at=CURRENT_TIMESTAMP,void_reason=? WHERE id=?",(reason or "Cancelled by user",call_id))
        previous=con.execute("SELECT * FROM calls WHERE company_id=? AND voided_at IS NULL ORDER BY called_at DESC,id DESC LIMIT 1",(company_id,)).fetchone()
        status=_status_from_call(previous) if previous else "NEW"
        con.execute("UPDATE companies SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(status,company_id))
        con.execute("INSERT INTO audit_log(action,company_id,details) VALUES('CALL_CANCELLED',?,?)",(company_id,json.dumps({"call_id":call_id,"restored_status":status,"reason":reason or "Cancelled by user"})))
    return {"company_id":company_id,"status":status}

def import_csv(content:bytes):
    reader=csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    created=updated=failed=0; errors=[]
    for index,row in enumerate(reader,start=2):
        try:
            _,was_created=upsert_company(row); created+=int(was_created); updated+=int(not was_created)
        except Exception as exc: failed+=1; errors.append(f"Row {index}: {exc}")
    return {"created":created,"updated":updated,"failed":failed,"errors":errors[:20]}

def dashboard_stats():
    with db() as con:
        totals=dict(con.execute("SELECT COUNT(*) companies,SUM(status='NEW') new_leads,SUM(status='FOLLOW_UP') follow_ups,SUM(status='OPPORTUNITY') opportunities,SUM(phone IS NOT NULL AND phone<>'') with_phone FROM companies").fetchone())
        labels=dict(con.execute("SELECT COUNT(*) labels,SUM(opportunity='YES') positives FROM calls WHERE opportunity IN ('YES','NO') AND voided_at IS NULL").fetchone())
        return {**totals,**labels}
