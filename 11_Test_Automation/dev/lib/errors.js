// Typed errors mapped to HTTP status codes by lib/http.js's wrapHandler.
class ValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = 'ValidationError';
    this.statusCode = 400;
  }
}

class AuthError extends Error {
  constructor(message) {
    super(message || 'You are not authorized to perform this action.');
    this.name = 'AuthError';
    this.statusCode = 401;
  }
}

module.exports = { ValidationError, AuthError };
