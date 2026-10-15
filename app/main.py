"""
Employee Attendance & Analytics API - STARTER

Run:  uvicorn app.main:app --port 8000
Env:  MONGO_URI, MONGO_DB (a local .env is loaded for convenience)

This file was written quickly by a colleague who has left the company. The happy path
works, but nobody has reviewed it. Read PROBLEM_STATEMENT.docx for what is expected of you,
openapi.yaml for the contract and DATA_MODEL.md for what is stored in MongoDB.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient

from decimal import Decimal, ROUND_HALF_UP

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
db = client[os.getenv("MONGO_DB", "attendance_db")]

db.attendance_logs.create_index(
    [("emp_code", 1), ("date", 1)],
    unique=True,
    name="unique_employee_attendance_date",
)

IST = timezone(timedelta(hours=5, minutes=30))

app = FastAPI(title="Employee Attendance & Analytics API", version="2.0.0")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #



def round_half_up(value: float, places: int = 2) -> float:
    quantum = Decimal("1").scaleb(-places)
    return float(
        Decimal(str(value)).quantize(
            quantum,
            rounding=ROUND_HALF_UP,
        )
    )


def to_ist(value: datetime) -> datetime:
    """Convert a datetime to Indian Standard Time."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(IST)


def compute_late_minutes(punch_in: datetime, shift_start: str) -> int:
    local_punch = to_ist(punch_in)
    h, m = map(int, shift_start.split(":"))
    shift_start_dt = local_punch.replace(
        hour=h, minute=m, second=0, microsecond=0
    )

    # A shift starting at or after midnight may belong to the previous
    # attendance day; its start must be resolved by the caller.
    elapsed = int((local_punch - shift_start_dt).total_seconds() // 60)
    return elapsed if elapsed > 10 else 0


def compute_work_hours(punch_in: datetime, punch_out: datetime) -> float:
    start = punch_in
    end = punch_out

    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    hours = (end - start).total_seconds() / 3600
    return round_half_up(hours, 2)


def compute_overtime(
    punch_out: datetime,
    shift_end: str,
    date_str: str,
    overnight: bool = False,
) -> int:
    local_out = to_ist(punch_out)
    h, m = map(int, shift_end.split(":"))

    end_date = datetime.fromisoformat(date_str).date()
    if overnight:
        end_date += timedelta(days=1)

    shift_end_dt = datetime(
        end_date.year, end_date.month, end_date.day,
        h, m, tzinfo=IST,
    )

    minutes = int((local_out - shift_end_dt).total_seconds() // 60)

    # Overtime is counted only when at least 30 minutes are worked
    # after the scheduled shift end.
    return minutes if minutes >= 30 else 0


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class EmployeeIn(BaseModel):
    emp_code: str
    name: str
    email: str
    department: str
    shift_start: str = "09:30"
    shift_end: str = "18:30"
    joined_on: str


class PunchInIn(BaseModel):
    emp_code: str
    punched_at: Optional[int] = None
    status: str = "PRESENT"

class RegularizeRequest(BaseModel):
    status: Optional[str] = None
    punch_in: Optional[int] = None
    punch_out: Optional[int] = None
    reason: str
    regularized_by: str

# --------------------------------------------------------------------------- #
# Endpoints provided
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/employees", status_code=201)
def create_employee(body: EmployeeIn):
    if db.employees.find_one({"emp_code": body.emp_code}):
        raise HTTPException(409, "emp_code already exists")
    doc = body.model_dump()
    doc["created_at"] = datetime.now()
    db.employees.insert_one(doc)
    doc.pop("_id", None)
    return doc


@app.get("/employees")
def list_employees(
    department: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    if page < 1:
        raise HTTPException(
            status_code=422,
            detail="page must be at least 1",
        )

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=422,
            detail="page_size must be between 1 and 100",
        )

    q = {}

    if department:
        q["department"] = department

    total = db.employees.count_documents(q)

    items = list(
        db.employees.find(q, {"_id": 0})
        .sort("emp_code", 1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@app.post("/attendance/punch-in", status_code=201)
def punch_in(body: PunchInIn):
    emp = db.employees.find_one({"emp_code": body.emp_code})

    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Convert the supplied timestamp from epoch milliseconds to UTC.
    # If no timestamp is supplied, use the current UTC time.
    if body.punched_at is not None:
        ts = datetime.fromtimestamp(
            body.punched_at / 1000,
            tz=timezone.utc,
        )
    else:
        ts = datetime.now(timezone.utc)

    # Convert the timestamp to IST for attendance calculations.
    local_ts = to_ist(ts)

    shift_start = emp["shift_start"]
    shift_end = emp["shift_end"]

    start_hour, start_minute = map(int, shift_start.split(":"))
    end_hour, end_minute = map(int, shift_end.split(":"))

    # Determine whether the employee has an overnight shift.
    overnight = (end_hour, end_minute) <= (start_hour, start_minute)

    # For an overnight shift, punches before shift end belong
    # to the previous attendance date.
    attendance_date = local_ts.date()

    if overnight and (local_ts.hour, local_ts.minute) < (
        end_hour,
        end_minute,
    ):
        attendance_date -= timedelta(days=1)

    d = attendance_date.isoformat()

    doc = {
        "emp_code": body.emp_code,
        "date": d,
        "status": body.status,
        "punch_in": ts,
        "punch_out": None,
        "work_hours": None,
        "late_minutes": compute_late_minutes(ts, shift_start),
        "overtime_minutes": 0,
        "half_day": False,
        "history": [],
    }

    try:
        res = db.attendance_logs.insert_one(doc)
    except Exception as exc:
        # Duplicate-key errors should return HTTP 409.
        if getattr(exc, "code", None) == 11000:
            raise HTTPException(
                status_code=409,
                detail="Already punched in for this date",
            )
        raise

    # Do not expose MongoDB's internal _id in the API response.
    doc.pop("_id", None)

    return doc


@app.post("/attendance/punch-out")
def punch_out(body: PunchInIn):
    emp = db.employees.find_one({"emp_code": body.emp_code})

    if not emp:
        raise HTTPException(
            status_code=404,
            detail="Employee not found",
        )

    # Get the punch-out timestamp in UTC.
    if body.punched_at is not None:
        ts = datetime.fromtimestamp(
            body.punched_at / 1000,
            tz=timezone.utc,
        )
    else:
        ts = datetime.now(timezone.utc)

    local_ts = to_ist(ts)

    # Determine the attendance date.
    start_hour, start_minute = map(
        int, emp["shift_start"].split(":")
    )
    end_hour, end_minute = map(
        int, emp["shift_end"].split(":")
    )

    overnight = (end_hour, end_minute) <= (
        start_hour, start_minute
    )

    attendance_date = local_ts.date()

    if overnight and (local_ts.hour, local_ts.minute) < (
        end_hour, end_minute
    ):
        attendance_date -= timedelta(days=1)

    d = attendance_date.isoformat()

    record = db.attendance_logs.find_one({
        "emp_code": body.emp_code,
        "date": d,
    })

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Punch-in record not found",
        )

    if record.get("punch_out") is not None:
        raise HTTPException(
            status_code=409,
            detail="Already punched out",
        )

    punch_in_time = record["punch_in"]

    # Calculate hours, overtime, and half-day status.
    work_hours = compute_work_hours(punch_in_time, ts)

    overtime_minutes = compute_overtime(
        ts,
        emp["shift_end"],
        d,
        overnight=overnight,
    )

    half_day = work_hours < 4.50

    db.attendance_logs.update_one(
        {
            "_id": record["_id"],
            "punch_out": None,
        },
        {
            "$set": {
                "punch_out": ts,
                "work_hours": work_hours,
                "overtime_minutes": overtime_minutes,
                "half_day": half_day,
            }
        },
    )

    updated = db.attendance_logs.find_one({
        "emp_code": body.emp_code,
        "date": d,
    }, {"_id": 0})

    return updated


@app.get("/attendance")
def list_attendance(
    emp_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    if page < 1:
        raise HTTPException(
            status_code=422,
            detail="page must be at least 1",
        )

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=422,
            detail="page_size must be between 1 and 100",
        )

    q = {}

    if emp_code:
        q["emp_code"] = emp_code

    if date_from or date_to:
        q["date"] = {}

        if date_from:
            q["date"]["$gte"] = date_from

        if date_to:
            q["date"]["$lte"] = date_to

    if status:
        q["status"] = status

    # Count only records matching the filters.
    total = db.attendance_logs.count_documents(q)

    # Let MongoDB sort and paginate the records.
    cursor = (
        db.attendance_logs.find(q, {"_id": 0})
        .sort("date", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    items = list(cursor)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@app.patch("/attendance/{emp_code}/{date}")
def regularize_attendance(
    emp_code: str,
    date: str,
    body: RegularizeRequest,
):
    # Find the employee.
    emp = db.employees.find_one({"emp_code": emp_code})

    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Find the attendance record.
    record = db.attendance_logs.find_one(
        {"emp_code": emp_code, "date": date}
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Attendance record not found",
        )

    # Start with the existing values.
    old_status = record.get("status", "PRESENT")
    old_in = record.get("punch_in")
    old_out = record.get("punch_out")

    new_status = body.status if body.status is not None else old_status
    new_in = (
        datetime.fromtimestamp(body.punch_in / 1000, tz=timezone.utc)
        if body.punch_in is not None
        else old_in
    )
    new_out = (
        datetime.fromtimestamp(body.punch_out / 1000, tz=timezone.utc)
        if body.punch_out is not None
        else old_out
    )

    # Validate the status.
    valid_statuses = {"PRESENT", "WFH", "ON_DUTY", "ABSENT", "LEAVE"}

    if new_status not in valid_statuses:
        raise HTTPException(status_code=422, detail="Invalid attendance status")

    # ABSENT and LEAVE must not have punch times.
    if new_status in {"ABSENT", "LEAVE"}:
        if body.punch_in is not None or body.punch_out is not None:
            raise HTTPException(
                status_code=422,
                detail="ABSENT or LEAVE cannot include punch times",
            )
        new_in = None
        new_out = None

    # Presence statuses require a punch-in.
    elif new_in is None:
        raise HTTPException(
            status_code=422,
            detail="Presence status requires punch_in",
        )

    # Validate the correction reason and author.
    if not body.reason or len(body.reason.strip()) < 5:
        raise HTTPException(
            status_code=422,
            detail="Reason must contain at least 5 characters",
        )

    if not body.regularized_by or len(body.regularized_by.strip()) < 1:
        raise HTTPException(
            status_code=422,
            detail="regularized_by is required",
        )

    # Validate punch-out.
    if new_out is not None:
        if new_in is None:
            raise HTTPException(
                status_code=422,
                detail="punch_out requires punch_in",
            )

        # Normalize both datetimes to UTC.
        if new_in.tzinfo is None:
            new_in = new_in.replace(tzinfo=timezone.utc)

        if new_out.tzinfo is None:
            new_out = new_out.replace(tzinfo=timezone.utc)

        if new_out <= new_in:
            raise HTTPException(
                status_code=422,
                detail="punch_out must be after punch_in",
            )

        if (new_out - new_in).total_seconds() > 24 * 60 * 60:
            raise HTTPException(
                status_code=422,
                detail="Punch duration cannot exceed 24 hours",
            )

    # Check that punch-in belongs to this attendance date in IST.
    if new_in is not None:
        if to_ist(new_in).date().isoformat() != date:
            raise HTTPException(
                status_code=422,
                detail="punch_in must belong to the attendance date",
            )

    # Recalculate the derived fields.
    if new_in is not None:
        late_minutes = compute_late_minutes(new_in, emp["shift_start"])
    else:
        late_minutes = 0

    if new_in is not None and new_out is not None:
        work_hours = compute_work_hours(new_in, new_out)

        end_hour, end_minute = map(int, emp["shift_end"].split(":"))
        start_hour, start_minute = map(int, emp["shift_start"].split(":"))
        overnight = (end_hour, end_minute) <= (start_hour, start_minute)

        overtime_minutes = compute_overtime(
            new_out,
            emp["shift_end"],
            date,
            overnight,
        )
        half_day = work_hours < 4.50
    else:
        work_hours = None
        overtime_minutes = 0
        half_day = False

    # Only include fields that actually changed in the audit history.
    changes = {}

    def epoch_ms(value):
        if value is None:
            return None
        return int(value.timestamp() * 1000)

    if old_status != new_status:
        changes["status"] = {"from": old_status, "to": new_status}

    if old_in != new_in:
        changes["punch_in"] = {
            "from": epoch_ms(old_in),
            "to": epoch_ms(new_in),
        }

    if old_out != new_out:
        changes["punch_out"] = {
            "from": epoch_ms(old_out),
            "to": epoch_ms(new_out),
        }

    if record.get("work_hours") != work_hours:
        changes["work_hours"] = {
            "from": record.get("work_hours"),
            "to": work_hours,
        }

    if record.get("late_minutes", 0) != late_minutes:
        changes["late_minutes"] = {
            "from": record.get("late_minutes", 0),
            "to": late_minutes,
        }

    if record.get("overtime_minutes", 0) != overtime_minutes:
        changes["overtime_minutes"] = {
            "from": record.get("overtime_minutes", 0),
            "to": overtime_minutes,
        }

    if record.get("half_day", False) != half_day:
        changes["half_day"] = {
            "from": record.get("half_day", False),
            "to": half_day,
        }

    if not changes:
        raise HTTPException(
            status_code=422,
            detail="The correction does not change anything",
        )

    history_entry = {
        "at": datetime.now(timezone.utc),
        "by": body.regularized_by,
        "reason": body.reason,
        "changes": changes,
    }

    # Update the record and append one history entry.
    db.attendance_logs.update_one(
        {"_id": record["_id"]},
        {
            "$set": {
                "status": new_status,
                "punch_in": new_in,
                "punch_out": new_out,
                "work_hours": work_hours,
                "late_minutes": late_minutes,
                "overtime_minutes": overtime_minutes,
                "half_day": half_day,
            },
            "$push": {"history": history_entry},
        },
    )

    # Return the updated record without MongoDB's internal ID.
    updated = db.attendance_logs.find_one(
        {"emp_code": emp_code, "date": date},
        {"_id": 0},
    )

    return updated
    return updated


# ADD THE MONTHLY ANALYTICS ENDPOINT BELOW THIS LINE

@app.get("/analytics/employees/{emp_code}/monthly")
def employee_monthly(emp_code: str, month: str):
    # Validate YYYY-MM format.
    try:
        month_start = datetime.strptime(month, "%Y-%m").date()
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="month must use YYYY-MM format",
        )

    if month_start.strftime("%Y-%m") != month:
        raise HTTPException(
            status_code=422,
            detail="month must use YYYY-MM format",
        )

    # Check that the employee exists.
    emp = db.employees.find_one({"emp_code": emp_code})

    if not emp:
        raise HTTPException(
            status_code=404,
            detail="Employee not found",
        )

    # Calculate the month's date range.
    if month_start.month == 12:
        next_month = month_start.replace(
            year=month_start.year + 1,
            month=1,
            day=1,
        )
    else:
        next_month = month_start.replace(
            month=month_start.month + 1,
            day=1,
        )

    start_date = month_start.isoformat()
    end_date = next_month.isoformat()

    # Count weekdays from the employee's joining date.
    joined_on = datetime.strptime(
        emp["joined_on"],
        "%Y-%m-%d",
    ).date()

    effective_start = max(month_start, joined_on)

    working_days = 0
    current_day = effective_start

    while current_day < next_month:
        if current_day.weekday() < 5:
            working_days += 1

        current_day += timedelta(days=1)

    # Calculate attendance totals in MongoDB.
    pipeline = [
        {
            "$match": {
                "emp_code": emp_code,
                "date": {
                    "$gte": start_date,
                    "$lt": end_date,
                },
            }
        },
        {
            "$group": {
                "_id": None,
                "present_days": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {
                                        "$in": [
                                            "$status",
                                            ["PRESENT", "WFH", "ON_DUTY"],
                                        ]
                                    },
                                    {
                                        "$lt": [
                                            {
                                                "$dayOfWeek": {
                                                    "$dateFromString": {
                                                        "dateString": "$date"
                                                    }
                                                }
                                            },
                                            7,
                                        ]
                                    },
                                ]
                            },
                            {
                                "$cond": [
                                    {"$eq": ["$half_day", True]},
                                    0.5,
                                    1,
                                ]
                            },
                            0,
                        ]
                    }
                },
                "leave_days": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$status", "LEAVE"]},
                            1,
                            0,
                        ]
                    }
                },
                "late_count": {
                    "$sum": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$late_minutes", 0]}, 0]},
                            1,
                            0,
                        ]
                    }
                },
                "total_late_minutes": {
                    "$sum": {"$ifNull": ["$late_minutes", 0]}
                },
                "total_overtime_minutes": {
                    "$sum": {"$ifNull": ["$overtime_minutes", 0]}
                },
            }
        },
    ]

    results = list(db.attendance_logs.aggregate(pipeline))

    totals = results[0] if results else {}

    present_days = totals.get("present_days", 0)
    attendance_pct = (
        round_half_up((present_days / working_days) * 100, 4)
        if working_days > 0
        else None
    )

    return {
        "emp_code": emp_code,
        "month": month,
        "working_days": working_days,
        "present_days": present_days,
        "leave_days": totals.get("leave_days", 0),
        "late_count": totals.get("late_count", 0),
        "total_late_minutes": totals.get("total_late_minutes", 0),
        "total_overtime_minutes": totals.get(
            "total_overtime_minutes",
            0,
        ),
        "attendance_pct": attendance_pct,
    }