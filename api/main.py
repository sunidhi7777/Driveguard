"""DriveGuard reliability and warranty risk API."""
from datetime import date
from pathlib import Path
import csv
import io
import random
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="DriveGuard API", version="1.0.0", description="Explainable drive reliability and warranty risk analytics")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATA = Path(__file__).resolve().parent.parent / "data" / "drives.csv"

def load_drives():
    with DATA.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key in ("power_on_hours", "temperature_c", "reallocated_sectors", "pending_sectors", "read_error_rate", "capacity_tb"):
            row[key] = float(row[key])
        row["failure"] = row["failure"].lower() == "true"
        row["purchase_date"] = date.fromisoformat(row["purchase_date"])
    return rows

def score(d):
    # Transparent heuristic, deliberately presented as a screening score rather than calibrated probability.
    risk = 4 + min(d["power_on_hours"] / 1200, 24) + max(d["temperature_c"] - 30, 0) * 1.15
    risk += min(d["reallocated_sectors"] * 5, 26) + min(d["pending_sectors"] * 9, 24)
    risk += min(d["read_error_rate"] / 800, 12)
    if d["failure"]: risk = max(risk, 96)
    return round(min(risk, 99), 1)

def enriched():
    rows = load_drives()
    for d in rows:
        d["risk_score"] = score(d)
        age = max((date.today() - d["purchase_date"]).days, 0)
        d["age_months"] = round(age / 30.44, 1)
        d["warranty_months_left"] = max(d["warranty_months"] - d["age_months"], 0)
        d["status"] = "Failed" if d["failure"] else ("Critical" if d["risk_score"] >= 65 else "Watch" if d["risk_score"] >= 35 else "Healthy")
        reasons=[]
        if d["pending_sectors"]: reasons.append(f"{int(d['pending_sectors'])} pending sectors")
        if d["reallocated_sectors"] >= 3: reasons.append(f"{int(d['reallocated_sectors'])} reallocated sectors")
        if d["temperature_c"] >= 45: reasons.append(f"high temperature ({int(d['temperature_c'])}°C)")
        if d["power_on_hours"] >= 30000: reasons.append("high power-on hours")
        if d["failure"]: reasons.insert(0,"recorded failure")
        d["risk_reasons"] = reasons or ["no elevated SMART indicators"]
        d["purchase_date"] = d["purchase_date"].isoformat()
    return rows

@app.get("/api/health")
def health(): return {"status":"ok","service":"driveguard-api"}

@app.get("/api/drives")
def drives(search: Optional[str] = None, status: Optional[str] = None):
    rows = enriched()
    if search: rows = [d for d in rows if search.lower() in d["serial"].lower() or search.lower() in d["model"].lower()]
    if status and status.lower() != "all": rows = [d for d in rows if d["status"].lower() == status.lower()]
    return sorted(rows, key=lambda d:d["risk_score"], reverse=True)

@app.get("/api/summary")
def summary():
    rows=enriched(); risky=[d for d in rows if d["risk_score"]>=65 and not d["failure"]]
    return {"fleet_size":len(rows),"at_risk":len(risky),"failed":sum(d["failure"] for d in rows),"avg_risk":round(sum(d["risk_score"] for d in rows)/len(rows),1),"warranty_exposure":round(sum(d["replacement_cost"] for d in risky),2),"failure_rate":round(sum(d["failure"] for d in rows)/len(rows)*100,1),"risk_distribution":[{"name":n,"value":sum(1 for d in rows if d["status"]==n)} for n in ("Healthy","Watch","Critical","Failed")]}

@app.get("/api/trends")
def trends():
    rows=enriched(); result=[]
    for hours in range(0,50001,5000):
        subset=[d for d in rows if d["power_on_hours"] >= hours]
        failures=sum(d["failure"] for d in subset)
        result.append({"hours":hours,"drives":len(subset),"failure_rate":round(failures/len(subset)*100,1) if subset else 0,"mean_risk":round(sum(d["risk_score"] for d in subset)/len(subset),1) if subset else 0})
    return result

@app.get("/api/audit")
def audit():
    rows=enriched(); flagged=sorted((d for d in rows if d["risk_score"]>=65 and not d["failure"]),key=lambda d:d["risk_score"],reverse=True)
    return {"generated_on":date.today().isoformat(),"method":"Explainable SMART screening heuristic (not a calibrated failure probability)","fleet_size":len(rows),"flagged_count":len(flagged),"estimated_exposure":round(sum(d["replacement_cost"] for d in flagged),2),"recommendations":[{"priority":"Immediate","action":"Back up data and replace drives with pending sectors or critical risk scores.","count":sum(d["pending_sectors"]>0 for d in flagged)},{"priority":"30 days","action":"Review warranty eligibility and schedule proactive replacements.","count":len(flagged)},{"priority":"Ongoing","action":"Capture SMART telemetry at least daily and investigate temperature excursions.","count":len(rows)}],"flagged_drives":[{"serial":d["serial"],"model":d["model"],"risk_score":d["risk_score"],"warranty_months_left":d["warranty_months_left"],"reasons":d["risk_reasons"],"replacement_cost":d["replacement_cost"]} for d in flagged]}

class DriveIn(BaseModel):
    serial: str = Field(min_length=1, max_length=64)
    model: str
    capacity_tb: float = Field(gt=0)
    purchase_date: date
    warranty_months: int = Field(ge=0, le=120)
    power_on_hours: float = Field(ge=0)
    temperature_c: float
    reallocated_sectors: float = Field(ge=0)
    pending_sectors: float = Field(ge=0)
    read_error_rate: float = Field(ge=0)
    replacement_cost: float = Field(ge=0)

@app.post("/api/drives/score")
def score_drive(d: DriveIn):
    row=d.model_dump(); row["failure"]=False
    risk=score(row)
    return {"serial":row["serial"],"risk_score":risk,"status":"Critical" if risk>=65 else "Watch" if risk>=35 else "Healthy","explanation":[f"SMART risk screening score: {risk}/100","Elevated score indicates the need for inspection, not a failure probability."]}

@app.post("/api/drives/import")
async def import_csv(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400,"Upload a .csv file")
    try:
        content=(await file.read()).decode("utf-8-sig")
        reader=csv.DictReader(io.StringIO(content))
        needed={"serial","model","capacity_tb","purchase_date","warranty_months","power_on_hours","temperature_c","reallocated_sectors","pending_sectors","read_error_rate","replacement_cost"}
        if not needed.issubset(set(reader.fieldnames or [])): raise ValueError("Missing required columns")
        imported=[]
        for raw in reader:
            d={k:raw[k] for k in needed}; d["failure"]=raw.get("failure","false").lower()=="true"
            for k in ("capacity_tb","warranty_months","power_on_hours","temperature_c","reallocated_sectors","pending_sectors","read_error_rate","replacement_cost"): d[k]=float(d[k])
            d["purchase_date"]=date.fromisoformat(d["purchase_date"]); d["risk_score"]=score(d); imported.append(d)
        return {"rows_imported":len(imported),"preview":imported[:5],"note":"Preview only. The starter app does not persist uploaded records."}
    except Exception as e: raise HTTPException(400,f"Invalid CSV: {e}")
