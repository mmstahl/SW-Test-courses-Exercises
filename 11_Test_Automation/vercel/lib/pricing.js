const { PRICE_TABLE, PARAMETERS } = require('./priceTable');

function round2(x) {
  return Math.round((Number(x) || 0) * 100) / 100;
}

// Base price = sum of the price of each parameter that currently has a
// value; any parameter left unselected contributes 0 (requirements §6.2).
function computeBasePrice(config) {
  let total = 0;
  PARAMETERS.forEach((p) => {
    const val = config[p];
    if (val && Object.prototype.hasOwnProperty.call(PRICE_TABLE[p], val)) {
      total += PRICE_TABLE[p][val];
    }
  });
  return round2(total);
}

module.exports = { round2, computeBasePrice };
