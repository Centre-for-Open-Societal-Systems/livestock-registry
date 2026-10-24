# Historical pre-fix seed evidence

Retained for traceability; these files are not the current acceptance result.
The initial SQLAlchemy multi-statement probe (`invalid-sqlalchemy-probe.json`)
did not preserve native psql percent-literal/transaction semantics and must not
be used to assert seed success or failure. The initial native psql passes show
the genuine duplicate-key and Crop lookup-table ownership failures subsequently
fixed. Current metadata verification uses ../target-pass-1.json,
../target-pass-2.json and ../seed-rehearsal.json with zero native SQL errors.
