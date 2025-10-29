import calendar
from datetime import datetime, date, time, timezone
from fastapi import FastAPI, HTTPException, status
from pymongo import MongoClient
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId
import uvicorn
import os
from dotenv import load_dotenv
app = FastAPI()
 
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
client: MongoClient = MongoClient(MONGO_URI)
# Now you can directly use the client as the database object
db = client.dairy_project

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    @classmethod
    def validate(cls, v, *args, **kwargs):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)
    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")

class Customer(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    name: str
    address: str
    phone_number: str
    default_milk_morning: float = 0.0
    default_milk_evening: float = 0.0
    price_per_liter: float = 60.0
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, json_encoders={ObjectId: str})

class Variation(BaseModel):
    customer_id: str
    date: datetime
    morning_quantity: float
    evening_quantity: float

@app.get("/")
def read_root():
    return {"message": "Welcome to the Dairy Project API"}

@app.get("/customers", response_model=list[Customer])
def get_all_customers():
    customers = list(db.customers.find())
    return customers

@app.post("/customers", status_code=status.HTTP_201_CREATED, response_model=Customer)
def create_customer(customer: Customer):
    customer_dict = customer.model_dump(by_alias=True, exclude={"id"})
    result = db.customers.insert_one(customer_dict)
    created_customer = db.customers.find_one({"_id": result.inserted_id})
    return created_customer

@app.post("/variations", status_code=status.HTTP_201_CREATED)
def add_variation(variation: Variation):
    variation_dict = variation.model_dump()
    db.daily_variations.update_one({"customer_id": variation.customer_id, "date": variation.date}, {"$set": variation_dict}, upsert=True)
    return {"message": "Variation recorded successfully"}

def get_data_for_month(customer_id: str, month: int, year: int):
    try:
        obj_id = ObjectId(customer_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Customer ID format")
    customer = db.customers.find_one({"_id": obj_id})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    start_date = datetime(year, month, 1, tzinfo=timezone.utc)
    num_days = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, num_days, 23, 59, 59, tzinfo=timezone.utc)
    variations_cursor = db.daily_variations.find({"customer_id": customer_id, "date": {"$gte": start_date, "$lte": end_date}})
    variations = {v["date"].strftime('%Y-%m-%d'): v for v in variations_cursor}
    return customer, variations, num_days

@app.get("/customers/{customer_id}/bill")
def get_customer_bill(customer_id: str, month: int, year: int):
    customer, variations, num_days = get_data_for_month(customer_id, month, year)
    total_liters = 0.0
    for day_num in range(1, num_days + 1):
        current_date_str = date(year, month, day_num).isoformat()
        if current_date_str in variations:
            total_liters += variations[current_date_str]["morning_quantity"]
            total_liters += variations[current_date_str]["evening_quantity"]
        else:
            total_liters += customer["default_milk_morning"]
            total_liters += customer["default_milk_evening"]
    amount_due = total_liters * customer["price_per_liter"]
    return {"customer_name": customer["name"], "month": month, "year": year, "total_liters": round(total_liters, 2), "amount_due": round(amount_due, 2)}

@app.get("/customers/{customer_id}/monthly_sheet")
def get_monthly_sheet_data(customer_id: str, month: int, year: int):
    customer, variations, num_days = get_data_for_month(customer_id, month, year)
    sheet_data = []
    today = date.today()
    days_to_show = num_days
    if year == today.year and month == today.month:
        days_to_show = today.day
    total_morning, total_evening = 0.0, 0.0
    for day_num in range(1, days_to_show + 1):
        current_date_str = date(year, month, day_num).isoformat()
        if current_date_str in variations:
            morning_qty = variations[current_date_str]["morning_quantity"]
            evening_qty = variations[current_date_str]["evening_quantity"]
        else:
            morning_qty = customer["default_milk_morning"]
            evening_qty = customer["default_milk_evening"]
        daily_total = morning_qty + evening_qty
        total_morning += morning_qty
        total_evening += evening_qty
        sheet_data.append({"Date": current_date_str, "Morning (L)": morning_qty, "Evening (L)": evening_qty, "Daily Total (L)": daily_total})
    grand_total = total_morning + total_evening
    return {"sheet_data": sheet_data, "totals": {"total_morning": round(total_morning, 2), "total_evening": round(total_evening, 2), "grand_total_liters": round(grand_total, 2), "amount_due": round(grand_total * customer["price_per_liter"], 2)}}

@app.get("/customers/{customer_id}/variations_summary")
def get_variations_summary(customer_id: str, month: int, year: int):
    """Fetches only the dates with variations for a given customer and month."""
    customer, variations, num_days = get_data_for_month(customer_id, month, year)
    
    summary_data = []
    for date_str, variation_data in variations.items():
        summary_data.append({
            "date": date_str,
            "morning": variation_data["morning_quantity"],
            "evening": variation_data["evening_quantity"],
            "total": variation_data["morning_quantity"] + variation_data["evening_quantity"],
            # Add the default values to the response
            "default_morning": customer["default_milk_morning"],
            "default_evening": customer["default_milk_evening"]
        })
        
    summary_data.sort(key=lambda x: x['date'])
    return summary_data

import uvicorn

if __name__ == "__main__":
    print("--- Starting FastAPI Server ---")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
