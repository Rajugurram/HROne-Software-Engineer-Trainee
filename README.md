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
3. Create `.env` locally :
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

## Known Issues and Limitations

The following issues remain under investigation:

1. **MongoDB Atlas connectivity:** During local testing, the application
   encountered an SSL handshake failure while connecting to MongoDB Atlas.
   As a result, database-dependent endpoints could not be fully verified.

2. **Database-dependent testing:** End-to-end testing of all API endpoints
   against a working MongoDB database remains incomplete.

3. **Index initialization:** The application is configured to attempt index
   creation during startup. If MongoDB is unavailable, index initialization
   may fail, and database operations may not work as expected.

### Testing Status

- Python syntax compilation: Passed.
- Python dependencies: Installed.
- FastAPI startup: Attempted; startup completed, but port 8000 was already
  occupied in one test.
- MongoDB connectivity: Failed during testing due to an SSL handshake error.
- Complete API and database integration testing: Not yet completed.

### Next Steps

- Investigate the MongoDB Atlas TLS connection issue.
- Verify database connectivity and index creation.
- Test all required endpoints against a working MongoDB database.
- Validate analytics results and query execution plans.