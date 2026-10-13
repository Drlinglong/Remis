import { describe, expect, it } from 'vitest';
import { isPublishedFileId, publicationErrorDetail } from './publicationValidation';

describe('publication input and server errors', () => {
  it.each(['0', '-1', ' 123', '', '123456789012345678901', 123, null])('rejects an invalid ID: %s', (value) => {
    expect(isPublishedFileId(value)).toBe(false);
  });
  it('preserves IDs as strings including 20-digit values', () => {
    expect(isPublishedFileId('1')).toBe(true);
    expect(isPublishedFileId('12345678901234567890')).toBe(true);
  });
  it('formats multiple FastAPI fields including nested tag indices', () => {
    expect(publicationErrorDetail({ response: { data: { detail: [
      { loc: ['body', 'title'], msg: 'Too long' }, { loc: ['body', 'tags', 2], msg: 'Invalid tag' },
    ] } } })).toBe('title: Too long; tags.2: Invalid tag');
  });
  it('keeps existing string, structured and network errors', () => {
    expect(publicationErrorDetail({ response: { data: { detail: 'Unavailable' } } })).toBe('Unavailable');
    expect(publicationErrorDetail({ response: { data: { detail: { message: 'Stale plan' } } } })).toBe('Stale plan');
    expect(publicationErrorDetail({ message: 'Network Error' })).toBe('Network Error');
  });
});
