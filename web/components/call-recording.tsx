"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Play, Pause } from "lucide-react";
import { getRecording, type CallRecording } from "@/lib/api";

/** Listen back to the call Orion made on your behalf.
 *
 * The link is signed and expires, so it is fetched when the player mounts
 * rather than stored on the negotiation - and refetched if playback fails,
 * which is what an expired link looks like from here.
 */
export function CallRecordingPlayer({ taskId }: { taskId: string }) {
  const [state, setState] = useState<CallRecording | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [duration, setDuration] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const load = useCallback(async () => {
    try {
      setState(await getRecording(taskId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [taskId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggle() {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
      return;
    }
    try {
      await audio.play();
    } catch {
      // Most likely an expired link. Fetch a fresh one and try once more,
      // rather than leaving a play button that silently does nothing.
      await load();
      setError("That link had expired. Press play again.");
    }
  }

  if (error && !state) {
    return <p className="mt-4 text-[13px] text-fail">{error}</p>;
  }

  if (!state) {
    return (
      <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.2em] text-muted">
        Checking for a recording…
      </p>
    );
  }

  if (!state.available) {
    const said =
      state.reason === "no_call_yet"
        ? "Nothing to play yet. A recording appears once Orion has made the call."
        : state.reason === "awaiting_recording"
          ? "The call is finishing. Its recording usually appears within a minute."
          : "That recording could not be loaded.";
    return <p className="mt-4 text-[14px] leading-relaxed text-ink-soft">{said}</p>;
  }

  const pct = duration > 0 ? (elapsed / duration) * 100 : 0;

  return (
    <div className="mt-5 rounded border border-line bg-surface-2 p-5">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={toggle}
          aria-label={playing ? "Pause the recording" : "Play the recording"}
          className="flex h-11 w-11 flex-none items-center justify-center rounded-full bg-accent text-accent-ink transition-colors hover:bg-accent-hover"
        >
          {playing ? <Pause size={17} /> : <Play size={17} className="ml-0.5" />}
        </button>

        <div className="min-w-0 flex-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted">
            The call Orion made
          </p>
          <div
            role="progressbar"
            aria-valuenow={Math.round(elapsed)}
            aria-valuemin={0}
            aria-valuemax={Math.round(duration) || 0}
            aria-label="Playback position"
            className="mt-2.5 h-1 w-full overflow-hidden rounded-full bg-line"
          >
            <div className="h-full rounded-full bg-accent transition-[width]" style={{ width: `${pct}%` }} />
          </div>
        </div>

        <span className="tabular flex-none font-mono text-[12px] text-muted">
          {format(elapsed)}
          {duration > 0 && ` / ${format(duration)}`}
        </span>
      </div>

      {error && <p className="mt-3 text-[13px] text-partial">{error}</p>}

      {/* Not `controls`: the native player exposes a download of a recording of
          somebody's phone call, and the link behind it is meant to expire. */}
      <audio
        ref={audioRef}
        src={state.url ?? undefined}
        preload="metadata"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onTimeUpdate={(e) => setElapsed(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => {
          const d = e.currentTarget.duration;
          if (Number.isFinite(d)) setDuration(d);
        }}
      />
    </div>
  );
}

function format(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
