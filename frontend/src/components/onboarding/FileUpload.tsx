import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

import { cx } from '../../lib/utils';

interface FileUploadProps {
  file: File | null;
  onFileSelected: (file: File | null) => void;
  disabled?: boolean;
}

const MAX_BYTES = 20 * 1024 * 1024;

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

  return (
    <div>
      <div
        {...getRootProps()}
        className={cx(
          'flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors',
          isDragActive
            ? 'border-indigo-500 bg-indigo-950/30'
            : 'border-slate-700 bg-slate-900/50 hover:border-slate-600',
          disabled && 'cursor-not-allowed opacity-60',
        )}
      >
        <input {...getInputProps()} />

        <span aria-hidden="true" className="mb-3 text-3xl text-slate-600">
          ⇪
        </span>

        {file ? (
          <>
            <p className="text-sm font-medium text-white">{file.name}</p>
            <p className="mt-1 text-xs text-slate-400">
              {(file.size / 1024).toFixed(0)} KB · click to choose a different file
            </p>
          </>
        ) : (
          <>
            <p className="text-sm font-medium text-slate-200">
              {isDragActive ? 'Drop it here' : 'Drag your company PDF here'}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              or click to browse · PDF, TXT or MD · up to 20 MB
            </p>
          </>
        )}
      </div>

      {rejection && (
        <p className="mt-2 text-xs text-red-400">
          {rejection.code === 'file-too-large'
            ? 'That file is larger than 20 MB.'
            : 'That file type is not supported — use a PDF, TXT or MD file.'}
        </p>
      )}
    </div>
  );
}
