# legacy-settlement runtime exception (EA-003 source)

**Approved exception:** legacy-settlement remains on Java 17 until retirement
milestone M-2027-01. Do not upgrade this repository's `maven.compiler.release`
before that milestone. This exception takes precedence over the enterprise
Java 25 runtime policy within the legacy-settlement scope.

Background: per incident INC-2024-118 (restricted), the settlement ledger
client exhibits undefined behavior on newer runtimes; the vendor fix is
scheduled alongside the M-2027-01 retirement.
