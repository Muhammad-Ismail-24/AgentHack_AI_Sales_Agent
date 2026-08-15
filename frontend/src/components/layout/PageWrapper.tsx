import type { ReactNode } from 'react';

import { cx } from '../../lib/utils';

interface PageWrapperProps {
  children: ReactNode;
  /** Kanban needs the full width; everything else gets the readable column. */
  wide?: boolean;
  className?: string;
}

export default function PageWrapper({
  children,
  wide = false,
  className,
}: PageWrapperProps) {
  return (
    <main
      className={cx(
        'mx-auto w-full px-8 py-8',
        wide ? 'max-w-none' : 'max-w-7xl',
        className,
      )}
    >
      {children}
    </main>
  );
}
