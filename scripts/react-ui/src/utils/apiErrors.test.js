import { describe, expect, it } from 'vitest';
import { formatApiError } from './apiErrors';

describe('formatApiError', () => {
    it('turns FastAPI validation details into render-safe text', () => {
        const error = {
            response: {
                data: {
                    detail: [
                        {
                            loc: ['body', 'api_url'],
                            msg: 'String should have at least 1 character',
                            input: 'must-not-be-rendered',
                        },
                        {
                            loc: ['body', 'selected_model'],
                            msg: 'String should have at least 1 character',
                        },
                    ],
                },
            },
        };

        const message = formatApiError(error);

        expect(message).toBe(
            'api_url: String should have at least 1 character; '
            + 'selected_model: String should have at least 1 character',
        );
        expect(message).not.toContain('must-not-be-rendered');
    });

    it('uses a structured message without stringifying the whole object', () => {
        expect(formatApiError({ response: { data: { detail: { message: 'Conflict' } } } }))
            .toBe('Conflict');
    });
});
