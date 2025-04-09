import json
from typing import Any, Dict, Optional, Union

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

        @self.mcp.resource("decks://{deck_name}/config")
        async def get_deck_config_resource(deck_name: str) -> str:
            """Get configuration of specific deck."""
            config = await self.anki_request("getDeckConfig", {"deck": deck_name})
            return json.dumps(config)

        @self.mcp.resource("models://{model_id}")
        async def get_model(model_id: str) -> str:
            """Get information about a specific note model."""
            models = await self.anki_request("findModelsById", {"modelIds": [int(model_id)]})
            return json.dumps(models)

        @self.mcp.resource("models://{model_name}/templates")
        async def get_model_templates_resource(model_name: str) -> str:
            """Get templates for a model."""
            templates = await self.anki_request("modelTemplates", {"modelName": model_name})
            return json.dumps(templates)

        @self.mcp.resource("models://{model_name}/styling")
        async def get_model_styling_resource(model_name: str) -> str:
            """Get CSS styling for a model."""
            styling = await self.anki_request("modelStyling", {"modelName": model_name})
            return json.dumps(styling)

        @self.mcp.resource("models://{model_name}/fields")
        async def get_model_fields_resource(model_name: str) -> str:
            """Get field names for a specific note model."""
            fields = await self.anki_request("modelFieldNames", {"modelName": model_name})
            return json.dumps(fields)

        @self.mcp.resource("models://{model_name}/fields/descriptions")
        async def get_model_field_descriptions_resource(model_name: str) -> str:
            """Get field descriptions for a model."""
            descriptions = await self.anki_request("modelFieldDescriptions", {"modelName": model_name})
            return json.dumps(descriptions)

        @self.mcp.resource("models://{model_name}/fields/fonts")
        async def get_model_field_fonts_resource(model_name: str) -> str:
            """Get fonts for model fields."""
            fonts = await self.anki_request("modelFieldFonts", {"modelName": model_name})
            return json.dumps(fonts)

        @self.mcp.resource("models://{model_name}/fields/templates")
        async def get_model_fields_on_templates_resource(model_name: str) -> str:
            """Get fields used on each card template."""
            fields = await self.anki_request("modelFieldsOnTemplates", {"modelName": model_name})
            return json.dumps(fields)

        @self.mcp.resource("cards://{card_id}")
        async def get_card(card_id: str) -> str:
            """Get information about a specific card."""
            cards = await self.anki_request("cardsInfo", {"cards": [int(card_id)]})
            if not cards:
                raise Exception(f"Card {card_id} not found")
            return json.dumps(cards[0])

        @self.mcp.resource("notes://{note_id}")
        async def get_note(note_id: str) -> str:
            """Get information about a specific note."""
            notes = await self.anki_request("notesInfo", {"notes": [int(note_id)]})
            if not notes:
                raise Exception(f"Note {note_id} not found")
            return json.dumps(notes[0])

        @self.mcp.resource("tags://")
        async def list_all_tags() -> str:
            """Get all available tags."""
            tags = await self.anki_request("getTags")
            return json.dumps(tags)

        @self.mcp.resource("tags://{tag_name}")
        async def get_tag_info(tag_name: str) -> str:
            """Get information about a specific tag."""
            notes = await self.anki_request("findNotes", {"query": f"tag:{tag_name}"})
            note_details = []
            if notes:
                note_details = await self.anki_request("notesInfo", {"notes": notes})
            tag_info = {
                "tag": tag_name,
                "noteCount": len(notes),
                "notes": note_details,
            }
            return json.dumps(tag_info)

        @self.mcp.tool()
        async def get_model_names_and_ids(ctx: Context) -> Dict[str, int]:
            """Get the names and IDs of all note models.
            
            Returns:
                Dict mapping model names to their IDs
            """
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
        async def get_cards_info(ctx: Context, card_ids: list[int]) -> list[Dict[str, Any]]:
            """Get information about specific cards."""
            return await self.anki_request("cardsInfo", {"cards": card_ids})

        @self.mcp.tool()
        async def get_decks_stats(ctx: Context, decks: list[str]) -> Dict[str, Any]:
            """Get statistics about decks.
            
            Args:
                decks: List of deck names
            
            Returns:
                Dict containing statistics for each deck
            """
            return await self.anki_request("getDeckStats", {"decks": decks})

        @self.mcp.tool()
        async def create_deck(ctx: Context, deck_name: str) -> int:
            """Create a new deck.
            
            Args:
                deck_name: Name of deck to create
            
            Returns:
                New deck ID
            """
            return await self.anki_request("createDeck", {"deck": deck_name})

        @self.mcp.tool()
        async def get_cards_review_logs(ctx: Context, card_ids: list[int]) -> list[Dict[str, Any]]:
            """Get review history for specific cards."""
            return await self.anki_request("getReviewsOfCards", {"cards": card_ids})

        @self.mcp.tool()
        async def set_card_due_time(
            ctx: Context,
            card_id: int,
            days_from_now: int
        ) -> bool:
            """Set the due time for cards."""
            return await self.anki_request("setSpecificValueOfCard", {
                "card": card_id,
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

        @self.mcp.tool()
        async def get_num_cards_reviewed_today(ctx: Context) -> int:
            """Gets the count of cards that have been reviewed in the current day.
            
            Returns:
                The number of cards reviewed today (based on Anki's day start configuration)
            """
            return await self.anki_request("getNumCardsReviewedToday")

        @self.mcp.tool()
        async def get_num_cards_reviewed_by_day(ctx: Context) -> list[tuple[str, int]]:
            """Gets the number of cards reviewed per day.
            
            Returns:
                A list of tuples containing (date_string, review_count)
                date_string format: "YYYY-MM-DD"
            """
            return await self.anki_request("getNumCardsReviewedByDay")

        @self.mcp.tool()
        async def get_collection_stats(ctx: Context, whole_collection: bool = True) -> str:
            """Gets the collection statistics report in HTML format.
            
            Args:
                whole_collection: If True, gets stats for the whole collection. If False, gets stats for the current deck.
            
            Returns:
                HTML string containing the statistics report
            """
            return await self.anki_request("getCollectionStatsHTML", {"wholeCollection": whole_collection})

        @self.mcp.tool()
        async def get_card_reviews(ctx: Context, deck_name: str, start_id: int) -> list[tuple[int, int, int, int, int, int, int, int, int]]:
            """Gets all card reviews for a specified deck after a certain time.
            
            Args:
                deck_name: Name of the deck to get reviews for
                start_id: Latest unix time not included in the result
            
            Returns:
                List of tuples containing:
                (reviewTime, cardID, usn, buttonPressed, newInterval, previousInterval, newFactor, reviewDuration, reviewType)
            """
            return await self.anki_request("cardReviews", {
                "deck": deck_name,
                "startID": start_id
            })

        @self.mcp.tool()
        async def get_latest_review_id(ctx: Context, deck_name: str) -> int:
            """Gets the unix time of the latest review for the given deck.
            
            Args:
                deck_name: Name of the deck to get the latest review time for
            
            Returns:
                Unix timestamp of the latest review, or 0 if no reviews exist
            """
            return await self.anki_request("getLatestReviewID", {"deck": deck_name})

        @self.mcp.tool()
        async def insert_reviews(ctx: Context, reviews: list[tuple[int, int, int, int, int, int, int, int, int]]) -> None:
            """Inserts review records into the database.
            
            Args:
                reviews: List of tuples containing:
                    (reviewTime, cardID, usn, buttonPressed, newInterval, previousInterval, newFactor, reviewDuration, reviewType)
            """
            return await self.anki_request("insertReviews", {"reviews": reviews})

        @self.mcp.tool()
        async def get_ease_factors(ctx: Context, card_ids: list[int]) -> list[int]:
            """Gets the ease factor for each of the given cards.
            
            Args:
                card_ids: List of card IDs to get ease factors for
            
            Returns:
                List of ease factors (in the same order as the input cards)
            """
            return await self.anki_request("getEaseFactors", {"cards": card_ids})

        @self.mcp.tool()
        async def set_ease_factors(ctx: Context, card_ids: list[int], ease_factors: list[int]) -> list[bool]:
            """Sets ease factor of cards by card ID.
            
            Args:
                card_ids: List of card IDs to set ease factors for
                ease_factors: List of ease factors to set (must match length of card_ids)
            
            Returns:
                List of booleans indicating success for each card
            """
            return await self.anki_request("setEaseFactors", {
                "cards": card_ids,
                "easeFactors": ease_factors
            })

        @self.mcp.tool()
        async def suspend_cards(ctx: Context, card_ids: list[int]) -> bool:
            """Suspend cards by card ID.
            
            Args:
                card_ids: List of card IDs to suspend
            
            Returns:
                True if successful (at least one card wasn't already suspended)
            """
            return await self.anki_request("suspend", {"cards": card_ids})

        @self.mcp.tool()
        async def unsuspend_cards(ctx: Context, card_ids: list[int]) -> bool:
            """Unsuspend cards by card ID.
            
            Args:
                card_ids: List of card IDs to unsuspend
            
            Returns:
                True if successful (at least one card was previously suspended)
            """
            return await self.anki_request("unsuspend", {"cards": card_ids})

        @self.mcp.tool()
        async def is_suspended(ctx: Context, card_id: int) -> bool:
            """Check if a card is suspended.
            
            Args:
                card_id: ID of the card to check
            
            Returns:
                True if the card is suspended, False otherwise
            """
            return await self.anki_request("suspended", {"card": card_id})

        @self.mcp.tool()
        async def are_suspended(ctx: Context, card_ids: list[int]) -> list[Optional[bool]]:
            """Check suspension status for multiple cards.
            
            Args:
                card_ids: List of card IDs to check
            
            Returns:
                List of booleans (True if suspended) or None if card doesn't exist
            """
            return await self.anki_request("areSuspended", {"cards": card_ids})

        @self.mcp.tool()
        async def are_due(ctx: Context, card_ids: list[int]) -> list[bool]:
            """Check if cards are due.
            
            Args:
                card_ids: List of card IDs to check
            
            Returns:
                List of booleans indicating whether each card is due
            """
            return await self.anki_request("areDue", {"cards": card_ids})

        @self.mcp.tool()
        async def get_intervals(ctx: Context, card_ids: list[int], complete: bool = False) -> Union[list[int], list[list[int]]]:
            """Get intervals for cards.
            
            Args:
                card_ids: List of card IDs to get intervals for
                complete: If True, returns all intervals, if False returns only most recent
            
            Returns:
                If complete=False: List of most recent intervals
                If complete=True: List of lists containing all intervals
                Negative intervals are in seconds, positive intervals in days
            """
            return await self.anki_request("getIntervals", {
                "cards": card_ids,
                "complete": complete
            })

        @self.mcp.tool()
        async def cards_to_notes(ctx: Context, card_ids: list[int]) -> list[int]:
            """Convert card IDs to their corresponding note IDs.
            
            Args:
                card_ids: List of card IDs to convert
            
            Returns:
                List of unique note IDs (duplicates removed)
            """
            return await self.anki_request("cardsToNotes", {"cards": card_ids})

        @self.mcp.tool()
        async def get_cards_mod_time(ctx: Context, card_ids: list[int]) -> list[Dict[str, Any]]:
            """Get modification times for cards.
            
            Args:
                card_ids: List of card IDs to get modification times for
            
            Returns:
                List of objects containing cardId and mod timestamp
            """
            return await self.anki_request("cardsModTime", {"cards": card_ids})

        @self.mcp.tool()
        async def forget_cards(ctx: Context, card_ids: list[int]) -> None:
            """Reset cards to new state.
            
            Args:
                card_ids: List of card IDs to reset
            """
            return await self.anki_request("forgetCards", {"cards": card_ids})

        @self.mcp.tool()
        async def relearn_cards(ctx: Context, card_ids: list[int]) -> None:
            """Make cards relearning.
            
            Args:
                card_ids: List of card IDs to set to relearning
            """
            return await self.anki_request("relearnCards", {"cards": card_ids})

        @self.mcp.tool()
        async def answer_cards(ctx: Context, answers: list[Dict[str, Any]]) -> list[bool]:
            """Answer cards.
            
            Args:
                answers: List of dicts containing:
                    - cardId: int
                    - ease: int (1-4)
            
            Returns:
                List of booleans indicating success for each card
            """
            return await self.anki_request("answerCards", {"answers": answers})

        @self.mcp.tool()
        async def set_due_date(ctx: Context, card_ids: list[int], days: str) -> bool:
            """Set due date for cards.
            
            Args:
                card_ids: List of card IDs to set due date for
                days: Due date specification:
                    - "0" = today
                    - "1!" = tomorrow + change interval to 1
                    - "3-7" = random choice between 3-7 days
            
            Returns:
                True if successful
            """
            return await self.anki_request("setDueDate", {
                "cards": card_ids,
                "days": days
            })

        @self.mcp.tool()
        async def can_add_notes(ctx: Context, notes: list[Dict[str, Any]]) -> list[bool]:
            """Check if notes can be added.
            
            Args:
                notes: List of note specifications with:
                    - deckName: str
                    - modelName: str
                    - fields: Dict[str, str]
                    - tags: Optional[list[str]]
            
            Returns:
                List of booleans indicating whether each note can be added
            """
            return await self.anki_request("canAddNotes", {"notes": notes})

        @self.mcp.tool()
        async def can_add_notes_with_error_detail(ctx: Context, notes: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
            """Check if notes can be added with detailed error information.
            
            Args:
                notes: List of note specifications with:
                    - deckName: str
                    - modelName: str
                    - fields: Dict[str, str]
                    - tags: Optional[list[str]]
            
            Returns:
                List of objects containing:
                    - canAdd: bool
                    - error: Optional[str] - Error message if canAdd is False
            """
            return await self.anki_request("canAddNotesWithErrorDetail", {"notes": notes})

        @self.mcp.tool()
        async def add_notes(ctx: Context, notes: list[Dict[str, Any]]) -> list[Optional[int]]:
            """Add multiple notes at once.
            
            Args:
                notes: List of note specifications with:
                    - deckName: str
                    - modelName: str
                    - fields: Dict[str, str]
                    - tags: Optional[list[str]]
                    - audio: Optional[list[Dict]] - Audio attachments
                    - video: Optional[list[Dict]] - Video attachments
                    - picture: Optional[list[Dict]] - Picture attachments
            
            Returns:
                List of note IDs (None for notes that couldn't be added)
            """
            return await self.anki_request("addNotes", {"notes": notes})

        @self.mcp.tool()
        async def update_note(ctx: Context, note: Dict[str, Any]) -> None:
            """Update a note's fields and/or tags.
            
            Args:
                note: Note specification with:
                    - id: int - Note ID
                    - fields: Optional[Dict[str, str]] - Fields to update
                    - tags: Optional[list[str]] - New tags
                    - audio: Optional[list[Dict]] - Audio attachments
                    - video: Optional[list[Dict]] - Video attachments
                    - picture: Optional[list[Dict]] - Picture attachments
            """
            return await self.anki_request("updateNote", {"note": note})

        @self.mcp.tool()
        async def update_note_model(ctx: Context, note: Dict[str, Any]) -> None:
            """Update a note's model, fields, and tags.
            
            Args:
                note: Note specification with:
                    - id: int - Note ID
                    - modelName: str - New model name
                    - fields: Dict[str, str] - New field values
                    - tags: Optional[list[str]] - New tags
            """
            return await self.anki_request("updateNoteModel", {"note": note})

        @self.mcp.tool()
        async def get_note_tags(ctx: Context, note_id: int) -> list[str]:
            """Get a note's tags.
            
            Args:
                note_id: ID of the note
            
            Returns:
                List of tags
            """
            return await self.anki_request("getNoteTags", {"note": note_id})

        @self.mcp.tool()
        async def get_tags(ctx: Context) -> list[str]:
            """Get all available tags.
            
            Returns:
                List of all tags in use
            """
            return await self.anki_request("getTags")

        @self.mcp.tool()
        async def clear_unused_tags(ctx: Context) -> None:
            """Remove all unused tags."""
            return await self.anki_request("clearUnusedTags")

        @self.mcp.tool()
        async def replace_tags(ctx: Context, note_ids: list[int], tag_to_replace: str, replace_with_tag: str) -> None:
            """Replace tags in specific notes.
            
            Args:
                note_ids: List of note IDs to modify
                tag_to_replace: Tag to replace
                replace_with_tag: New tag
            """
            return await self.anki_request("replaceTags", {
                "notes": note_ids,
                "tag_to_replace": tag_to_replace,
                "replace_with_tag": replace_with_tag
            })

        @self.mcp.tool()
        async def replace_tags_in_all_notes(ctx: Context, tag_to_replace: str, replace_with_tag: str) -> None:
            """Replace tags in all notes.
            
            Args:
                tag_to_replace: Tag to replace
                replace_with_tag: New tag
            """
            return await self.anki_request("replaceTagsInAllNotes", {
                "tag_to_replace": tag_to_replace,
                "replace_with_tag": replace_with_tag
            })

        @self.mcp.tool()
        async def get_notes_info(ctx: Context, note_ids: Optional[list[int]] = None, query: Optional[str] = None) -> list[Dict[str, Any]]:
            """Get detailed information about notes.
            
            Args:
                note_ids: Optional list of note IDs to get info for
                query: Optional search query to find notes
                (One of note_ids or query must be provided)
            
            Returns:
                List of note information objects containing:
                    - noteId: int
                    - modelName: str
                    - tags: list[str]
                    - fields: Dict[str, Dict[str, Any]]
                    - cards: list[int]
            """
            params = {}
            if note_ids is not None:
                params["notes"] = note_ids
            if query is not None:
                params["query"] = query
            return await self.anki_request("notesInfo", params)

        @self.mcp.tool()
        async def get_notes_mod_time(ctx: Context, note_ids: list[int]) -> list[Dict[str, Any]]:
            """Get modification times for notes.
            
            Args:
                note_ids: List of note IDs
            
            Returns:
                List of objects containing:
                    - noteId: int
                    - mod: int (modification timestamp)
            """
            return await self.anki_request("notesModTime", {"notes": note_ids})

        @self.mcp.tool()
        async def remove_empty_notes(ctx: Context) -> None:
            """Remove all empty notes."""
            return await self.anki_request("removeEmptyNotes")

        @self.mcp.tool()
        async def get_model_names(ctx: Context) -> list[str]:
            """Get the complete list of model names.
            
            Returns:
                List of model names
            """
            return await self.anki_request("modelNames")

        @self.mcp.tool()
        async def get_deck_names(ctx: Context) -> list[str]:
            """Get the complete list of deck names.
            
            Returns:
                List of deck names
            """
            return await self.anki_request("deckNames")

        @self.mcp.tool()
        async def get_deck_configs(ctx: Context) -> Dict[str, Any]:
            """Get all deck configurations.
            
            Returns:
                Dict mapping config names to their settings
            """
            return await self.anki_request("getDeckConfigs")

        @self.mcp.tool()
        async def save_deck_config(ctx: Context, config: Dict[str, Any]) -> bool:
            """Save deck configuration.
            
            Args:
                config: Configuration object to save
            
            Returns:
                True if successful
            """
            return await self.anki_request("saveDeckConfig", {"config": config})

        @self.mcp.tool()
        async def set_deck_config_id(ctx: Context, decks: list[str], config_id: int) -> bool:
            """Set configuration group for decks.
            
            Args:
                decks: List of deck names
                config_id: ID of configuration group to set
            
            Returns:
                True if successful
            """
            return await self.anki_request("setDeckConfigId", {
                "decks": decks,
                "configId": config_id
            })

        @self.mcp.tool()
        async def clone_deck_config_id(ctx: Context, name: str, clone_from: int) -> int:
            """Create new options group, cloning from an existing one.
            
            Args:
                name: Name for new options group
                clone_from: ID of group to clone from
            
            Returns:
                New options group ID
            """
            return await self.anki_request("cloneDeckConfigId", {
                "name": name,
                "cloneFrom": clone_from
            })

        @self.mcp.tool()
        async def remove_deck_config(ctx: Context, config_id: int) -> bool:
            """Remove a configuration group.
            
            Args:
                config_id: ID of configuration group to remove
            
            Returns:
                True if successful
            """
            return await self.anki_request("removeDeckConfig", {"configId": config_id})

        @self.mcp.tool()
        async def get_deck_config(ctx: Context, deck: str) -> Dict[str, Any]:
            """Get configuration of specific deck.
            
            Args:
                deck: Name of the deck
            
            Returns:
                Configuration of the specified deck
            """
            return await self.anki_request("getDeckConfig", {"deck": deck})

    def run(self):
        """Run the MCP server."""
        self.mcp.run()

def main():
    """Run the MCP server."""
    server = AnkiServer()
    server.run()


if __name__ == "__main__":
    main() 