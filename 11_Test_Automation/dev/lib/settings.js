const { ValidationError } = require('./errors');

const DEFAULT_SETTINGS = {
  level: 1,
  requiredEmailDomain: '',
  studentResetEnabled: false,
  bugs: {
    discountCodeMode: 'normal', // 'normal' | 'acceptAny' | 'acceptNone'
    allowBuyWithPartialConfig: false,
    returnStaysAvailableWhenEmpty: false,
    creditBasis: 'paid', // 'paid' (correct) | 'base' (bug)
    allowDiscountCodeReuse: false,
  },
};

function rowToSettings(row) {
  return {
    level: row.level,
    requiredEmailDomain: row.required_email_domain,
    studentResetEnabled: row.student_reset_enabled,
    bugs: {
      discountCodeMode: row.discount_code_mode,
      allowBuyWithPartialConfig: row.allow_buy_with_partial_config,
      returnStaysAvailableWhenEmpty: row.return_stays_available_when_empty,
      creditBasis: row.credit_basis,
      allowDiscountCodeReuse: row.allow_discount_code_reuse,
    },
  };
}

async function getSettings(executor) {
  const result = await executor.query('SELECT * FROM settings WHERE id = 1');
  if (result.rows.length === 0) {
    // Should never happen — schema.sql seeds the singleton row — but fall
    // back to defaults rather than throw.
    return JSON.parse(JSON.stringify(DEFAULT_SETTINGS));
  }
  return rowToSettings(result.rows[0]);
}

async function saveSettings(executor, settings) {
  await executor.query(
    `UPDATE settings SET
       level = $1,
       required_email_domain = $2,
       student_reset_enabled = $3,
       discount_code_mode = $4,
       allow_buy_with_partial_config = $5,
       return_stays_available_when_empty = $6,
       allow_discount_code_reuse = $7,
       credit_basis = $8,
       updated_at = now()
     WHERE id = 1`,
    [
      settings.level,
      settings.requiredEmailDomain,
      settings.studentResetEnabled,
      settings.bugs.discountCodeMode,
      settings.bugs.allowBuyWithPartialConfig,
      settings.bugs.returnStaysAvailableWhenEmpty,
      settings.bugs.allowDiscountCodeReuse,
      settings.bugs.creditBasis,
    ]
  );
  return settings;
}

// Same merge semantics as the GAS version's mergeSettings_: override.bugs
// merges key-by-key into base.bugs; every other top-level key overrides
// wholesale when present.
function mergeSettings(base, override) {
  const merged = JSON.parse(JSON.stringify(base));
  override = override || {};
  for (const k of Object.keys(override)) {
    if (k === 'bugs' && override.bugs) {
      merged.bugs = Object.assign({}, merged.bugs, override.bugs);
    } else {
      merged[k] = override[k];
    }
  }
  return merged;
}

function validateSettings(settings) {
  settings.level = Number(settings.level);
  if (![1, 2, 3, 4].includes(settings.level)) {
    throw new ValidationError('level must be 1-4.');
  }
  if (!['normal', 'acceptAny', 'acceptNone'].includes(settings.bugs.discountCodeMode)) {
    throw new ValidationError('invalid discountCodeMode');
  }
  if (!['paid', 'base'].includes(settings.bugs.creditBasis)) {
    throw new ValidationError('invalid creditBasis');
  }
  settings.bugs.allowBuyWithPartialConfig = !!settings.bugs.allowBuyWithPartialConfig;
  settings.bugs.returnStaysAvailableWhenEmpty = !!settings.bugs.returnStaysAvailableWhenEmpty;
  settings.bugs.allowDiscountCodeReuse = !!settings.bugs.allowDiscountCodeReuse;
  settings.studentResetEnabled = !!settings.studentResetEnabled;
  settings.requiredEmailDomain = (settings.requiredEmailDomain || '').toString().trim();
  return settings;
}

module.exports = { DEFAULT_SETTINGS, getSettings, saveSettings, mergeSettings, validateSettings };
