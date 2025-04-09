# mcp-anki-server

## prerequisite

- [Anki Desktop](https://apps.ankiweb.net/)
- [Anki Connect](https://ankiweb.net/shared/info/2055492159)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)


## usage


### cursor

update `.mcp.json` to add the following:

```
{
    "mcpServers": {
      "anki": {
        "command": "uv",
        "args": ["run", "--with", "mcp-server-anki", "mcp-server-anki"],
        "env": {},
        "disabled": false,
        "autoApprove": []
      }
    }
}
```

### chatwise

Go to Settings -> Tools -> Add and use the following config:

```
Type: stdio
ID: Anki
Command: uv run --with mcp-server-anki mcp-server-anki
```
