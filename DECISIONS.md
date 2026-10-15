# DECISIONS.md

1. **Indexes:** I use a unique index on employee code and a unique compound index on `(emp_code, date)` so duplicate employees and duplicate daily attendance records cannot be inserted under concurrency. Department/join-date and attendance date/status indexes support common filters, analytics date ranges, and explainable query plans. Indexes are created idempotently at startup.

2. **Simultaneous punch-ins:** Both requests may initially observe no record, but the unique compound index is the final concurrency guard. One insert succeeds with 201; the other receives duplicate-key error 11000 and must be translated to 409.

3. **Leaderboard ties:** The leaderboard uses competition ranking. Equal total late minutes share a rank and the next rank is skipped (1, 2, 2, 4). The limit filters rank, not array position, so all employees tied at the cutoff rank are returned. Employee code provides deterministic order within ties.

4. **Employees without logs:** Department summaries start with employees who joined by the end of the month and then look up attendance. Preserving employees with no matching logs ensures they count toward headcount but contribute zero to attendance totals.

5. **100x data:** I would monitor explain plans and latency, verify compound indexes against real filter/sort patterns, pre-aggregate frequently requested monthly summaries, and move expensive trend reporting to a scheduled/materialized analytics collection if freshness requirements allow it.
