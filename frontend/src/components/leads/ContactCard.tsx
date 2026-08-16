import type { Contact } from '../../lib/types';
import { initials } from '../../lib/utils';
import Badge from '../ui/Badge';

interface ContactCardProps {
  contact: Contact;
}

export default function ContactCard({ contact }: ContactCardProps) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-bark-700 bg-bark-900/60 p-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-terra-600/20 text-xs font-semibold text-terra-300">
        {initials(contact.name)}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate text-sm font-medium text-white">
            {contact.name ?? 'Unknown contact'}
          </p>
          {contact.is_primary && <Badge label="Primary" color="terra" />}
        </div>

        {contact.role && (
          <p className="truncate text-xs text-bark-400">{contact.role}</p>
        )}

        {contact.email && (
          <a
            href={`mailto:${contact.email}`}
            className="mt-1 block truncate text-xs text-terra-400 hover:text-terra-300 hover:underline"
          >
            {contact.email}
          </a>
        )}

        {contact.linkedin_url && (
          <a
            href={contact.linkedin_url}
            target="_blank"
            rel="noreferrer noopener"
            className="mt-0.5 inline-block text-xs text-bark-400 hover:text-bark-200 hover:underline"
          >
            LinkedIn ↗
          </a>
        )}
      </div>
    </div>
  );
}
