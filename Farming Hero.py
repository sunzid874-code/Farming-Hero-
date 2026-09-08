from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

# Database Setup
DATABASE_URL = "sqlite:///./farming_hero.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ------------------- SQLAlchemy ORM Models -------------------

class FieldModel(Base):
    __tablename__ = "fields"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    location = Column(String)
    area_acres = Column(Float)
    soil_type = Column(String)

    crops = relationship("CropModel", back_populates="field", cascade="all, delete")
    irrigations = relationship("IrrigationModel", back_populates="field", cascade="all, delete")
    fertilizers = relationship("FertilizerModel", back_populates="field", cascade="all, delete")
    expenses = relationship("ExpenseModel", back_populates="field", cascade="all, delete")

class CropModel(Base):
    __tablename__ = "crops"

    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(Integer, ForeignKey("fields.id"))
    crop_name = Column(String)
    planting_date = Column(Date)
    expected_harvest_date = Column(Date)
    growth_stage = Column(String)  # e.g., Seedling, Vegetative, Harvest-Ready, Harvested
    status = Column(String, default="Active")

    field = relationship("FieldModel", back_populates="crops")

class IrrigationModel(Base):
    __tablename__ = "irrigations"

    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(Integer, ForeignKey("fields.id"))
    water_amount_liters = Column(Float)
    date = Column(Date)
    status = Column(String)  # Completed, Scheduled

    field = relationship("FieldModel", back_populates="irrigations")

class FertilizerModel(Base):
    __tablename__ = "fertilizers"

    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(Integer, ForeignKey("fields.id"))
    name = Column(String)
    quantity_kg = Column(Float)
    date = Column(Date)

    field = relationship("FieldModel", back_populates="fertilizers")

class ExpenseModel(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(Integer, ForeignKey("fields.id"), nullable=True)  # Can be general or field specific
    category = Column(String)  # Seed, Water, Fertilizer, Equipment, Worker, etc.
    amount = Column(Float)
    expense_date = Column(Date)
    description = Column(String)

    field = relationship("FieldModel", back_populates="expenses")

class EquipmentModel(Base):
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    status = Column(String)  # Operational, Under Maintenance, In Use
    assigned_field_id = Column(Integer, nullable=True)

Base.metadata.create_all(bind=engine)

# ------------------- Pydantic Schemas -------------------

class FieldBase(BaseModel):
    name: str
    location: str
    area_acres: float
    soil_type: str

class FieldCreate(FieldBase):
    pass

class FieldResponse(FieldBase):
    id: int
    class Config:
        from_attributes = True

class CropCreate(BaseModel):
    field_id: int
    crop_name: str
    planting_date: date
    expected_harvest_date: date
    growth_stage: str

class CropResponse(CropCreate):
    id: int
    status: str
    class Config:
        from_attributes = True

class IrrigationCreate(BaseModel):
    field_id: int
    water_amount_liters: float
    date: date
    status: str

class FertilizerCreate(BaseModel):
    field_id: int
    name: str
    quantity_kg: float
    date: date

class ExpenseCreate(BaseModel):
    field_id: Optional[int] = None
    category: str
    amount: float
    expense_date: date
    description: str

class ExpenseResponse(ExpenseCreate):
    id: int
    class Config:
        from_attributes = True

class TotalExpenseSummary(BaseModel):
    total_expenses: float
    expenses_by_field: dict

class EquipmentCreate(BaseModel):
    name: str
    status: str
    assigned_field_id: Optional[int] = None

# ------------------- FastAPI App & Endpoints -------------------

app = FastAPI(title="Farming Hero API", version="1.0.0")

# Enable CORS for Frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def root():
    return {"message": "Welcome to Farming Hero Backend API!"}

# --- FIELD ENDPOINTS ---

@app.post("/fields/", response_model=FieldResponse)
def create_field(field: FieldCreate, db: Session = Depends(get_db)):
    db_field = FieldModel(**field.dict())
    db.add(db_field)
    db.commit()
    db.refresh(db_field)
    return db_field

@app.get("/fields/", response_model=List[FieldResponse])
def get_all_fields(db: Session = Depends(get_db)):
    return db.query(FieldModel).all()

@app.get("/fields/{field_id}/details")
def get_field_details(field_id: int, db: Session = Depends(get_db)):
    field = db.query(FieldModel).filter(FieldModel.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    
    return {
        "field": field,
        "crops": field.crops,
        "irrigations": field.irrigations,
        "fertilizers": field.fertilizers,
        "expenses": field.expenses
    }

# --- CROP MANAGEMENT ENDPOINTS ---

@app.post("/crops/", response_model=CropResponse)
def add_crop(crop: CropCreate, db: Session = Depends(get_db)):
    db_crop = CropModel(**crop.dict())
    db.add(db_crop)
    db.commit()
    db.refresh(db_crop)
    return db_crop

@app.put("/crops/{crop_id}/growth")
def update_crop_growth(crop_id: int, stage: str, status: Optional[str] = "Active", db: Session = Depends(get_db)):
    crop = db.query(CropModel).filter(CropModel.id == crop_id).first()
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")
    crop.growth_stage = stage
    crop.status = status
    db.commit()
    return {"message": "Crop growth stage updated", "crop": crop}

# --- WATER & FERTILIZER TRACKING ---

@app.post("/irrigations/")
def log_irrigation(irrigation: IrrigationCreate, db: Session = Depends(get_db)):
    db_irrigation = IrrigationModel(**irrigation.dict())
    db.add(db_irrigation)
    db.commit()
    db.refresh(db_irrigation)
    return db_irrigation

@app.post("/fertilizers/")
def log_fertilizer(fertilizer: FertilizerCreate, db: Session = Depends(get_db)):
    db_fertilizer = FertilizerModel(**fertilizer.dict())
    db.add(db_fertilizer)
    db.commit()
    db.refresh(db_fertilizer)
    return db_fertilizer

# --- EXPENSE CALCULATIONS ---

@app.post("/expenses/", response_model=ExpenseResponse)
def add_expense(expense: ExpenseCreate, db: Session = Depends(get_db)):
    db_expense = ExpenseModel(**expense.dict())
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

@app.get("/expenses/summary", response_model=TotalExpenseSummary)
def get_expense_summary(db: Session = Depends(get_db)):
    all_expenses = db.query(ExpenseModel).all()
    total = sum([e.amount for e in all_expenses])
    
    field_expenses = {}
    fields = db.query(FieldModel).all()
    for f in fields:
        field_total = sum([e.amount for e in f.expenses])
        field_expenses[f.name] = field_total
        
    return {
        "total_expenses": total,
        "expenses_by_field": field_expenses
    }

# --- EQUIPMENT MANAGEMENT ---

@app.post("/equipment/")
def add_equipment(equipment: EquipmentCreate, db: Session = Depends(get_db)):
    db_equipment = EquipmentModel(**equipment.dict())
    db.add(db_equipment)
    db.commit()
    db.refresh(db_equipment)
    return db_equipment

@app.get("/equipment/")
def list_equipment(db: Session = Depends(get_db)):
    return db.query(EquipmentModel).all()