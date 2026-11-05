import { createFromSource } from 'fumadocs-core/search/server';
import { source } from '@/lib/source';

// Emitted as a static JSON file by `output: 'export'` (see src/components/search.tsx for the client side).
export const revalidate = false;

export const { staticGET: GET } = createFromSource(source, { language: 'english' });
