// Whether the twice-a-day checks are on: a few words for the blue strip, and a
// panel for the side column that says how to turn them on.

import type { Schedule } from "../../lib/api";
import { timeUntil } from "../../lib/format";
import { ClockIcon } from "../common/Icons";

const timeOfDay = (time: string) => {
  const [hours, minutes] = time.split(":").map(Number);
  return new Date(2000, 0, 1, hours, minutes).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
};

export function ScheduleStatus({ schedule }: { schedule: Schedule | null }) {
  if (!schedule) return null;
  let text = "Auto-check: use cron here";
  if (schedule.on && schedule.next_check) text = `Auto-check on · next ${timeUntil(schedule.next_check)}`;
  else if (schedule.available) text = "Auto-check off";
  return (
    <span className={`schedule-status ${schedule.on ? "on" : "off"}`}>
      <ClockIcon size={14} />
      {text}
    </span>
  );
}

export function SchedulePanel({ schedule }: { schedule: Schedule | null }) {
  if (!schedule) return null;
  return (
    <section className="panel" aria-labelledby="schedule-heading">
      <h2 id="schedule-heading" className="panel-title">
        <ClockIcon /> Auto-checks
      </h2>
      {schedule.on ? (
        <p className="small">
          <span className="dot-on" aria-hidden="true" /> On, every day at {schedule.times.map(timeOfDay).join(" and ")}.
          {schedule.next_check && <> Next one {timeUntil(schedule.next_check)}.</>}
        </p>
      ) : schedule.available ? (
        <>
          <p className="small">Off: prices are only checked when you press Check now. To check twice a day, run:</p>
          <code className="command">python -m price_tracker schedule on</code>
        </>
      ) : (
        <>
          <p className="small">This server has no Windows Task Scheduler. Have cron run, twice a day:</p>
          <code className="command">python -m price_tracker check --log</code>
        </>
      )}
    </section>
  );
}
