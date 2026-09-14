const { ValidationError, AuthError } = require('./errors');

function assertMethod(req, method) {
  if (req.method !== method) {
    const err = new Error(`This endpoint requires an HTTP ${method} request.`);
    err.statusCode = 405;
    throw err;
  }
}

function sendJson(res, statusCode, body) {
  res.status(statusCode).json(body);
}

// Wraps an async endpoint handler: ValidationError -> 400, AuthError -> 401,
// anything else with an explicit statusCode -> that code, all with
// {error: message}; any other thrown error -> 500 with a generic message
// (the real error is still logged server-side).
function wrapHandler(fn) {
  return async (req, res) => {
    try {
      await fn(req, res);
    } catch (err) {
      if (err instanceof ValidationError || err instanceof AuthError || err.statusCode) {
        res.status(err.statusCode || 400).json({ error: err.message });
        return;
      }
      console.error(err);
      res.status(500).json({ error: 'Internal server error.' });
    }
  };
}

module.exports = { assertMethod, sendJson, wrapHandler };
