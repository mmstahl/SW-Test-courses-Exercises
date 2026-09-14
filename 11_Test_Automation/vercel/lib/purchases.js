function rowToPurchase(row) {
  return {
    purchaseId: row.purchase_id,
    studentEmail: row.student_email,
    seq: row.purchase_seq,
    Model: row.model,
    Storage: row.storage,
    Color: row.color,
    Network: row.network,
    Accessory: row.accessory,
    basePrice: Number(row.base_price),
    discountCodeUsed: row.discount_code_used,
    paidPrice: Number(row.paid_price),
    creditApplied: Number(row.credit_applied),
    requestedPayment: Number(row.requested_payment),
    codeGenerated: row.code_generated,
    status: row.status,
    createdAt: row.created_at,
  };
}

// One read of this student's purchase history, ordered oldest-first so
// that findMatchInPurchases naturally returns the OLDEST matching
// still-Bought purchase (requirements §6.4's "N identical phones" rule) —
// mirrors getPurchasesForEmail_ being read once and reused for both the
// sequence number and the match/eligibility checks.
async function getPurchasesForEmail(executor, email) {
  const result = await executor.query(
    'SELECT * FROM purchases WHERE student_email = $1 ORDER BY purchase_seq ASC',
    [email]
  );
  return result.rows.map(rowToPurchase);
}

function findMatchInPurchases(purchases, config) {
  for (const p of purchases) {
    if (
      p.status === 'Bought' &&
      p.Model === (config.Model || '') &&
      p.Storage === (config.Storage || '') &&
      p.Color === (config.Color || '') &&
      p.Network === (config.Network || '') &&
      p.Accessory === (config.Accessory || '')
    ) {
      return p;
    }
  }
  return null;
}

async function insertPurchase(executor, data) {
  const result = await executor.query(
    `INSERT INTO purchases (
       student_email, purchase_seq, model, storage, color, network, accessory,
       base_price, discount_code_used, paid_price, credit_applied, requested_payment,
       code_generated, status
     ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,'Bought')
     RETURNING purchase_id`,
    [
      data.email,
      data.seq,
      data.config.Model,
      data.config.Storage,
      data.config.Color,
      data.config.Network,
      data.config.Accessory,
      data.basePrice,
      data.discountCodeUsed,
      data.paidPrice,
      data.creditApplied,
      data.requestedPayment,
      data.codeGenerated,
    ]
  );
  return result.rows[0].purchase_id;
}

async function markPurchaseReturned(executor, purchaseId) {
  await executor.query(`UPDATE purchases SET status = 'Returned' WHERE purchase_id = $1`, [
    purchaseId,
  ]);
}

// Mirrors computeReturnEnabledFromPurchases_ exactly.
function computeReturnEnabledFromPurchases(purchases, settings) {
  if (settings.level < 4) return false;
  if (purchases.length === 0) return false;
  if (settings.bugs.returnStaysAvailableWhenEmpty) return true;
  return purchases.some((p) => p.status === 'Bought');
}

module.exports = {
  getPurchasesForEmail,
  findMatchInPurchases,
  insertPurchase,
  markPurchaseReturned,
  computeReturnEnabledFromPurchases,
};
