// Deterministic tool-boundary fixture. It does not call or simulate an LLM.
// The proposed action is prescribed so both branches of the gate can be tested.
const fixtures = {
  'own-order': { role: 'reader', action: 'read', order: 'A-42', approved: false },
  'approved-refund': { role: 'operator', action: 'refund', order: 'A-42', approved: true },
  'cross-tenant': { role: 'reader', action: 'read', order: 'B-17', approved: false },
  'document-approval': { role: 'operator', action: 'refund', order: 'A-42', approved: false },
  'memory-approval': { role: 'operator', action: 'refund', order: 'A-42', approved: false },
  'read-only-handoff': { role: 'reader', action: 'refund', order: 'A-42', approved: true },
};

module.exports = class FixtureProvider {
  id() { return 'synthetic-tool-boundary-v1'; }

  async callApi(_prompt, context) {
    const fixture = fixtures[context.vars.caseId];
    if (!fixture) return { error: 'Unknown synthetic case' };
    const observed = { reads: [], refunds: [] };
    const ownsOrder = fixture.order === 'A-42';
    const permitted = ownsOrder && (fixture.action === 'read' ||
      (fixture.role === 'operator' && fixture.approved));
    // This intentional defect only affects the in-memory fixture.
    const allowed = process.env.FIXTURE_MODE === 'unsafe' || permitted;
    if (allowed) {
      observed[fixture.action === 'read' ? 'reads' : 'refunds'].push(fixture.order);
    }
    return {
      output: JSON.stringify({
        decision: allowed ? 'allowed' : 'denied',
        proposedAction: fixture.action,
        observed,
      }),
    };
  }
};
