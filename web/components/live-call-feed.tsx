"use client";

import { useEffect, useRef, useState } from "react";
import { subscribeToNegotiationEvents, type LiveEvent } from "@/lib/api";

// Events arrive from the backend's SSE feed while the call is happening - turns
// as they're spoken, offers the agent logs mid-call through its tools, and the
// post-call verification result. The stream replays what's already happened on
// connect, so landing on this page mid-call still shows the whole conversation.

const STATUS_COPY: Record<string, string> = {
  dialing: "Dialing…",
  connected: "Connected",
  call_ended: "Call ended",
  awaiting_recording: "Waiting for the recording",
  transcribing: "Transcribing the call",
  needs_human_review: "Needs human review",
};

export function LiveCallFeed({ taskId }: { taskId: string }) {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [backend, setBackend] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    return subscribeToNegotiationEvents(taskId, (event) => {
      if (event.type === "status") {
        setStatus(event.status);
        if (event.backend) setBackend(event.backend);
        return;
      }
      setEvents((previous) => [...previous, event]);
    });
  }, [taskId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [events]);

  if (status === null && events.length === 0) return null;

  return (
    <section className="mt-6 rounded border border-line bg-surface p-6">
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Live call</p>
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-accent">
          {status ? STATUS_COPY[status] ?? status : "-"}
          {backend ? ` · ${backend}` : ""}
        </p>
      </div>

      <div ref={scrollRef} className="max-h-96 space-y-3 overflow-y-auto pr-1">
        {events.map((event, index) => (
          <FeedItem key={index} event={event} />
        ))}
      </div>
    </section>
  );
}

function FeedItem({ event }: { event: LiveEvent }) {
  switch (event.type) {
    case "turn":
      return (
        <div className={event.speaker === "orion" ? "text-right" : ""}>
          <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
            {event.speaker === "orion" ? "Orion" : "Representative"}
          </p>
          <p className="text-sm leading-relaxed">{event.text}</p>
        </div>
      );

    case "offer":
      return (
        <p className="border-l-2 border-accent pl-3 text-sm text-muted">
          Offer logged
          {event.monthly_rate != null ? `: $${event.monthly_rate}/mo` : ""}
          {event.description ? ` - ${event.description}` : ""}
          {event.accepted ? " (accepted)" : ""}
        </p>
      );

    case "confirmation":
      return (
        <p className="border-l-2 border-pass pl-3 text-sm text-pass">
          Confirmation {event.confirmation_number ?? "-"}
          {event.new_rate != null ? ` at $${event.new_rate}/mo` : ""}
        </p>
      );

    case "stance": {
      // The read of the room. This isn't decoration - the same reading is
      // pushed into the agent's context, so it changes what it says next.
      const tone =
        event.stance === "conceding" || event.stance === "softening"
          ? "border-pass text-pass"
          : event.stance === "hostile" || event.stance === "refusing"
            ? "border-fail text-fail"
            : "border-partial text-partial";
      return (
        <p className={`border-l-2 pl-3 text-sm ${tone}`}>
          Rep is <span className="font-medium">{event.stance}</span>
          {!event.has_authority && " (no discount authority)"} - {event.advice}
        </p>
      );
    }

    case "escalation_sent":
      return (
        <p className="border-l-2 border-accent pl-3 text-sm text-accent">
          You were notified over {event.channels.join(" and ")}.
        </p>
      );

    case "escalation":
      return (
        <p className="border-l-2 border-fail pl-3 text-sm text-fail">
          Escalated to a human{event.reason ? `: ${event.reason}` : ""}
        </p>
      );

    case "verification":
      return (
        <p className={`border-l-2 pl-3 text-sm ${event.verified ? "border-pass text-pass" : "border-fail text-fail"}`}>
          {event.verified ? "Verified from the recording" : "Could not be verified automatically"}
          {event.outcome ? ` - ${event.outcome}` : ""}
        </p>
      );

    case "error":
      return <p className="border-l-2 border-fail pl-3 text-sm text-fail">{event.message}</p>;

    default:
      return null;
  }
}
