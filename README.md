# Employee Attendance & Analytics API

FastAPI + MongoDB implementation for the HROne Software Engineer Trainee assignment.

## Requirements
- Python 3.11+
- MongoDB Atlas or MongoDB 6+
- Dependencies in `requirements.txt`

## Setup
1. Create a virtual environment:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install packages:
   ```powershell
   py -m pip install -r requirements.txt
   ```
3. Create `.env` locally (do not commit it):
   ```env
   MONGO_URI=mongodb+srv://<username>:<password>@<cluster-host>/?retryWrites=true&w=majority
   MONGO_DB=attendance_db
   ```
4. Start the API:
   ```powershell
   uvicorn app.main:app --port 8000
   ```
5. Open `http://127.0.0.1:8000/docs`.

## Implemented endpoints
- `GET /health`
- `POST /employees`, `GET /employees`
- `POST /attendance/punch-in`, `POST /attendance/punch-out`
- `GET /attendance`
- `PATCH /attendance/{emp_code}/{date}`
- `GET /analytics/employees/{emp_code}/monthly`
- `GET /analytics/departments/summary`
- `GET /analytics/leaderboard/late`
- `GET /analytics/departments/{department}/trend`
- `GET /admin/explain/{endpoint}`

## Notes
- MongoDB indexes are created automatically at import/startup.
- The API expects epoch milliseconds for timestamps and `YYYY-MM-DD` dates.
- Verify all endpoints against `openapi.yaml` and the assignment's edge cases before final submission.
- Never commit `.env`, credentials, `.venv`, or backup files.
