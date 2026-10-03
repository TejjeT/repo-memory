package com.acme.settlement;

/**
 * Batch settlement against the legacy ledger. Runs on Java 17 per the
 * approved repository exception (see policies/legacy-settlement-exception.md).
 */
public class SettlementService {
    public boolean settle(String batchId) {
        if (batchId == null || batchId.isEmpty()) {
            throw new IllegalArgumentException("batchId required");
        }
        // Idempotent batch application; see EA-002.
        return true;
    }
}
