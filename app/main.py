
from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import hashlib
import json
import re
import os

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="String Analyzer Service",
    
    
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./strings.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class StringEntry(Base):
    __tablename__ = "strings"
    id = Column(String, primary_key=True, index=True)  # sha256
    value = Column(Text, nullable=False, unique=True)
    properties_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



def compute_properties(value: str) -> Dict[str, Any]:
    
    v = value
    length = len(v)
    

    is_palindrome = v.lower() == v.lower()[::-1]
    
    unique_characters = len(set(v))
    

    word_count = 0 if v.strip() == "" else len(v.split())
    
    sha = hashlib.sha256(v.encode("utf-8")).hexdigest()
    
    
    freq = {}
    for ch in v:
        freq[ch] = freq.get(ch, 0) + 1
    
    return {
        "length": length,
        "is_palindrome": is_palindrome,
        "unique_characters": unique_characters,
        "word_count": word_count,
        "sha256_hash": sha,
        "character_frequency_map": freq,
    }

def parse_nl_query(q: str) -> Dict[str, Any]:
    
    q_lower = q.lower()
    parsed: Dict[str, Any] = {}
    
  
    if re.search(r"(single|one) word", q_lower):
        parsed["word_count"] = 1
    
   
    m = re.search(r"longer than (\d+)", q_lower)
    if m:
        parsed["min_length"] = int(m.group(1)) + 1 
    
   
    if "palindrom" in q_lower:
        parsed["is_palindrome"] = True
    
    
    m = re.search(r"contain(?:ing|s)? (?:the )?letter ([a-z])", q_lower)
    if m:
        parsed["contains_character"] = m.group(1)
    
   
    if re.search(r"first vowel", q_lower):
        parsed["contains_character"] = "a"
    
    
    if "min_length" in parsed and "max_length" in parsed:
        if parsed["min_length"] > parsed["max_length"]:
            raise ValueError("Query parsed but resulted in conflicting filters")
    
    if not parsed:
        raise ValueError("Unable to parse natural language query")
    
    return parsed


class CreateRequest(BaseModel):
    value: str = Field(..., description="String to analyze")

class PropertiesModel(BaseModel):
    length: int
    is_palindrome: bool
    unique_characters: int
    word_count: int
    sha256_hash: str
    character_frequency_map: Dict[str, int]

class StringResponse(BaseModel):
    id: str
    value: str
    properties: PropertiesModel
    created_at: str




def row_to_response(row: StringEntry) -> Dict[str, Any]:
    
    props = json.loads(row.properties_json)
    return {
        "id": row.id,
        "value": row.value,
        "properties": props,
        "created_at": row.created_at.replace(tzinfo=timezone.utc).isoformat(),
    }


@app.post("/strings", status_code=201)
def create_string(req: CreateRequest, db: Session = Depends(get_db)):
    
   
    if not isinstance(req.value, str):
        raise HTTPException(status_code=422, detail="Field 'value' must be a string")
 
    props = compute_properties(req.value)
    sha = props["sha256_hash"]
    
   
    existing = db.query(StringEntry).filter(StringEntry.id == sha).first()
    if existing:
        raise HTTPException(status_code=409, detail="String already exists in the system")
    
    
    now = datetime.now(timezone.utc)
    row = StringEntry(
        id=sha,
        value=req.value,
        properties_json=json.dumps(props),
        created_at=now
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    
    return row_to_response(row)


@app.get("/strings/{string_value}")
def get_string(string_value: str, db: Session = Depends(get_db)):
    
    row = db.query(StringEntry).filter(StringEntry.value == string_value).first()
    
   
    if not row:
        row = db.query(StringEntry).filter(StringEntry.id == string_value).first()
    
    if not row:
        raise HTTPException(status_code=404, detail="String does not exist in the system")
    
    return row_to_response(row)


@app.get("/strings")
def list_strings(
    is_palindrome: Optional[bool] = Query(None, description="Filter by palindrome status"),
    min_length: Optional[int] = Query(None, ge=0, description="Minimum string length"),
    max_length: Optional[int] = Query(None, ge=0, description="Maximum string length"),
    word_count: Optional[int] = Query(None, ge=0, description="Exact word count"),
    contains_character: Optional[str] = Query(None, min_length=1, max_length=1, description="Character that must be present"),
    db: Session = Depends(get_db)
):
    
    if min_length is not None and max_length is not None:
        if min_length > max_length:
            raise HTTPException(status_code=400, detail="min_length cannot be greater than max_length")
    
   
    rows = db.query(StringEntry).all()
    results = []
    
    for r in rows:
        props = json.loads(r.properties_json)
        ok = True
        
       
        if is_palindrome is not None and props.get("is_palindrome") != is_palindrome:
            ok = False
        if min_length is not None and props.get("length") < min_length:
            ok = False
        if max_length is not None and props.get("length") > max_length:
            ok = False
        if word_count is not None and props.get("word_count") != word_count:
            ok = False
        if contains_character is not None:
            char_freq = props.get("character_frequency_map", {})
            if char_freq.get(contains_character, 0) == 0:
                ok = False
        
        if ok:
            results.append(row_to_response(r))
    
    
    filters_applied = {}
    if is_palindrome is not None:
        filters_applied["is_palindrome"] = is_palindrome
    if min_length is not None:
        filters_applied["min_length"] = min_length
    if max_length is not None:
        filters_applied["max_length"] = max_length
    if word_count is not None:
        filters_applied["word_count"] = word_count
    if contains_character is not None:
        filters_applied["contains_character"] = contains_character
    
    return {
        "data": results,
        "count": len(results),
        "filters_applied": filters_applied
    }

@app.get("/strings/filter-by-natural-language")
def nl_filter(
    query: str = Query(..., description="Natural language query"),
    db: Session = Depends(get_db)
):
    
    try:
        parsed = parse_nl_query(query)
    except ValueError as e:
        
        if "conflicting" in str(e).lower():
            raise HTTPException(status_code=422, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    
  
    result = list_strings(
        is_palindrome=parsed.get("is_palindrome"),
        min_length=parsed.get("min_length"),
        max_length=parsed.get("max_length"),
        word_count=parsed.get("word_count"),
        contains_character=parsed.get("contains_character"),
        db=db
    )
    
    
    result["interpreted_query"] = {
        "original": query,
        "parsed_filters": parsed
    }
    
    return result


@app.delete("/strings/{string_value}", status_code=204)
def delete_string(string_value: str, db: Session = Depends(get_db)):
    
    row = db.query(StringEntry).filter(StringEntry.value == string_value).first()
    
    
    if not row:
        row = db.query(StringEntry).filter(StringEntry.id == string_value).first()
    
    if not row:
        raise HTTPException(status_code=404, detail="String does not exist in the system")
    
    db.delete(row)
    db.commit()
    
    return None 


@app.get("/")
def root():
    
    return {
        
        "status": "ok",   
    }