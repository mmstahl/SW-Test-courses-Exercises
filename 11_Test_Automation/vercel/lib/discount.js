const { DISCOUNT_CODE_LENGTH, EMAIL_PREFIX_LENGTH, PAD_CHAR } = require('./priceTable');

async function findDiscountCode(executor, email, code) {
  const result = await executor.query(
    'SELECT status FROM discount_codes WHERE student_email = $1 AND code = $2',
    [email, code]
  );
  return result.rows.length ? { status: result.rows[0].status } : null;
}

// Mirrors evaluateDiscount_ in the GAS version exactly.
async function evaluateDiscount(executor, email, codeRaw, settings) {
  const code = (codeRaw || '').toString().trim();
  if (settings.level < 2 || !code) {
    return { entered: code, valid: false, message: null };
  }
  if (code.length !== DISCOUNT_CODE_LENGTH) {
    return { entered: code, valid: false, message: 'Unknown code' };
  }
  const mode = settings.bugs.discountCodeMode;
  if (mode === 'acceptNone') {
    return { entered: code, valid: false, message: 'Unknown code' };
  }
  if (mode === 'acceptAny') {
    return { entered: code, valid: true, message: null };
  }
  const row = await findDiscountCode(executor, email, code);
  if (!row) {
    return { entered: code, valid: false, message: 'Unknown code' };
  }
  if (settings.bugs.allowDiscountCodeReuse) {
    return { entered: code, valid: true, message: null };
  }
  if (row.status === 'Active') {
    return { entered: code, valid: true, message: null };
  }
  if (row.status === 'Redeemed') {
    return { entered: code, valid: false, message: 'This code was already used' };
  }
  if (row.status === 'Disabled') {
    return {
      entered: code,
      valid: false,
      message: 'Invalid code. The phone that got you this code was returned.',
    };
  }
  return { entered: code, valid: false, message: 'Unknown code' };
}

function generateDiscountCode(email, seq) {
  const localPart = email.split('@')[0];
  let prefix = localPart.substring(0, EMAIL_PREFIX_LENGTH);
  while (prefix.length < EMAIL_PREFIX_LENGTH) prefix += PAD_CHAR;
  const seqStr = seq < 10 ? '0' + seq : String(seq);
  return prefix + seqStr;
}

async function insertDiscountCode(executor, code, email, purchaseId) {
  await executor.query(
    `INSERT INTO discount_codes (student_email, code, generated_by_purchase_id, status)
     VALUES ($1, $2, $3, 'Active')`,
    [email, code, purchaseId]
  );
}

// Only marks a row Redeemed if it's currently Active — mirrors
// markCodeRedeemed_, which is a no-op for acceptAny codes (never a real
// row) and for a code already Redeemed/Disabled (shouldn't happen given
// evaluateDiscount already rejected those, but keep the guard).
async function markCodeRedeemed(executor, email, code) {
  await executor.query(
    `UPDATE discount_codes SET status = 'Redeemed'
     WHERE student_email = $1 AND code = $2 AND status = 'Active'`,
    [email, code]
  );
}

async function disableDiscountCode(executor, email, code) {
  await executor.query(
    `UPDATE discount_codes SET status = 'Disabled'
     WHERE student_email = $1 AND code = $2`,
    [email, code]
  );
}

module.exports = {
  findDiscountCode,
  evaluateDiscount,
  generateDiscountCode,
  insertDiscountCode,
  markCodeRedeemed,
  disableDiscountCode,
};
