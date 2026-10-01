# Formulas

| Need | Formula | `calculate` expression example |
|---|---|---|
| Price incl. VAT (TTC) | HT × (1 + rate) | `100 * (1 + 0.20)` |
| Price excl. VAT (HT) | TTC / (1 + rate) | `120 / (1 + 0.20)` |
| VAT amount | HT × rate | `100 * 0.20` |
| Percentage change | (new − old) / old × 100 | `(130 - 100) / 100 * 100` |
| Compound interest (final capital) | C × (1 + r)^n | `1000 * (1 + 0.03) ** 5` |
| Loan monthly payment | P × i / (1 − (1 + i)^−n), i = annual rate / 12, n = months | `200000 * (0.036/12) / (1 - (1 + 0.036/12) ** -240)` |
| Total cost of a loan | monthly payment × n − P | `1170.22 * 240 - 200000` |

Common French VAT rates: 20 % (standard), 10 %, 5.5 %, 2.1 %.
