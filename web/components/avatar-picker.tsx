"use client";

import { useRef, useState } from "react";
import { Camera } from "lucide-react";

/** Longest side of the stored image, in pixels. */
const MAX_EDGE = 320;
/** A generous ceiling for the encoded result; a 320px JPEG lands far under it. */
const MAX_BYTES = 120_000;

/**
 * The profile picture: click it and choose a file.
 *
 * It used to be a text field asking for a URL, which meant hosting your own
 * photograph somewhere first. The picture is scaled down to {@link MAX_EDGE}px
 * in the browser and stored inline with the profile, so there is no bucket to
 * configure, no public object to leak, and no link that rots when the host it
 * pointed at goes away.
 */
export function AvatarPicker({
  value,
  initial,
  onChange,
}: {
  value: string;
  initial: string;
  onChange: (dataUrl: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pick(file: File | null) {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("That is not an image.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onChange(await downscale(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "That image could not be read.");
    } finally {
      setBusy(false);
      // Clearing it means picking the same file twice still fires a change.
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => input.current?.click()}
        aria-label={value ? "Change your profile picture" : "Add a profile picture"}
        className="group relative h-20 w-20 flex-none overflow-hidden rounded-full border border-line"
      >
        {value ? (
          // A plain img: the value is a data URL of the person's own picture,
          // which next/image has nothing to optimise and no host to allow.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={value} alt="" className="h-full w-full object-cover" />
        ) : (
          <span className="flex h-full w-full items-center justify-center bg-accent-soft text-[1.6rem] font-medium text-accent">
            {initial}
          </span>
        )}

        <span className="absolute inset-0 flex items-center justify-center bg-black/55 text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
          <Camera size={18} />
        </span>
      </button>

      <input
        ref={input}
        type="file"
        accept="image/*"
        className="sr-only"
        onChange={(e) => pick(e.target.files?.[0] ?? null)}
      />

      <p className="mt-2 text-[12px] text-muted">
        {busy ? "Reading…" : error ? <span className="text-fail">{error}</span> : "Click to change"}
      </p>
    </div>
  );
}

/** Scale to fit MAX_EDGE and re-encode as JPEG. */
async function downscale(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height));
  const width = Math.max(1, Math.round(bitmap.width * scale));
  const height = Math.max(1, Math.round(bitmap.height * scale));

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("This browser cannot resize the image.");
  context.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();

  const dataUrl = canvas.toDataURL("image/jpeg", 0.82);
  if (dataUrl.length > MAX_BYTES) throw new Error("That image is too large to store.");
  return dataUrl;
}
