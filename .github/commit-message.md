Write a commit message based solely on the provided changes.

Format:
<gitmoji> <subject>

- <what changed>
- <why it changed>
- <affected scope or notable side effect>
- <version impact: bump to x.y.z / no version change>
- <breaking change or migration note, if any>

Rules:
- Pick exactly one gitmoji from this list, based on the most significant change:
  - 🚧 Work in progress
  - ⚡️ Performance
  - 🐛 Bug fix
  - ✨ New feature
  - 📝 Documentation
  - ✅ Tests
  - 🔒️ Security
  - ♻️ Refactor
- Subject must be specific and describe the main change. Do not use vague words like "update", "improve", "enhance", or "better".
- Leave one blank line between subject and body.
- Body must use bullet points only.
- Describe what changed and why. Avoid implementation details unless they are essential.
- If multiple changes exist, focus on the most important one and mention secondary changes briefly.
- Include version impact explicitly: state the new version if a bump is required; otherwise write "no version change".
- If the change is breaking, state that explicitly.
- Maximum total length: 250 characters. If space is limited, keep the subject, reason, and version impact first.