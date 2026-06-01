# Evy-CLI

A little shelf of command-line tools I make for Jason.

Each tool lives in its own subfolder as a small, copyable project with an AI-agent-friendly README: hand the README to another agent and it should understand how to install, configure, verify, and use the tool without needing a tour guide.

## Tools

| Tool | Purpose | Path |
| --- | --- | --- |
| Pastes.io CLI | Create, read, list, and delete Pastes.io pastebin entries from the terminal. | `pastes/` |
| Evy Mail CLI | Send email through Resend with a mandatory approved-recipient whitelist. | `evy-mail/` |

## Repository convention

Every CLI project should include:

- A standalone executable or installable package.
- A `README.md` written for copy/paste into another AI agent.
- Setup instructions.
- Required environment variables and secret-handling notes.
- Common commands.
- Verification steps.
- Known pitfalls.

## For future Evy

When we create a new CLI tool:

1. Add a new subfolder at the repo root.
2. Include its source, README, and any packaging files.
3. Keep secrets out of Git.
4. Verify the CLI locally before committing.
5. Update this main README's tool table.

I am, after all, a librarian. The tools should have labels.
