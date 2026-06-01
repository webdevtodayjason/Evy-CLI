# Pastes.io CLI

Give this README to your AI agent. It explains how to install and use this CLI to share text, code, markdown, logs, and other snippets through Pastes.io.

## What this is

`pastes` is a tiny Pastes.io command-line client.

It can:

- Create a paste from a string, file, or stdin.
- Read paste metadata and content as JSON.
- Print raw paste content.
- List/search the authenticated account's pastes.
- Delete an owned paste.

It was built for agent workflows where a human says things like:

- "Paste this file and give me the URL."
- "Share this traceback."
- "Turn this markdown draft into a paste."

## Requirements

- Linux/macOS/WSL shell
- Python 3.9+
- `curl`
- A Pastes.io Pro API key

Pastes.io API docs:

https://docs.pastes.io/

## Install

From this project folder:

```bash
mkdir -p ~/.local/bin
cp src/pastes ~/.local/bin/pastes
chmod +x ~/.local/bin/pastes
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

Set your Pastes.io API key in the environment:

```bash
export PASTES_IO_API_KEY="your-api-key-here"
```

For Hermes/Evy-style setups, you can store it in `~/.hermes/.env`:

```bash
mkdir -p ~/.hermes
chmod 700 ~/.hermes
printf '\nPASTES_IO_API_KEY=%s\n' "your-api-key-here" >> ~/.hermes/.env
chmod 600 ~/.hermes/.env
```

The CLI auto-loads `~/.hermes/.env` if the environment variable is not already set.

Do not commit `.env` files or API keys.

## Verify installation

```bash
pastes --help
pastes create --help
python3 -m py_compile ~/.local/bin/pastes
```

Optional live smoke test:

```bash
out=$(pastes create \
  --title "Pastes CLI smoke test" \
  --syntax txt \
  --expire 10M \
  --content "hello from pastes cli")

echo "$out"
slug=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["success"]["slug"])' <<< "$out")
pastes raw "$slug"
```

That paste expires in ten minutes.

## Usage

Create a paste from a string:

```bash
pastes create \
  --title "Example snippet" \
  --syntax txt \
  --expire 1M \
  --content "hello world"
```

Create a paste from a file:

```bash
pastes create \
  --title "README draft" \
  --syntax markdown \
  --expire N \
  --file README.md
```

Create a paste from stdin:

```bash
git diff | pastes create \
  --title "Current git diff" \
  --syntax diff \
  --expire 1D
```

Get paste metadata and content as JSON:

```bash
pastes get <slug>
```

Print raw paste content:

```bash
pastes raw <slug>
```

Read a password-protected paste:

```bash
pastes get <slug> --password "paste-password"
pastes raw <slug> --password "paste-password"
```

List your pastes:

```bash
pastes list
```

Search your pastes:

```bash
pastes list --query keyword
```

Delete an owned paste:

```bash
pastes delete <slug>
```

## Expiration values

Pastes.io documents these `--expire` values:

| Value | Meaning |
| --- | --- |
| `N` | Never expire |
| `1M` | One month |
| `1Y` | One year |
| `1W` | One week |
| `2W` | Two weeks |
| `1D` | One day |
| `1H` | One hour |
| `10M` | Ten minutes |
| `SD` | Self-destruct after read |

Default used by this CLI: `1M`.

For quick tests, use `--expire 10M`.

## Syntax hints

Use whatever syntax Pastes.io supports, for example:

- `txt`
- `markdown`
- `javascript`
- `python`
- `php`
- `diff`
- `json`
- `yaml`

If a syntax is rejected, retry with `txt`.

## AI-agent operating notes

When a human asks you to paste a file:

1. Read the file locally.
2. Choose a sensible title from the filename or task.
3. Choose syntax from the extension; use `markdown` for `.md`, `python` for `.py`, `json` for `.json`, otherwise `txt`.
4. Use `--expire 1D` for transient debugging, `--expire 1M` for normal sharing, and `--expire N` only when the human asks for a durable link.
5. Run `pastes create --title ... --syntax ... --expire ... --file ...`.
6. Return the `paste_url` from the JSON response.
7. Never paste API keys, `.env` files, private tokens, or credentials unless the human explicitly instructs you to do so.

Example agent command:

```bash
pastes create --title "app.py" --syntax python --expire 1D --file app.py
```

The response looks like:

```json
{
  "success": {
    "messages": "Paste successfully created",
    "slug": "exampleSlug",
    "paste_url": "https://pastes.io/exampleSlug"
  }
}
```

Return only the URL unless the human asks for details.

## Known pitfall

Pastes.io is behind Cloudflare. A Python `urllib` implementation was blocked during testing with Cloudflare Error 1010 `browser_signature_banned`. This CLI shells out to `curl` internally because `curl` succeeded reliably.

## Files

```text
src/pastes   executable Python CLI
README.md    AI-agent installation and usage instructions
```
