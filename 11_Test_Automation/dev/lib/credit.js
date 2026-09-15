async function getStoreCredit(executor, email) {
  const result = await executor.query(
    'SELECT balance FROM store_credit WHERE student_email = $1',
    [email]
  );
  return result.rows.length ? Number(result.rows[0].balance) : 0;
}

async function setStoreCredit(executor, email, balance) {
  await executor.query(
    `INSERT INTO store_credit (student_email, balance) VALUES ($1, $2)
     ON CONFLICT (student_email) DO UPDATE SET balance = EXCLUDED.balance`,
    [email, balance]
  );
}

module.exports = { getStoreCredit, setStoreCredit };
