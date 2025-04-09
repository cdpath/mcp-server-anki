# mcp-anki-server

## prerequsites

- [Anki Desktop](https://apps.ankiweb.net/)
- [Anki Connect](https://ankiweb.net/shared/info/2055492159)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)


## Usage

```bash
git clone https://github.com/cdpath/mcp-server-anki $HOME/Developer/mcp-server-anki
```


### Cursor

update `.mcp.json` to add the following:

```
{
    "mcpServers": {
      "anki": {
        "command": "uv",
        "args": ["--directory", "$HOME/Developer/mcp-server-anki", "run", "server.py"],
        "env": {},
        "disabled": false,
        "autoApprove": []
      }
    }
  }
```

### Chatwise

Go to Settings -> Tools -> Add and use the following config:

```
Type: stdio
ID: Anki
Command: `uv --directory $HOME/Developer/mcp-server-anki run server.py`
```