---
name: financial-calculations
description: Compute money-related figures (VAT / TVA, percentage change, compound interest, loan monthly payments). Use for any finance or price calculation question.
---
# Financial calculations

Follow these steps for every money-related question:

1. Identify the quantity asked (price incl./excl. VAT, growth, final capital, monthly payment...).
2. Open `references/formulas.md` with `read_skill_file` and pick the matching formula.
   Do not rely on memory for formulas.
3. Write the expression with the user's numbers substituted, then evaluate it with the
   `calculate` tool. Never compute in your head, even for simple operations.
   Percentages are decimals in formulas (20 % -> 0.20). Monthly rate = annual rate / 12.
4. Report in your notes:
   - the formula used (in words),
   - the numeric expression you evaluated,
   - the result rounded to 2 decimals, with its unit (€, %, months...).
5. If a required input is missing (rate, duration...), say which one and assume nothing.
