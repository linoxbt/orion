/** The sound a phone makes while the far end is ringing.
 *
 * Synthesised rather than shipped as an audio file: it is two sine waves and a
 * cadence, so a file would be dead weight and one more thing to fail to load.
 *
 * North American ringback is 440 Hz + 480 Hz, two seconds on and four off.
 * That cadence is the recognisable part - a single continuous tone reads as a
 * fault tone, not as ringing.
 */
const RING_HZ = [440, 480];
const ON_SECONDS = 2;
const CYCLE_SECONDS = 6;

export class Ringback {
  private ctx: AudioContext | null = null;
  private oscillators: OscillatorNode[] = [];
  private gain: GainNode | null = null;
  private stopped = false;

  async start(): Promise<void> {
    if (this.ctx) return;
    this.stopped = false;

    const Ctor =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return;

    const ctx = new Ctor();
    this.ctx = ctx;
    // Autoplay policy: a context created outside a gesture starts suspended.
    // Placing a call is a click, so this normally succeeds.
    if (ctx.state === "suspended") {
      try {
        await ctx.resume();
      } catch {
        return;
      }
    }
    if (this.stopped) {
      void this.stop();
      return;
    }

    const gain = ctx.createGain();
    // Quiet enough to talk over. A ringback at full scale is startling.
    gain.gain.value = 0;
    gain.connect(ctx.destination);
    this.gain = gain;

    for (const hz of RING_HZ) {
      const osc = ctx.createOscillator();
      osc.type = "sine";
      osc.frequency.value = hz;
      osc.connect(gain);
      osc.start();
      this.oscillators.push(osc);
    }

    this.scheduleCadence(ctx.currentTime);
  }

  /** Schedule enough cycles that it keeps ringing without a timer. */
  private scheduleCadence(from: number): void {
    const gain = this.gain;
    if (!gain) return;
    // A minute of ringing is longer than any call waits before giving up.
    for (let i = 0; i < 10; i += 1) {
      const at = from + i * CYCLE_SECONDS;
      // Ramps rather than steps: an instant gain change clicks audibly.
      gain.gain.setValueAtTime(0, at);
      gain.gain.linearRampToValueAtTime(0.08, at + 0.04);
      gain.gain.setValueAtTime(0.08, at + ON_SECONDS - 0.04);
      gain.gain.linearRampToValueAtTime(0, at + ON_SECONDS);
    }
  }

  async stop(): Promise<void> {
    this.stopped = true;
    for (const osc of this.oscillators) {
      try {
        osc.stop();
        osc.disconnect();
      } catch {
        /* already stopped */
      }
    }
    this.oscillators = [];
    this.gain?.disconnect();
    this.gain = null;
    const ctx = this.ctx;
    this.ctx = null;
    if (ctx) {
      try {
        await ctx.close();
      } catch {
        /* already closed */
      }
    }
  }
}
