import json
from typing import Any, Dict, Optional

import aiohttp
from mcp.server.fastmcp import Context, FastMCP

class AnkiServer:
    def __init__(self, anki_connect_url: str = "http://localhost:8765"):
        self.anki_connect_url = anki_connect_url
        self.mcp = FastMCP(
            "Anki MCP",
            dependencies=["aiohttp>=3.9.0"]
        )
        self._setup_handlers()

    async def anki_request(self, action: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make a request to the AnkiConnect API."""
        if params is None:
            params = {}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.anki_connect_url,
                json={
                    "action": action,
                    "version": 6,
                    "params": params,
                },
            ) as response:
                data = await response.json()
                if data.get("error"):
                    raise Exception(f"AnkiConnect error: {data['error']}")
                return data["result"]

    def _setup_handlers(self):
        """Set up resources and tools for the MCP server."""
        
        @self.mcp.resource("decks://{deck_id}")
        async def get_deck(deck_id: str) -> str:
            """Get information about a specific deck."""
            decks = await self.anki_request("getDeckConfig", {"deck": deck_id})
            return json.dumps(decks)

        @self.mcp.resource("models://{model_id}")
        async def get_model(model_id: str) -> str:
            """Get information about a specific note model."""
            models = await self.anki_request("findModelsById", {"modelIds": [int(model_id)]})
            return json.dumps(models)

        @self.mcp.tool()
        async def list_decks(ctx: Context) -> list[str]:
            """Get the names of all decks from Anki."""
            return await self.anki_request("deckNames")

        @self.mcp.tool()
        async def list_models(ctx: Context) -> Dict[str, int]:
            """Get the names and IDs of all note models from Anki."""
            return await self.anki_request("modelNamesAndIds")

        @self.mcp.tool()
        async def get_model_fields(ctx: Context, model_name: str) -> list[str]:
            """Get field names for a specific note model."""
            return await self.anki_request("modelFieldNames", {"modelName": model_name})

        @self.mcp.tool()
        async def add_note(
            ctx: Context,
            deck_name: str,
            model_name: str,
            fields: Dict[str, str],
            tags: Optional[list[str]] = None
        ) -> int:
            """Create a new note in Anki.
            
            Args:
                deck_name: Name of the deck to add the note to
                model_name: Name of the note model/type to use
                fields: Map of field names to values
                tags: Optional list of tags to apply to the note
            
            Returns:
                The ID of the created note
            """
            note = {
                "deckName": deck_name,
                "modelName": model_name,
                "fields": fields,
                "tags": tags or [],
            }
            return await self.anki_request("addNote", {"note": note})

        @self.mcp.tool()
        async def find_notes(ctx: Context, query: str) -> list[int]:
            """Find notes using Anki's search syntax."""
            return await self.anki_request("findNotes", {"query": query})

        @self.mcp.tool()
        async def update_note_fields(
            ctx: Context,
            note_id: int,
            fields: Dict[str, str]
        ) -> None:
            """Update the fields of an existing note."""
            return await self.anki_request("updateNoteFields", {
                "note": {"id": note_id, "fields": fields}
            })

        @self.mcp.tool()
        async def delete_notes(ctx: Context, note_ids: list[int]) -> None:
            """Delete notes by their IDs."""
            return await self.anki_request("deleteNotes", {"notes": note_ids})

        @self.mcp.tool()
        async def add_tags(
            ctx: Context,
            note_ids: list[int],
            tags: str
        ) -> None:
            """Add tags to notes."""
            return await self.anki_request("addTags", {
                "notes": note_ids,
                "tags": tags
            })

        @self.mcp.tool()
        async def remove_tags(
            ctx: Context,
            note_ids: list[int],
            tags: str
        ) -> None:
            """Remove tags from notes."""
            return await self.anki_request("removeTags", {
                "notes": note_ids,
                "tags": tags
            })

        @self.mcp.tool()
        async def get_card_info(ctx: Context, card_ids: list[int]) -> list[Dict[str, Any]]:
            """Get information about specific cards."""
            return await self.anki_request("cardsInfo", {"cards": card_ids})

        @self.mcp.tool()
        async def get_deck_stats(ctx: Context, deck_name: str) -> Dict[str, Any]:
            """Get statistics about a specific deck."""
            return await self.anki_request("getDeckStats", {"deck": deck_name})

        @self.mcp.tool()
        async def export_deck(
            ctx: Context,
            deck_name: str,
            path: str,
            include_schedule: bool = True
        ) -> bool:
            """Export a deck to an .apkg file."""
            return await self.anki_request("exportPackage", {
                "deck": deck_name,
                "path": path,
                "includeSched": include_schedule
            })

        @self.mcp.tool()
        async def create_deck(ctx: Context, deck_name: str) -> int:
            """Create a new deck."""
            return await self.anki_request("createDeck", {"deck": deck_name})

        @self.mcp.tool()
        async def get_card_review_logs(ctx: Context, card_id: int) -> list[Dict[str, Any]]:
            """Get review history for a specific card."""
            return await self.anki_request("getReviewsOfCard", {"card": card_id})

        @self.mcp.tool()
        async def set_card_due_time(
            ctx: Context,
            card_ids: list[int],
            days_from_now: int
        ) -> bool:
            """Set the due time for cards."""
            return await self.anki_request("setSpecificValueOfCard", {
                "cards": card_ids,
                "keys": ["due"],
                "newValues": [days_from_now]
            })

        @self.mcp.tool()
        async def store_media_file(
            ctx: Context,
            filename: str,
            data: str
        ) -> None:
            """Store a media file in Anki's media folder.
            
            Args:
                filename: The name to save the file as
                data: Base64-encoded file content
            """
            return await self.anki_request("storeMediaFile", {
                "filename": filename,
                "data": data
            })

        @self.mcp.tool()
        async def get_media_file_names(ctx: Context, pattern: str = "") -> list[str]:
            """Get the names of media files in Anki's media folder.
            
            Args:
                pattern: Optional pattern to filter files (e.g., "*.jpg")
            """
            return await self.anki_request("getMediaFilesNames", {"pattern": pattern})

        @self.mcp.tool()
        async def delete_media_file(ctx: Context, filename: str) -> None:
            """Delete a media file from Anki's media folder."""
            return await self.anki_request("deleteMediaFile", {"filename": filename})

    def run(self):
        """Run the MCP server."""
        self.mcp.run()

def main():
    """Run the MCP server."""
    server = AnkiServer()
    server.run()


if __name__ == "__main__":
    main() 