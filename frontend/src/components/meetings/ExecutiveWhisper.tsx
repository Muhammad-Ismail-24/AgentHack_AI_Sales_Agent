import { useCallback, useEffect, useState } from 'react';

import {
  buildWhisper,
  buildWhisperAudio,
  describeError,
  getWhisper,
  resolveMediaUrl,
} from '../../lib/api';
import type { Whisper } from '../../lib/types';
import Badge from '../ui/Badge';
import Button from '../ui/Button';

interface ExecutiveWhisperProps {
  meetingId: string;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}

/**
 * The Executive Whisperer: the thirty seconds before the call, as a script.
 *
 * Not a summary of the deal — a verbatim opening line, the objections the
 * prospect will raise with the rebuttal for each, and the points to land.
 * The same payload is what the T-30min WhatsApp reminder sends, and what the
 * drive-time voice note is read from.
 */
export default function ExecutiveWhisper({
  meetingId,
  onError,
  onNotice,
}: ExecutiveWhisperProps) {
  const [whisper, setWhisper] = useState<Whisper | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [isBuilding, setIsBuilding] = useState(false);
  const [isRendering, setIsRendering] = useState(false);

  const fetchWhisper = useCallback(async () => {
    try {
      const existing = await getWhisper(meetingId);
      setWhisper(existing);
      if (existing?.audio_url) setAudioUrl(resolveMediaUrl(existing.audio_url));
    } catch (err) {
      onError(describeError(err));
    }
  }, [meetingId, onError]);

  useEffect(() => {
    void fetchWhisper();
  }, [fetchWhisper]);

  async function handleBuild() {
    setIsBuilding(true);
    try {
      setWhisper(await buildWhisper(meetingId));
      setIsOpen(true);
    } catch (err) {
      onError(describeError(err));
    } finally {
      setIsBuilding(false);
    }
  }

  async function handleAudio() {
    setIsRendering(true);
    try {
      const result = await buildWhisperAudio(meetingId);
      // A null audio_url is the documented no-TTS-key outcome, not a failure —
      // the text script is unaffected, so it gets a notice rather than an error.
      if (result.audio_url) {
        setAudioUrl(resolveMediaUrl(result.audio_url));
        onNotice(
          result.whatsapp_sent
            ? 'Audio briefing rendered and sent to WhatsApp.'
            : 'Audio briefing rendered.',
        );
      } else {
        onNotice(result.message ?? 'No audio was generated.');
      }
    } catch (err) {
      onError(describeError(err));
    } finally {
      setIsRendering(false);
    }
  }

  return (
    <div className="mt-3 border-t border-slate-700 pt-3">
      <div className="flex flex-wrap items-center gap-2">
        <span aria-hidden="true">🎤</span>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Executive whisper
        </h4>

        {whisper ? (
          <button
            type="button"
            onClick={() => setIsOpen((open) => !open)}
            aria-expanded={isOpen}
            className="text-xs font-medium text-indigo-400 hover:text-indigo-300"
          >
            {isOpen ? 'Hide script' : 'Show script'}
          </button>
        ) : (
          <span className="text-xs italic text-slate-500">Not written yet</span>
        )}

        <div className="ml-auto flex gap-2">
          <Button size="sm" variant="ghost" onClick={handleBuild} loading={isBuilding}>
            {whisper ? 'Rewrite' : 'Write script'}
          </Button>
          {whisper && (
            <Button
              size="sm"
              variant="secondary"
              onClick={handleAudio}
              loading={isRendering}
              title="Render a 60-second voice note and send it to WhatsApp"
            >
              🎧 Drive-time audio
            </Button>
          )}
        </div>
      </div>

      {audioUrl && (
        <audio controls src={audioUrl} className="mt-3 w-full">
          Your browser does not support audio playback.
        </audio>
      )}

      {whisper && isOpen && (
        <div className="mt-3 animate-fade-in space-y-4 rounded-lg border border-slate-700 bg-slate-900/60 p-4">
          {whisper.opening_line && (
            <div className="rounded-lg border border-indigo-500/40 bg-indigo-950/40 p-3">
              <h5 className="text-xs font-semibold uppercase tracking-wide text-indigo-400">
                Open with this, word for word
              </h5>
              <p className="mt-1.5 text-sm font-medium italic leading-relaxed text-indigo-100">
                &ldquo;{whisper.opening_line}&rdquo;
              </p>
            </div>
          )}

          {whisper.customer_problem && (
            <div>
              <h5 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Their problem
              </h5>
              <p className="mt-1 text-sm leading-relaxed text-slate-300">
                {whisper.customer_problem}
              </p>
              {whisper.evidence && (
                <p className="mt-1 border-l-2 border-slate-700 pl-2 text-xs italic text-slate-500">
                  {whisper.evidence}
                </p>
              )}
            </div>
          )}

          {whisper.recommended_service && (
            <div>
              <h5 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                You are pitching
              </h5>
              <p className="mt-1 text-sm text-indigo-300">
                {whisper.recommended_service}
              </p>
            </div>
          )}

          {whisper.objections.length > 0 && (
            <div>
              <h5 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                They will push back
              </h5>
              <ul className="mt-1.5 space-y-2.5">
                {whisper.objections.map((item) => (
                  <li
                    key={item.objection}
                    className="rounded-lg border border-slate-700 bg-slate-800/60 p-3"
                  >
                    <p className="text-sm text-yellow-200">
                      <Badge label="They say" color="yellow" className="mr-2" />
                      {item.objection}
                    </p>
                    <p className="mt-2 text-sm text-green-200">
                      <Badge label="You say" color="green" className="mr-2" />
                      {item.rebuttal}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {whisper.key_points.length > 0 && (
            <div>
              <h5 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Points to land
              </h5>
              <ul className="mt-1.5 space-y-1.5">
                {whisper.key_points.map((point) => (
                  <li
                    key={point}
                    className="flex gap-2 text-sm leading-relaxed text-slate-300"
                  >
                    <span aria-hidden="true" className="text-green-500">
                      ✓
                    </span>
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {whisper.watch_out_for.length > 0 && (
            <div>
              <h5 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Watch out for
              </h5>
              <ul className="mt-1.5 space-y-1.5">
                {whisper.watch_out_for.map((point) => (
                  <li
                    key={point}
                    className="flex gap-2 text-sm leading-relaxed text-slate-300"
                  >
                    <span aria-hidden="true" className="text-yellow-500">
                      !
                    </span>
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
