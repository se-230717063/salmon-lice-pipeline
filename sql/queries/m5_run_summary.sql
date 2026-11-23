-- Values are bound parameters. Rebuild/manual runs cannot count as scheduled days.
WITH runs AS (
 SELECT run_id,run_time,run_kind,COUNT(*) AS steps,
        SUM(exit_code<>0) AS failed_steps,MIN(started_at) AS started,MAX(finished_at) AS finished
 FROM pipeline_run GROUP BY run_id,run_time,run_kind
)
SELECT run_kind,MIN(run_time) AS first_run,MAX(run_time) AS last_run,
       COUNT(*) AS runs,COUNT(DISTINCT date(run_time,:local_offset)) AS local_days,
       SUM(failed_steps>0) AS failed_runs
FROM runs WHERE run_time>=:since AND run_time<=:until GROUP BY run_kind;
