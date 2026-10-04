# legacy-settlement runtime exception (EA-003 source)

**Approved exception:** legacy-settlement remains on Java 17 until retirement
milestone M-2027-01. Do not upgrade this repository's `maven.compiler.release`
before that milestone. This exception takes precedence over the enterprise
Java 25 runtime policy within the legacy-settlement scope.

Background (approved public summary): the settlement ledger client is not yet
certified on newer runtimes; certification is scheduled alongside the
M-2027-01 retirement. Detailed root-cause records are restricted to the
incident review group and are not part of this document.
