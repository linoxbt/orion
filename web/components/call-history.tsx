"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Play, Pause, Download } from "lucide-react";
import { listCalls, type CallRecord } from "@/lib/api";

/** Every call on this negotiation, each one playable and downloadable.
 *
 * A negotiation is dialled more than once, and the earlier attempts are often
 * the interesting ones - a line that was busy, a menu that went nowhere. They
 * are all here rather than only the most recent.
 */
export function CallHistory({ taskId }: { taskId: string }) {
  const [calls, setCalls] = useState<CallRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const load = useCallback(async () => {
    try {
      setCalls(await listCalls(taskId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [taskId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggle(call: CallRecord) {
    const audio = audioRef.current;
    if (!audio || !call.url) return;
    const id = call.call_sid ?? call.started_at;

    if (playing === id) {
      audio.pause();
      return;
    }
    audio.src = call.url;
    try {
      await audio.play();
      setPlaying(id);
    } catch {
      // Most likely an expired link: fetch fresh ones rather than leaving a
      // play button that silently does nothing.
      await load();
      setError("That link had expired. Press play again.");
    }
  }

  if (error && !calls) return <p className="mt-4 text-[13px] text-fail">{error}</p>;

  if (!calls) {
    return (
      <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.2em] text-muted">
        Loading calls…
      </p>
    );
  }

  if (calls.length === 0) {
    return (
      <p className="mt-4 text-[14px] leading-relaxed text-ink-soft">
        No calls yet. Every attempt will be listed here, with its recording.
      </p>
    );
  }

  return (
    <div className="mt-5 overflow-hidden rounded border border-line">
      {calls.map((call, i) => {
        const id = call.call_sid ?? call.started_at;
        const isPlaying = playing === id;
        return (
          <div
            key={id}
            className="flex flex-wrap items-center gap-4 border-b border-line p-4 last:border-b-0"
          >
            <button
              type="button"
              onClick={() => toggle(call)}
              disabled={!call.url}
              aria-label={isPlaying ? "Pause" : "Play this call"}
              className="flex h-10 w-10 flex-none items-center justify-center rounded-full bg-accent text-accent-ink transition-colors hover:bg-accent-hover disabled:opacity-30"
            >
              {isPlaying ? <Pause size={15} /> : <Play size={15} className="ml-0.5" />}
            </button>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
                  Attempt {calls.length - i}
                </span>
                <span className="text-[13px] text-ink">
                  {new Date(call.started_at).toLocaleString()}
                </span>
                <Status call={call} />
              </div>
              {call.outcome && (
                <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">{call.outcome}</p>
              )}
            </div>

            <span className="tabular flex-none font-mono text-[12px] text-muted">
              {call.duration_seconds != null ? formatDuration(call.duration_seconds) : "—"}
            </span>

            {call.url && (
              <a
                href={call.url}
                download={call.download_name ?? undefined}
                className="flex h-9 w-9 flex-none items-center justify-center rounded border border-line text-muted transition-colors hover:border-ink hover:text-ink"
                aria-label="Download this recording"
              >
                <Download size={14} />
              </a>
            )}
          </div>
        );
      })}

      {error && <p className="border-t border-line p-4 text-[13px] text-partial">{error}</p>}

      <audio
        ref={audioRef}
        preload="none"
        onPause={() => setPlaying(null)}
        onEnded={() => setPlaying(null)}
      />
    </div>
  );
}

function Status({ call }: { call: CallRecord }) {
  const [label, tone] = !call.answered
    ? [call.end_reason ?? "not answered", "text-muted"]
    : call.end_reason === "completed"
      ? ["answered", "text-pass"]
      : [call.end_reason ?? "ended", "text-partial"];

  return (
    <span className={`font-mono text-[10px] uppercase tracking-[0.16em] ${tone}`}>{label}</span>
  );
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}
