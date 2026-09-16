"""FastAPI routes and static web application entry point."""
from __future__ import annotations
import csv,io
from pathlib import Path
from fastapi import FastAPI,File,HTTPException,Query,UploadFile
from fastapi.responses import FileResponse,StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .database import init_db,db
from .seed import seed
from .services import dashboard_stats,get_company,import_csv,list_companies,log_call,upsert_company
from .ml import status as model_status,train
from .sec_importer import import_ciks

app=FastAPI(title="Mensana Opportunity Radar",version="0.1.0")
STATIC=Path(__file__).parent/"static"
app.mount("/static",StaticFiles(directory=STATIC),name="static")

@app.on_event("startup")
def startup(): init_db(); seed()

class CallInput(BaseModel):
    reached:str="NO_ANSWER"; opportunity:str="UNKNOWN"; opportunity_type:str|None=None
    strength:str|None=None; meeting:bool=False; follow_up_at:str|None=None
    notes:str|None=Field(None,max_length=5000); do_not_contact:bool=False

class SecInput(BaseModel):
    ciks:list[str]; identity:str

@app.get("/")
def index(): return FileResponse(STATIC/"index.html")
@app.get("/api/health")
def health(): return {"status":"ok","version":"0.1.0"}
@app.get("/api/stats")
def stats(): return dashboard_stats()
@app.get("/api/companies")
def companies(status:str="NEW",country:str|None=None,search:str|None=None,min_score:float=Query(0,ge=0,le=100)):
    return list_companies(status,country,search,min_score)
@app.get("/api/companies/{company_id}")
def company(company_id:int):
    result=get_company(company_id)
    if not result: raise HTTPException(404,"Company not found")
    return result
@app.post("/api/companies")
def create_company(payload:dict):
    try: company_id,created=upsert_company(payload); return {"id":company_id,"created":created}
    except ValueError as exc: raise HTTPException(400,str(exc))
@app.post("/api/companies/{company_id}/calls")
def call(company_id:int,payload:CallInput):
    try: return {"status":log_call(company_id,payload.model_dump())}
    except ValueError as exc: raise HTTPException(400,str(exc))
@app.post("/api/import/csv")
async def upload_csv(file:UploadFile=File(...)):
    if not file.filename.lower().endswith(".csv"): raise HTTPException(400,"Choose a CSV file")
    return import_csv(await file.read())
@app.post("/api/import/sec")
async def sec(payload:SecInput):
    try: return await import_ciks(payload.ciks,payload.identity)
    except ValueError as exc: raise HTTPException(400,str(exc))
@app.get("/api/model")
def model(): return model_status()
@app.post("/api/model/train")
def retrain(): return train()
@app.get("/api/export.csv")
def export():
    with db() as con: rows=[dict(r) for r in con.execute("SELECT c.*,f.final_score,f.model_probability FROM companies c JOIN features f ON f.company_id=c.id")]
    output=io.StringIO(); writer=csv.DictWriter(output,fieldnames=rows[0].keys() if rows else ["id"]); writer.writeheader(); writer.writerows(rows)
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=mensana-companies.csv"})
