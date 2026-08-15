# Bounded test-first protocol

Use this protocol when an automated test can observe the requested behavior at a stable seam.

1. Confirm the baseline and choose the narrowest meaningful behavior boundary.
2. Add or adjust a test that fails for the intended reason.
3. Run it and read the failure; a syntax error or unrelated failure is not a valid red state.
4. Write the minimum production change.
5. Run the focused test until green.
6. Perform at most one local refactor that preserves behavior.
7. Run related checks and the risk-proportional broader suite.
8. Review that the test proves behavior rather than implementation trivia.

Do not weaken assertions, mock the unit under test, hide unrelated baseline failures, or force this ritual where no suitable harness exists. For migrations, performance, and UI, pair tests with data/query/render evidence appropriate to the boundary.
