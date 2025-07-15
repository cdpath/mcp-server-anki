import json
import base64
from typing import Any, Dict, Optional, Union, List
import re

import aiohttp
from mcp.server.fastmcp import Context, FastMCP


class AnkiServer:
    def __init__(self, anki_connect_url: str = "http://localhost:8765"):
        self.anki_connect_url = anki_connect_url
        self.mcp = FastMCP("Anki MCP", dependencies=["aiohttp>=3.9.0"])
        self._setup_handlers()

    async def anki_request(
        self, action: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
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

    def _parse_ids_from_path(self, path: str) -> List[str]:
        """Parse comma-separated IDs from path."""
        if not path:
            return []
        return [id.strip() for id in path.split(",") if id.strip()]

    def _encode_cursor(self, data: Dict[str, Any]) -> str:
        """Encode pagination cursor."""
        return base64.b64encode(json.dumps(data).encode()).decode()

    def _decode_cursor(self, cursor: str) -> Dict[str, Any]:
        """Decode pagination cursor."""
        try:
            return json.loads(base64.b64decode(cursor).decode())
        except Exception:
            raise ValueError("Invalid cursor")

    def _paginate_list(self, items: List[Any], cursor: Optional[str] = None, page_size: int = 50) -> Dict[str, Any]:
        """Paginate a list of items."""
        start_index = 0
        if cursor:
            cursor_data = self._decode_cursor(cursor)
            start_index = cursor_data.get("start_index", 0)
        
        end_index = start_index + page_size
        page_items = items[start_index:end_index]
        
        result = {"items": page_items}
        
        # Add nextCursor if there are more items
        if end_index < len(items):
            next_cursor_data = {"start_index": end_index}
            result["nextCursor"] = self._encode_cursor(next_cursor_data)
        
        return result

    def _setup_handlers(self):
        """Set up resources and tools for the MCP server."""

        # RESOURCES (Read-only operations)
        @self.mcp.resource("anki://decks")
        async def get_all_decks() -> str:
            """Get all deck names and IDs."""
            decks = await self.anki_request("deckNamesAndIds")
            # Convert dict to list of objects for better structure
            deck_list = [{"name": name, "id": deck_id} for name, deck_id in decks.items()]
            return json.dumps(deck_list)

        @self.mcp.resource("anki://decks/{deck_id}")
        async def get_deck_config(deck_id: str) -> str:
            """Get configuration of specific deck by ID or name."""
            # Try as ID first if it looks numeric, otherwise try as name
            if deck_id.isdigit():
                config = await self.anki_request("getDeckConfig", {"deck": int(deck_id)})
            else:
                config = await self.anki_request("getDeckConfig", {"deck": deck_id})
            return json.dumps(config)

        @self.mcp.resource("anki://decks/{deck_id}/stats")
        async def get_decks_stats(deck_id: str) -> str:
            """Get statistics for a deck by deck_id"""
            stats = await self.anki_request("getDeckStats", {"decks": [deck_id]})
            return json.dumps(stats)

        @self.mcp.resource("anki://models")
        async def get_all_models() -> str:
            """Get all note models with their templates and fields."""
            model_names_and_ids = await self.anki_request("modelNamesAndIds")
            models = await self.anki_request(
                "findModelsById", {"modelIds": list(model_names_and_ids.values())}
            )
            return json.dumps(models)

        @self.mcp.resource("anki://models/{model_name}")
        async def get_model_info(model_name: str) -> str:
            """Get model info for a specific model, including templates and fields."""
            fields_on_templates = await self.anki_request(
                "modelFieldsOnTemplates", {"modelName": model_name}
            )
            return json.dumps(fields_on_templates)

        @self.mcp.resource("anki://cards/{card_ids}")
        async def get_cards_info(card_ids: str) -> str:
            """Get information about one or more cards (comma-separated IDs)."""
            card_id_list = [int(card_id) for card_id in self._parse_ids_from_path(card_ids)]
            if not card_id_list:
                raise Exception("No card IDs provided")
            
            cards = await self.anki_request("cardsInfo", {"cards": card_id_list})
            # Return single object if only one card requested, array otherwise
            if len(card_id_list) == 1:
                if not cards:
                    raise Exception(f"Card {card_id_list[0]} not found")
                return json.dumps(cards[0])
            return json.dumps(cards)

        @self.mcp.resource("anki://notes/{note_ids}")
        async def get_notes_info(note_ids: str) -> str:
            """Get information about one or more notes (comma-separated IDs)."""
            note_id_list = [int(note_id) for note_id in self._parse_ids_from_path(note_ids)]
            if not note_id_list:
                raise Exception("No note IDs provided")
            
            notes = await self.anki_request("notesInfo", {"notes": note_id_list})
            # Return single object if only one note requested, array otherwise
            if len(note_id_list) == 1:
                if not notes:
                    raise Exception(f"Note {note_id_list[0]} not found")
                return json.dumps(notes[0])
            return json.dumps(notes)

        @self.mcp.resource("anki://cards/{card_ids}/reviews")
        async def get_cards_review_logs(card_ids: str) -> str:
            """Get review history for one or more cards (comma-separated IDs)."""
            card_id_list = [int(card_id) for card_id in self._parse_ids_from_path(card_ids)]
            if not card_id_list:
                raise Exception("No card IDs provided")
            
            reviews = await self.anki_request("getReviewsOfCards", {"cards": card_id_list})
            return json.dumps(reviews)

        @self.mcp.resource("anki://tags")
        async def get_all_tags() -> str:
            """Get all available tags."""
            tags = await self.anki_request("getTags")
            return json.dumps(tags)

        @self.mcp.resource("anki://session/current")
        async def get_current_session() -> str:
            """Get current learning session state including current card."""
            current_card = await self.anki_request("guiCurrentCard")
            return json.dumps({
                "current_card": current_card,
                "timestamp": int(__import__("time").time())
            })

        @self.mcp.resource("anki://collection/stats")
        async def get_collection_stats() -> str:
            """Get collection statistics in HTML format."""
            stats_html = await self.anki_request("getCollectionStatsHTML", {"wholeCollection": True})
            return json.dumps({
                "stats_html": stats_html,
                "generated_at": int(__import__("time").time())
            })

        @self.mcp.resource("anki://stats/daily")
        async def get_daily_stats() -> str:
            """Get daily review statistics."""
            today_reviews = await self.anki_request("getNumCardsReviewedToday")
            return json.dumps({
                "today": today_reviews,
                "date": __import__("datetime").datetime.now().strftime("%Y-%m-%d")
            })

        # TOOLS (Operations with side effects)
        @self.mcp.tool()
        async def anki_search(
            ctx: Context,
            query: str,
            search_type: str = "cards",
            cursor: Optional[str] = None
        ) -> str:
            """Search cards or notes using Anki's search syntax with pagination.

            Args:
                query: Anki search query (e.g., "deck:current", "tag:important")
                search_type: "cards" or "notes"
                cursor: Optional pagination cursor

            Returns:
                JSON string with search results and optional nextCursor
            """
            if search_type not in ["cards", "notes"]:
                raise ValueError("search_type must be 'cards' or 'notes'")
            
            if search_type == "cards":
                result_ids = await self.anki_request("findCards", {"query": query})
                data = await self.anki_request("cardsInfo", {"cards": result_ids})
                
            else:
                result_ids = await self.anki_request("findNotes", {"query": query})
                data = await self.anki_request("notesInfo", {"notes": result_ids})
            
            paginated = self._paginate_list(data, cursor, page_size=100)
            return json.dumps({
                "search_type": search_type,
                "query": query,
                "total_found": len(result_ids),
                **paginated
            })

        @self.mcp.tool()
        async def anki_create_notes(
            ctx: Context,
            notes: List[Dict[str, Any]]
        ) -> List[Optional[int]]:
            """Create one or more notes in Anki.

            Args:
                notes: List of note specifications with:
                    - deckName: str
                    - modelName: str
                    - fields: Dict[str, str]
                    - tags: Optional[List[str]]

            Returns:
                List of note IDs (None for notes that couldn't be added)
            """
            return await self.anki_request("addNotes", {"notes": notes})

        @self.mcp.tool()
        async def anki_update_note(ctx: Context, note: Dict[str, Any]) -> None:
            """Update a note's fields and/or tags.

            Args:
                note: Note specification with:
                    - id: int - Note ID
                    - fields: Optional[Dict[str, str]] - Fields to update
                    - tags: Optional[List[str]] - New tags
            """
            await self.anki_request("updateNote", {"note": note})

        @self.mcp.tool()
        async def anki_manage_tags(
            ctx: Context,
            action: str,
            note_ids: List[Union[str, int]],
            tags: str,
            tag_to_replace: Optional[str] = None,
            replace_with_tag: Optional[str] = None
        ) -> None:
            """Manage tags on notes.

            Args:
                action: "add" | "delete" | "replace"
                note_ids: List of note IDs to modify
                tags: Tag string for add/delete operations
                tag_to_replace: Tag to replace (for replace action)
                replace_with_tag: New tag (for replace action)
            """
            note_ids = [int(note_id) for note_id in note_ids]
            
            if action == "add":
                await self.anki_request("addTags", {"notes": note_ids, "tags": tags})
            elif action == "delete":
                await self.anki_request("removeTags", {"notes": note_ids, "tags": tags})
            elif action == "replace":
                await self.anki_request("replaceTags", {
                    "notes": note_ids,
                    "tag_to_replace": tag_to_replace,
                    "replace_with_tag": replace_with_tag
                })
            else:
                raise ValueError(f"Invalid action: {action}. Must be 'add', 'delete', or 'replace'")

        @self.mcp.tool()
        async def anki_change_card_state(
            ctx: Context,
            action: str,
            card_ids: List[Union[str, int]],
            days: Optional[str] = None,
            ease_factors: Optional[List[int]] = None
        ) -> Any:
            """Change card states and properties.

            Args:
                action: "suspend" | "unsuspend" | "forget" | "relearn" | "set_due" | "set_ease"
                card_ids: List of card IDs to modify
                days: Due date specification for set_due (e.g., "0", "1!", "3-7")
                ease_factors: List of ease factors for set_ease (must match card_ids length)

            Returns:
                Result depends on action (bool for most, list for some)
            """
            card_ids = [int(card_id) for card_id in card_ids]
            
            if action == "suspend":
                return await self.anki_request("suspend", {"cards": card_ids})
            elif action == "unsuspend":
                return await self.anki_request("unsuspend", {"cards": card_ids})
            elif action == "forget":
                await self.anki_request("forgetCards", {"cards": card_ids})
                return True
            elif action == "relearn":
                await self.anki_request("relearnCards", {"cards": card_ids})
                return True
            elif action == "set_due":
                if not days:
                    raise ValueError("days parameter required for set_due action")
                return await self.anki_request("setDueDate", {"cards": card_ids, "days": days})
            elif action == "set_ease":
                if not ease_factors or len(ease_factors) != len(card_ids):
                    raise ValueError("ease_factors must match card_ids length for set_ease action")
                return await self.anki_request("setEaseFactors", {"cards": card_ids, "easeFactors": ease_factors})
            else:
                raise ValueError(f"Invalid action: {action}")

        @self.mcp.tool()
        async def anki_gui_control(
            ctx: Context,
            action: str,
            ease: Optional[int] = None
        ) -> Any:
            """Control Anki GUI for interactive learning.

            Args:
                action: "current_card" | "show_answer" | "answer" | "undo"
                ease: Answer ease for "answer" action (1=Again, 2=Hard, 3=Good, 4=Easy)

            Returns:
                Result depends on action
            """
            if action == "current_card":
                return await self.anki_request("guiCurrentCard")
            elif action == "show_answer":
                return await self.anki_request("guiShowAnswer")
            elif action == "answer":
                if ease is None:
                    raise ValueError("ease parameter required for answer action")
                if ease not in [1, 2, 3, 4]:
                    raise ValueError("ease must be 1 (Again), 2 (Hard), 3 (Good), or 4 (Easy)")
                return await self.anki_request("guiAnswerCard", {"ease": ease})
            elif action == "undo":
                return await self.anki_request("guiUndo")
            else:
                raise ValueError(f"Invalid action: {action}")

        @self.mcp.tool()
        async def anki_delete_notes(ctx: Context, note_ids: List[Union[str, int]]) -> None:
            """Delete notes by their IDs.
            
            Args:
                note_ids: List of note IDs to delete
            """
            note_ids = [int(note_id) for note_id in note_ids]
            await self.anki_request("deleteNotes", {"notes": note_ids})

        @self.mcp.tool()
        async def anki_update_deck_config(ctx: Context, config: Dict[str, Any]) -> bool:
            """Update deck configuration.

            Args:
                config: Configuration object to save

            Returns:
                True if successful
            """
            return await self.anki_request("saveDeckConfig", {"config": config})

    def run(self):
        """Run the MCP server."""
        self.mcp.run()


def main():
    """Run the MCP server."""
    server = AnkiServer()
    server.run()


if __name__ == "__main__":
    main()
