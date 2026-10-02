import { describe, it, expect } from 'vitest';
import { APIError } from '../utils/api';

describe('API Utilities', () => {
  it('instantiates APIError with code, message, and status', () => {
    const error = new APIError('UNAUTHORIZED', 'Invalid credentials provided', 401);
    expect(error.code).toBe('UNAUTHORIZED');
    expect(error.message).toBe('Invalid credentials provided');
    expect(error.status).toBe(401);
    expect(error.name).toBe('APIError');
  });
});
