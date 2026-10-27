# Popup identity metadata correction

The identity split previously extracted widgets with lax recursive JSONPath. Array auto-unwrapping could visit widget objects twice. The helper now uses strict descent and deterministically retains the first occurrence per requested widget ID. Its intake assertion and native regression checks count actual widget objects rather than DISTINCT IDs.

The last-sorting `zzzzzzzz_popup_only_fin.sql` projects FIN widgets to native read-only displays. Stored IDs and data paths remain intact; Verify with Fayda writes the backing FIN field. The separate 16-digit FAN input remains available. Registered Farmer name and source projections remain present. No framework, compiled UI, storage, or verification-service change is included.

`test_popup_identity_metadata.py` checks nested arrays and genuine duplicate IDs against the SQL helper, seeds all metadata, reapplies the final patch twice, and repeats the full seed twice. It walks actual widget arrays to assert five unique intake widgets, read-only FIN in every registered/intake-bound section, editable intake FAN, unchanged stored field paths, registered Farmer name, and stable metadata.

Host result: one duplicate-counter regression passed per registry; three PostgreSQL tests per registry are skipped without FARMER_TEST_DATABASE_URL. Python syntax and Git whitespace checks pass. Native PostgreSQL execution and full integration acceptance remain promotion blockers until the integration branch CI executes these tests. Local Docker is on hold following the engine failure; no runtime mutation or deployment was performed.

Registered duplicate identity controls from earlier profile-panel matching are also pruned in the final patch, preserving all other widgets and null configuration array values. Native tests explicitly count each registered identity control once. All three current production widgets/helpers passed 54 browser assertions each (162 total) and targeted strict TypeScript checks against the installed platform widget dependency. Browser evidence uses real platform Redux/data-path actions with request fixtures; live verification and exact deployed dependency builds remain pending.

26 October hosted follow-up: candidate `fd525f57830161a388e139f797768fb34d5ced55` passed all four actual PostgreSQL
identity cases with no skips, repeated metadata with zero SQL errors and identical
configuration, native notification mapping and 54 browser assertions. See
[the hosted run](https://github.com/asmitonweb/livestock-registry/actions/runs/40266605930).
The earlier host-only skipped result above is retained as historical context.
Full lifecycle, live provider and restored-data acceptance remain separate.

Expanded PostgreSQL follow-up [run 40267918917](https://github.com/asmitonweb/livestock-registry/actions/runs/40267918917)
passed 268 checks and executed all 72 database cases. Nineteen explicitly
named HTTP simulation cases remained skipped in that run; a separate signed HTTP
gate is being prepared. Module processes and fixture databases are isolated inside
one owned disposable PostgreSQL container; production model behavior is unchanged.

Signed HTTP follow-up at `4c7d9e65a9c5df51e965977161f226f18dbab1d1` [run 40270037553](https://github.com/asmitonweb/livestock-registry/actions/runs/40270037553) passed all 19 previously skipped executions with zero skips (13 distinct behaviors, inherited duplicates counted explicitly). JUnit case-name/class counters match the full-PG skip counter exactly; no substitute cases were selected. Real production lookup/IAM/AWE clients issued 173 Postman request events per registry. Exact owned resource cleanup completed. These are synthetic dependencies over real HTTP, not proof of the live AWE engine, consent service or Kafka transport.
