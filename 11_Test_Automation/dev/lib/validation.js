const { PARAMETERS } = require('./priceTable');
const { ValidationError } = require('./errors');

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function normalizeParam(v) {
  return v === undefined || v === null ? '' : String(v).trim();
}

// params keys are lowercase (model, storage, ...) as submitted by the
// client/API; config keys are the PRICE_TABLE's capitalized names.
function readConfig(params) {
  return {
    Model: normalizeParam(params.model),
    Storage: normalizeParam(params.storage),
    Color: normalizeParam(params.color),
    Network: normalizeParam(params.network),
    Accessory: normalizeParam(params.accessory),
  };
}

function configToLogString(config) {
  return PARAMETERS.map((p) => config[p]).join('|');
}

function validateEmail(emailRaw, settings) {
  const email = (emailRaw || '').toString().trim();
  if (!email || !EMAIL_RE.test(email)) {
    throw new ValidationError('A valid email address is required.');
  }
  if (settings.requiredEmailDomain) {
    const domain = settings.requiredEmailDomain.replace(/^@/, '').toLowerCase();
    if (!email.toLowerCase().endsWith('@' + domain)) {
      throw new ValidationError('Email must end with @' + domain);
    }
  }
  return email;
}

module.exports = { EMAIL_RE, normalizeParam, readConfig, configToLogString, validateEmail };
