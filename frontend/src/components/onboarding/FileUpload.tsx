import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

import { cx } from '../../lib/utils';

interface FileUploadProps {
  file: File | null;
  onFileSelected: (file: File | null) => void;
  disabled?: boolean;
}

const MAX_BYTES = 20 * 1024 * 1024;

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export default function FileUpload({
  file,
  onFileSelected,
  disabled = false,
}: FileUploadProps) {
  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted.length > 0) onFileSelected(accepted[0]);
    },
    [onFileSelected],
  );

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    disabled,
    multiple: false,
    maxSize: MAX_BYTES,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
    },
  });

  const rejection = fileRejections[0]?.errors[0];

  // Once a file is chosen the dropzone becomes a summary chip. Picking a
  // different file used to mean clicking the same target again with no way to
  // simply clear the selection — hence the explicit Remove.
  if (file) {
    return (
      <div className="rounded-xl border border-terra-600/40 bg-terra-950/25 p-4">
        <div className="flex items-center gap-3.5">
          <span
            aria-hidden="true"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg
                       bg-gradient-to-br from-terra-400 to-terra-600 text-lg text-white
                       shadow-md shadow-terra-950/50"
          >
            ▤
          </span>

          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-cream" title={file.name}>
              {file.name}
            </p>
            <p className="mt-0.5 text-xs text-bark-400">
              {formatSize(file.size)} · ready to load
            </p>
          </div>

          <div className="flex shrink-0 items-center gap-1">
            <button
              {...getRootProps()}
              type="button"
              disabled={disabled}
              className="rounded-md px-2.5 py-1.5 text-xs font-medium text-bark-300
                         transition-colors hover:bg-bark-800 hover:text-cream
                         disabled:cursor-not-allowed disabled:opacity-50"
            >
              <input {...getInputProps()} />
              Replace
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onFileSelected(null)}
              className="rounded-md px-2.5 py-1.5 text-xs font-medium text-bark-400
                         transition-colors hover:bg-red-950/50 hover:text-red-300
                         disabled:cursor-not-allowed disabled:opacity-50"
            >
              Remove
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div
        {...getRootProps()}
        className={cx(
          'group flex cursor-pointer flex-col items-center justify-center rounded-xl',
          'border-2 border-dashed px-6 py-14 text-center transition-all duration-150',
          isDragActive
            ? 'scale-[1.01] border-terra-400 bg-terra-950/40 shadow-lg shadow-terra-950/40'
            : 'border-bark-700 bg-bark-950/40 hover:border-terra-600/70 hover:bg-bark-900/60',
          disabled && 'cursor-not-allowed opacity-60',
        )}
      >
        <input {...getInputProps()} />

        <span
          aria-hidden="true"
          className={cx(
            'mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border text-2xl transition-colors',
            isDragActive
              ? 'border-terra-400/60 bg-terra-600/25 text-terra-200'
              : 'border-bark-700 bg-bark-900 text-bark-500 group-hover:border-terra-600/50 group-hover:text-terra-300',
          )}
        >
          ⇪
        </span>

        <p className="text-sm font-medium text-bark-100">
          {isDragActive ? 'Drop it here' : 'Drag your company PDF here'}
        </p>
        <p className="mt-1.5 text-xs text-bark-500">
          or <span className="text-terra-300 underline decoration-terra-600/50">click to browse</span>
        </p>
        <p className="mt-3 text-[11px] uppercase tracking-wide text-bark-600">
          PDF · TXT · MD — up to 20 MB
        </p>
      </div>

      {rejection && (
        <p className="mt-2.5 flex items-center gap-1.5 text-xs text-red-300">
          <span aria-hidden="true">⚠</span>
          {rejection.code === 'file-too-large'
            ? 'That file is larger than 20 MB.'
            : 'That file type is not supported — use a PDF, TXT or MD file.'}
        </p>
      )}
    </div>
  );
}
