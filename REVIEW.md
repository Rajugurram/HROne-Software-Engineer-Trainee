# REVIEW.md

| # | Where | Defect / symptom | Fix |
|---|---|---|---|
| 1 | `health()` | Returned `ok` without checking MongoDB, even when the database was unavailable. | Execute `ping`; return HTTP 503 on connection failure. |
| 2 | Index setup | Attendance had a unique compound index, but common employee and date/status access paths lacked supporting indexes. | Add unique employee-code, department/join-date, date/employee, and status/date indexes. |
| 3 | Employee creation | Duplicate check alone is race-prone under simultaneous requests. | Add a unique `emp_code` index; catch duplicate-key errors and return 409 (ensure this handler is included if testing concurrent creates). |
| 4 | Timestamp inputs | Pydantic `int` alone can coerce strings/floats and does not reject seconds-scale timestamps. | Validate epoch-millisecond values as strict integers and reject out-of-range values (verify/enforce in request models before final submission). |
| 5 | Punch-in status | Arbitrary status values could be stored. | Restrict status to `PRESENT`, `WFH`, or `ON_DUTY` (enforce in model validation before final submission). |
| 6 | Punch-in / punch-out | Naive datetimes and inconsistent overnight date calculations can cause timezone boundary errors. | Normalize instants to UTC and derive attendance dates in IST using employee shift times. |
| 7 | Punch-out | Two concurrent requests could both read `punch_out=None`; the update result was not checked. | Use a conditional atomic update and return 409 when `matched_count` is zero. |
| 8 | Punch-out | Work-hour duration and invalid timestamp ordering need validation. | Reject punch-out at or before punch-in and durations above the contract maximum. |
| 9 | Regularization | Concurrent read/modify/write can overwrite another request's changes or history. | Use compare-and-set update conditions and `$push` history atomically; return 409 on a lost race. |
| 10 | Regularization | Timestamp validation and overnight shift checks are critical edge cases. | Validate strict millisecond timestamps and recalculate all derived fields using the employee's shift. |
| 11 | Employee monthly | Weekday and join-date boundaries must be calculated consistently; the original implementation iterates calendar dates in Python. | Keep aggregation for attendance totals and validate the monthly working-day calculation against the contract. |
| 12 | Department summary | A log-first aggregation omits employees with no logs and can miscount headcount. | Start from eligible employees and `$lookup` logs, preserving employees without matching records. |
| 13 | Late leaderboard | Array position is not competition rank; ties at the cutoff must be retained. | Use `$rank`, sort ties by employee code, and apply limit to rank rather than row count. |
| 14 | Department trend | Missing dates and weekends must be represented; Python loops are not acceptable for gap filling. | Use MongoDB `$densify` and a window stage for the moving average. |
| 15 | Explain endpoint | Analytics queries need a reproducible execution plan with execution statistics. | Add endpoint-specific explain operations and return raw explain output. |

## Items reviewed
- The compound unique index on `(emp_code, date)` is appropriate for one attendance record per employee per attendance date.
- UTC instants and IST calendar dates are both needed; they are not interchangeable.
- Derived attendance values should be recalculated rather than accepted from request bodies.
