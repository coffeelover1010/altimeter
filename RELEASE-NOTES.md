# Altimeter 0.3.1

- WoW patches no longer disable measurements when the client build changes. One short chat warning per login/reload explains that terrain data may be outdated; readings continue.
- Refreshed the complete readable terrain dataset from Forever 1.60.1.70938: 3,322 tiles across 48 maps, with no tile extraction failures.
- Includes terrain sampling controls and optional minimap contours from 0.3.0.

Validated offline against all generated terrain tiles, including ocean masks and build-mismatch behavior. Live-client verification of this release is pending. Existing unsupported interiors and unreadable map records remain outside coverage.

Install the full package with all eight addon folders. Existing users can /reload; fully restart WoW if adding missing addon folders.
