// Product data — fixed reference values (requirements doc §2). Ported
// verbatim from reference-appsscript-version/Code.js.
const PRICE_TABLE = {
  Model: { 'Pixel 9': 900, 'Pixel 9 Pro': 1050, 'Pixel 9 Pro XL': 1430 },
  Storage: { '128GB': 0, '256GB': 56, '512GB': 98, '1TB': 164 },
  Color: { Black: 0, Red: 100, Silver: 80, Blue: 60 },
  Network: { '5G': 115, '4G': 0 },
  Accessory: { None: 0, Case: 45, Charger: 32, Earbuds: 215 },
};

const PARAMETERS = ['Model', 'Storage', 'Color', 'Network', 'Accessory'];
const DISCOUNT_RATE = 0.15;
const DISCOUNT_CODE_LENGTH = 7;
const EMAIL_PREFIX_LENGTH = 5;
const PAD_CHAR = 'Z';

function getProductOptions() {
  const out = {};
  PARAMETERS.forEach((p) => {
    out[p] = Object.keys(PRICE_TABLE[p]);
  });
  return out;
}

module.exports = {
  PRICE_TABLE,
  PARAMETERS,
  DISCOUNT_RATE,
  DISCOUNT_CODE_LENGTH,
  EMAIL_PREFIX_LENGTH,
  PAD_CHAR,
  getProductOptions,
};
