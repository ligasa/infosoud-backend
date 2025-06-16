from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from urllib.parse import urlparse, parse_qs
import httpx, asyncio, json, os
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CASES_FILE = "cases.json"
CHECK_FILE = "last_check.json"

class URLInput(BaseModel):
    url: str

class SpisovkaDelete(BaseModel):
    spisovka: str

def load_cases():
    if not os.path.exists(CASES_FILE):
        return []
    with open(CASES_FILE, "r") as f:
        return json.load(f)

def save_cases(cases):
    with open(CASES_FILE, "w") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

def save_last_check_time():
    with open(CHECK_FILE, "w") as f:
        json.dump({"last_check": datetime.now().isoformat()}, f)

def load_last_check_time():
    if not os.path.exists(CHECK_FILE):
        return None
    with open(CHECK_FILE, "r") as f:
        return json.load(f).get("last_check")

async def get_html_length(url):
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        return len(resp.text)

@app.get("/api/list")
def list_spisovky():
    return load_cases()

@app.get("/api/last-check")
def last_check():
    return {"last_check": load_last_check_time()}

@app.post("/api/add")
async def add_spisovka(data: URLInput):
    parsed = urlparse(data.url)
    params = parse_qs(parsed.query)

    senat = params.get("cisloSenatu", [""])[0]
    druh_vec = params.get("druhVec", [""])[0]
    bc = params.get("bcVec", [""])[0]
    rocnik = params.get("rocnik", [""])[0]
    typ_soudu = params.get("typSoudu", [""])[0]

    if not all([senat, druh_vec, bc, rocnik, typ_soudu]):
        raise HTTPException(status_code=400, detail="URL není kompletní.")

    spisovka = f"{senat}_{druh_vec}_{bc}_{rocnik}"

    length = await get_html_length(data.url)
    cases = load_cases()

    for case in cases:
        if case["spisovka"] == spisovka:
            raise HTTPException(status_code=400, detail="Spisovka už je sledovaná.")

    new_case = {
        "spisovka": spisovka,
        "typSoudu": typ_soudu,
        "url": data.url,
        "length": length
    }
    cases.append(new_case)
    save_cases(cases)
    return new_case

@app.delete("/api/delete")
def delete_spisovka(data: SpisovkaDelete):
    cases = load_cases()
    updated = [c for c in cases if c["spisovka"] != data.spisovka]
    if len(updated) == len(cases):
        raise HTTPException(status_code=404, detail="Spisovka nebyla nalezena.")
    save_cases(updated)
    return {"message": "Smazáno"}

@app.get("/api/check-all")
async def check_all():
    cases = load_cases()
    updated_cases = []

    for case in cases:
        new_length = await get_html_length(case["url"])
        updated_cases.append({
            "spisovka": case["spisovka"],
            "old_length": case["length"],
            "new_length": new_length,
            "changed": new_length != case["length"]
        })
        case["length"] = new_length

    save_cases(cases)
    save_last_check_time()
    return updated_cases
