# Evy Mail CLI

Give this README to your AI agent. It explains how to install and use this CLI to send email safely through Resend with an approved-recipient whitelist.

## What this is

`evy-mail` is a small command-line email sender for AI-agent workflows.

It uses the Resend API and is designed to prevent accidental outbound email by requiring a local approved-recipient whitelist before any message can be sent.

It can:

- Store non-secret sender configuration.
- Use any Resend API key environment variable.
- Approve and remove recipient addresses.
- Send plain text or HTML email.
- Send body content from strings, files, or stdin.
- Dry-run a message without sending.

## Requirements

- Linux/macOS/WSL shell
- Python 3.9+
- `curl`
- A Resend API key
- A verified Resend sending domain or sender identity

Resend API docs:

https://resend.com/docs/api-reference/emails/send-email

## Install

From this project folder:

```bash
mkdir -p ~/.local/bin
cp src/evy-mail ~/.local/bin/evy-mail
chmod +x ~/.local/bin/evy-mail
```

Make sure `~/.local/bin` is on PATH:

```bash
case ":$PATH:" in
  *:$HOME/.local/bin:*) echo "~/.local/bin already on PATH" ;;
  *) echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc ;;
esac
```

For the current shell only:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Configure

Put your Resend API key in the environment:

```bash
export RESEND_API_KEY="re_your_key_here"
```

For Hermes/Evy-style setups, store it in `~/.hermes/.env`:

```bash
mkdir -p ~/.hermes
chmod 700 ~/.hermes
printf '\nRESEND_API_KEY=%s\n' "re_your_key_here" >> ~/.hermes/.env
chmod 600 ~/.hermes/.env
```

Do not commit `.env` files or API keys.

Initialize local config:

```bash
evy-mail init \
  --from "Evy <evy@evysnook.com>" \
  --api-key-env RESEND_API_KEY
```

This creates:

```text
~/.hermes/evy-mail/config.json
~/.hermes/evy-mail/recipients.json
```

The config file stores only non-secret settings. The API key stays in the environment or `~/.hermes/.env`.

## Verify installation

```bash
python3 -m py_compile ~/.local/bin/evy-mail
evy-mail --help
evy-mail config
evy-mail whitelist list
```

## Recipient whitelist

The CLI refuses to send unless every recipient is approved first.

List approved recipients:

```bash
evy-mail whitelist list
```

Approve a recipient:

```bash
evy-mail whitelist add person@example.com --label "Person / reason"
```

Remove a recipient:

```bash
evy-mail whitelist remove person@example.com
```

The whitelist is stored at:

```text
~/.hermes/evy-mail/recipients.json
```

## Usage

Dry-run a message:

```bash
evy-mail send \
  --to person@example.com \
  --subject "Hello" \
  --text "Hello from Evy" \
  --dry-run
```

Send plain text:

```bash
evy-mail send \
  --to person@example.com \
  --subject "Hello" \
  --text "Hello from Evy"
```

Send from a text file:

```bash
evy-mail send \
  --to person@example.com \
  --subject "Update" \
  --text-file /path/to/message.txt
```

Send HTML:

```bash
evy-mail send \
  --to person@example.com \
  --subject "Update" \
  --html-file /path/to/message.html
```

Pipe body from stdin:

```bash
printf 'Hello from Evy\n' | evy-mail send \
  --to person@example.com \
  --subject "Hello"
```

Multiple recipients:

```bash
evy-mail send \
  --to first@example.com \
  --to second@example.com \
  --subject "Team update" \
  --text-file update.txt
```

CC/BCC are supported and must also be whitelisted:

```bash
evy-mail send \
  --to person@example.com \
  --cc other@example.com \
  --subject "FYI" \
  --text "Message"
```

## Use another sending domain/key

Set a different sender and API-key environment variable:

```bash
evy-mail config \
  --set-from "Sender <sender@example.com>" \
  --set-api-key-env OTHER_RESEND_API_KEY
```

Then provide that key:

```bash
export OTHER_RESEND_API_KEY="re_other_key_here"
```

## AI-agent operating notes

When a human asks you to send an email:

1. Identify the exact recipient email address.
2. Check the whitelist:
   ```bash
   evy-mail whitelist list
   ```
3. If the recipient is not whitelisted, do not send. Ask for approval, or if the human explicitly approved that exact email in the current task, add it:
   ```bash
   evy-mail whitelist add person@example.com --label "Approved by human"
   ```
4. Draft the subject and body.
5. Use `--dry-run` first for complex, sensitive, or external-facing mail.
6. Send only after all recipients are whitelisted.
7. Report the returned Resend `id` if successful.

Example safe flow:

```bash
evy-mail whitelist list
evy-mail whitelist add person@example.com --label "Approved by Jason"
evy-mail send --to person@example.com --subject "Hello" --text "Hello from Evy" --dry-run
evy-mail send --to person@example.com --subject "Hello" --text "Hello from Evy"
```

## Known pitfalls

- Never commit `RESEND_API_KEY`, `.env`, or generated local config containing private recipient metadata unless the human asks.
- This CLI enforces whitelist checks for `to`, `cc`, and `bcc`.
- Resend may reject a sender if the domain is not verified or if the email local part is not accepted.
- Jason requested `Evy <evy@evysnook.com>` as the default sender. If Resend rejects it, ask before changing it.
- Sending is a real external side effect. Dry-run first unless the task is routine and the recipient is already approved.

## Files

```text
src/evy-mail  executable Python CLI
README.md     AI-agent installation and usage instructions
```
