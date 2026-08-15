import type { Classification } from '../../lib/types';
import { classificationToColor } from '../../lib/utils';
import Badge from '../ui/Badge';

interface ClassificationBadgeProps {
  classification: Classification | string | null;
}

export default function ClassificationBadge({
  classification,
}: ClassificationBadgeProps) {
  return (
    <Badge
      label={classification ?? 'Unclassified'}
      color={classificationToColor(classification)}
    />
  );
}
