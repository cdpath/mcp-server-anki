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
        
        @self.mcp.tool()
        async def list_decks(ctx: Context) -> str:
            """List all the decks"""
            decks = await self.anki_request("deckNamesAndIds")
            """
            {"Default": 1}
            """
            return json.dumps(decks)

        @self.mcp.tool()
        async def get_deck_config(ctx: Context, deck_name: str) -> str:
            """Get configuration of specific deck."""
            config = await self.anki_request("getDeckConfig", {"deck": deck_name})
            """
            {
                "lapse": {"leechFails": 8, "delays": [10], "minInt": 1, "leechAction": 0, "mult": 0},
                "dyn": false,
                "autoplay": true,
                "mod": 1502970872,
                "id": 1,
                "maxTaken": 60,
                "new": {"bury": true, "order": 1, "initialFactor": 2500, "perDay": 20, "delays": [1, 10], "separate": true, "ints": [1, 4, 7]},
                "name": "Default",
                "rev": {"bury": true, "ivlFct": 1, "ease4": 1.3, "maxIvl": 36500, "perDay": 100, "minSpace": 1, "fuzz": 0.05},
                "timer": 0,
                "replayq": true,
                "usn": -1
            }
            """
            return json.dumps(config)

        @self.mcp.tool()
        async def update_deck_config(ctx: Context, config: Dict[str, Any]) -> bool:
            """Save deck configuration.
            
            Args:
                config: Configuration object to save
            
            Returns:
                True if successful
            """
            return await self.anki_request("saveDeckConfig", {"config": config})

        @self.mcp.tool()
        async def set_deck_config_id(ctx: Context, decks: list[str], config_id: Union[str, int]) -> bool:
            """Set configuration group for decks.
            
            Args:
                decks: List of deck names
                config_id: ID of configuration group to set
            
            Returns:
                True if successful
            """
            return await self.anki_request("setDeckConfigId", {
                "decks": decks,
                "configId": int(config_id)
            })

        @self.mcp.tool()
        async def clone_deck_config_id(ctx: Context, name: str, clone_from: Union[str, int]) -> int:
            """Create new options group, cloning from an existing one.
            
            Args:
                name: Name for new options group
                clone_from: ID of group to clone from
            
            Returns:
                New options group ID
            """
            return await self.anki_request("cloneDeckConfigId", {
                "name": name,
                "cloneFrom": int(clone_from)
            })

        @self.mcp.tool()
        async def delete_deck_config(ctx: Context, config_id: Union[str, int]) -> bool:
            """Remove a configuration group.
            
            Args:
                config_id: ID of configuration group to remove
            
            Returns:
                True if successful
            """
            return await self.anki_request("removeDeckConfigId", {"configId": int(config_id)})

        @self.mcp.tool()
        async def list_models(ctx: Context) -> str:
            """List all the models and their templates and fields"""
            model_names_and_ids = await self.anki_request("modelNamesAndIds")
            """
            {
                "Basic": 1483883011648,
                "Basic (and reversed card)": 1483883011644,
                "Basic (optional reversed card)": 1483883011631,
                "Cloze": 1483883011630
            }
            """
            models = await self.anki_request("findModelsById", {"modelIds": list(model_names_and_ids.values())})
            """
            [
                {
                "id": 1704387367119,
                "name": "Basic",
                "type": 0,
                "mod": 1704387367,
                "usn": -1,
                "sortf": 0,
                "did": null,
                "tmpls": [
                    { "name": "Card 1", "ord": 0, "qfmt": "{{Front}}", "afmt": "{{FrontSide}}\n\n<hr id=answer>\n\n{{Back}}", "bqfmt": "", "bafmt": "", "did": null, "bfont": "", "bsize": 0, "id": 9176047152973362695 }
                ],
                "flds": [
                    { "name": "Front", "ord": 0, "sticky": false, "rtl": false, "font": "Arial", "size": 20, "description": "", "plainText": false, "collapsed": false, "excludeFromSearch": false, "id": 2453723143453745216, "tag": null, "preventDeletion": false },
                    { "name": "Back", "ord": 1, "sticky": false, "rtl": false, "font": "Arial", "size": 20, "description": "", "plainText": false, "collapsed": false, "excludeFromSearch": false, "id": -4853200230425436781, "tag": null, "preventDeletion": false }
                ],
                "css": "",
                "req": [...],
                "originalStockKind": 1
                }
            ]
            """
            return json.dumps(models)

        @self.mcp.tool()
        async def get_model_info(ctx: Context, model_name: str) -> str:
            """Get model info for a specific model, including templates and fields"""
            fields_on_templates = await self.anki_request("modelFieldsOnTemplates", {"modelName": model_name})
            """
            {
                "Card 1": [["Front"], ["Back"]],
                "Card 2": [["Back"], ["Front"]]
            }
            """
            return json.dumps(fields_on_templates)

        @self.mcp.tool()
        async def get_card_info(ctx: Context, card_id: Union[str, int]) -> str:
            """Get information about a specific card."""
            cards = await self.anki_request("cardsInfo", {"cards": [int(card_id)]})
            if not cards:
                raise Exception(f"Card {card_id} not found")
            """
            {
                "answer": "back content",
                "question": "front content",
                "deckName": "Default",
                "modelName": "Basic",
                "fieldOrder": 1,
                "fields": {
                    "Front": {"value": "front content", "order": 0},
                    "Back": {"value": "back content", "order": 1}
                },
                "css":"p {font-family:Arial;}",
                "cardId": 1498938915662,
                "interval": 16,
                "note":1502298033753,
                "ord": 1,
                "type": 0,
                "queue": 0,
                "due": 1,
                "reps": 1,
                "lapses": 0,
                "left": 6,
                "mod": 1629454092
            }
            """
            return json.dumps(cards[0])

        @self.mcp.tool()
        async def get_note_info(ctx: Context, note_id: Union[str, int]) -> str:
            """Get information about a specific note."""
            notes = await self.anki_request("notesInfo", {"notes": [int(note_id)]})
            if not notes:
                raise Exception(f"Note {note_id} not found")
            """
            {
                "noteId":1502298033753,
                "profile": "User_1",
                "modelName": "Basic",
                "tags":["tag","another_tag"],
                "fields": {
                    "Front": {"value": "front content", "order": 0},
                    "Back": {"value": "back content", "order": 1}
                },
                "mod": 1718377864,
                "cards": [1498938915662]
            }            
            """
            return json.dumps(notes[0])

        @self.mcp.tool()
        async def list_all_tags(ctx: Context) -> str:
            """Get all available tags."""
            tags = await self.anki_request("getTags")
            return json.dumps(tags)

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
        async def search_notes(ctx: Context, query: str = "deck:current") -> list[int]:
            """Find notes using Anki's search syntax."""
            return await self.anki_request("findNotes", {"query": query})

        @self.mcp.tool()
        async def search_cards(ctx: Context, query: str = "deck:current") -> list[int]:
            """Find cards using Anki's search syntax."""
            return await self.anki_request("findCards", {"query": query})

        @self.mcp.tool()
        async def update_note_fields(
            ctx: Context,
            note_id: Union[str, int],
            fields: Dict[str, str]
        ) -> None:
            """Update the fields of an existing note."""
            return await self.anki_request("updateNoteFields", {
                "note": {"id": note_id, "fields": fields}
            })

        @self.mcp.tool()
        async def delete_notes(ctx: Context, note_ids: list[Union[str, int]]) -> None:
            """Delete notes by their IDs."""
            return await self.anki_request("deleteNotes", {"notes": note_ids})

        @self.mcp.tool()
        async def add_tags(
            ctx: Context,
            note_ids: list[Union[str, int]],
            tags: str
        ) -> None:
            """Add tags to notes."""
            return await self.anki_request("addTags", {
                "notes": note_ids,
                "tags": tags
            })

        @self.mcp.tool()
        async def delete_tags(
            ctx: Context,
            note_ids: list[Union[str, int]],
            tags: str
        ) -> None:
            """Remove tags from notes."""
            return await self.anki_request("removeTags", {
                "notes": note_ids,
                "tags": tags
            })

        @self.mcp.tool()
        async def batch_get_cards_info(ctx: Context, card_ids: list[Union[str, int]]) -> list[Dict[str, Any]]:
            """Get information about specific cards."""
            return await self.anki_request("cardsInfo", {"cards": card_ids})

        @self.mcp.tool()
        async def batch_get_decks_stats(ctx: Context, decks: list[str]) -> Dict[str, Any]:
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
        async def batch_get_cards_review_logs(ctx: Context, card_ids: list[Union[str, int]]) -> list[Dict[str, Any]]:
            """Get review history for specific cards."""
            return await self.anki_request("getReviewsOfCards", {"cards": card_ids})

        @self.mcp.tool()
        async def set_card_due_time(
            ctx: Context,
            card_id: Union[str, int],
            days_from_now: int
        ) -> bool:
            """Set the due time for cards."""
            return await self.anki_request("setSpecificValueOfCard", {
                "card": card_id,
                "keys": ["due"],
                "newValues": [days_from_now]
            })

        @self.mcp.tool()
        async def get_num_cards_reviewed_by_day(ctx: Context, today: bool = True) -> list[tuple[str, int]]:
            """Gets the number of cards reviewed per day.
            
            Returns:
                A list of tuples containing (date_string, review_count)
                date_string format: "YYYY-MM-DD"
            """
            if today:
                return await self.anki_request("getNumCardsReviewedToday")
            else:
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
        async def get_latest_review_time(ctx: Context, deck_name: str) -> int:
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
        async def get_ease_factors(ctx: Context, card_ids: list[Union[str, int]]) -> list[int]:
            """Gets the ease factor for each of the given cards.
            
            Args:
                card_ids: List of card IDs to get ease factors for
            
            Returns:
                List of ease factors (in the same order as the input cards)
            """
            card_ids = [int(card_id) for card_id in card_ids]
            return await self.anki_request("getEaseFactors", {"cards": card_ids})

        @self.mcp.tool()
        async def set_ease_factors(ctx: Context, card_ids: list[Union[str, int]], ease_factors: list[int]) -> list[bool]:
            """Sets ease factor of cards by card ID.
            
            Args:
                card_ids: List of card IDs to set ease factors for
                ease_factors: List of ease factors to set (must match length of card_ids)
            
            Returns:
                List of booleans indicating success for each card
            """
            card_ids = [int(card_id) for card_id in card_ids]
            return await self.anki_request("setEaseFactors", {
                "cards": card_ids,
                "easeFactors": ease_factors
            })

        @self.mcp.tool()
        async def suspend_cards(ctx: Context, card_ids: list[Union[str, int]]) -> bool:
            """Suspend cards by card ID.
            
            Args:
                card_ids: List of card IDs to suspend
            
            Returns:
                True if successful (at least one card wasn't already suspended)
            """
            card_ids = [int(card_id) for card_id in card_ids]
            return await self.anki_request("suspend", {"cards": card_ids})

        @self.mcp.tool()
        async def unsuspend_cards(ctx: Context, card_ids: list[Union[str, int]]) -> bool:
            """Unsuspend cards by card ID.
            
            Args:
                card_ids: List of card IDs to unsuspend
            
            Returns:
                True if successful (at least one card was previously suspended)
            """
            card_ids = [int(card_id) for card_id in card_ids]
            return await self.anki_request("unsuspend", {"cards": card_ids})

        @self.mcp.tool()
        async def are_suspended(ctx: Context, card_ids: list[Union[str, int]]) -> list[Optional[bool]]:
            """Check suspension status for multiple cards.
            
            Args:
                card_ids: List of card IDs to check
            
            Returns:
                List of booleans (True if suspended) or None if card doesn't exist
            """
            card_ids = [int(card_id) for card_id in card_ids]
            return await self.anki_request("areSuspended", {"cards": card_ids})

        @self.mcp.tool()
        async def are_due(ctx: Context, card_ids: list[Union[str, int]]) -> list[bool]:
            """Check if cards are due.
            
            Args:
                card_ids: List of card IDs to check
            
            Returns:
                List of booleans indicating whether each card is due
            """
            card_ids = [int(card_id) for card_id in card_ids]
            return await self.anki_request("areDue", {"cards": card_ids})

        @self.mcp.tool()
        async def get_intervals(ctx: Context, card_ids: list[Union[str, int]], complete: bool = False) -> Union[list[int], list[list[int]]]:
            """Get intervals for cards.
            
            Args:
                card_ids: List of card IDs to get intervals for
                complete: If True, returns all intervals, if False returns only most recent
            
            Returns:
                If complete=False: List of most recent intervals
                If complete=True: List of lists containing all intervals
                Negative intervals are in seconds, positive intervals in days
            """
            card_ids = [int(card_id) for card_id in card_ids]
            return await self.anki_request("getIntervals", {
                "cards": card_ids,
                "complete": complete
            })

        @self.mcp.tool()
        async def lookup_note_ids_for_cards(ctx: Context, card_ids: list[Union[str, int]]) -> list[int]:
            """Convert card IDs to their corresponding note IDs.
            
            Args:
                card_ids: List of card IDs to convert
            
            Returns:
                List of unique note IDs (duplicates removed)
            """
            card_ids = [int(card_id) for card_id in card_ids]
            return await self.anki_request("cardsToNotes", {"cards": card_ids})

        @self.mcp.tool()
        async def get_cards_modification_time(ctx: Context, card_ids: list[Union[str, int]]) -> list[Dict[str, Any]]:
            """Get modification times for cards.
            
            Args:
                card_ids: List of card IDs to get modification times for
            
            Returns:
                List of objects containing cardId and mod timestamp
            """
            card_ids = [int(card_id) for card_id in card_ids]
            return await self.anki_request("cardsModTime", {"cards": card_ids})

        @self.mcp.tool()
        async def forget_cards(ctx: Context, card_ids: list[Union[str, int]]) -> None:
            """Reset cards to new state.
            
            Args:
                card_ids: List of card IDs to reset
            """
            card_ids = [int(card_id) for card_id in card_ids]
            return await self.anki_request("forgetCards", {"cards": card_ids})

        @self.mcp.tool()
        async def relearn_cards(ctx: Context, card_ids: list[Union[str, int]]) -> None:
            """Make cards relearning.
            
            Args:
                card_ids: List of card IDs to set to relearning
            """
            card_ids = [int(card_id) for card_id in card_ids]
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
        async def set_due_date(ctx: Context, card_ids: list[Union[str, int]], days: str) -> bool:
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
            card_ids = [int(card_id) for card_id in card_ids]
            return await self.anki_request("setDueDate", {
                "cards": card_ids,
                "days": days
            })

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
                    - modelName: str - New model name (GUI's Change Note Type)
                    - fields: Dict[str, str] - New field values
                    - tags: Optional[list[str]] - New tags
            """
            return await self.anki_request("updateNoteModel", {"note": note})

        @self.mcp.tool()
        async def clear_unused_tags(ctx: Context) -> None:
            """Remove all unused tags."""
            return await self.anki_request("clearUnusedTags")

        @self.mcp.tool()
        async def replace_tags(ctx: Context, replace_all: bool = False, note_ids: Optional[list[Union[str, int]]] = None, tag_to_replace: str = None, replace_with_tag: str = None) -> None:
            """Replace tags in specific notes or all notes.
            
            Args:
                replace_all: If True, replace tags in all notes
                note_ids: List of note IDs to modify
                tag_to_replace: Tag to replace
                replace_with_tag: New tag
            """
            if replace_all:
                return await self.anki_request("replaceTagsInAllNotes", {
                    "tag_to_replace": tag_to_replace,
                    "replace_with_tag": replace_with_tag
                })
            else:
                note_ids = [int(note_id) for note_id in note_ids]
                return await self.anki_request("replaceTags", {
                    "notes": note_ids,
                    "tag_to_replace": tag_to_replace,
                    "replace_with_tag": replace_with_tag
                })

        @self.mcp.tool()
        async def get_notes_info(ctx: Context, note_ids: Optional[list[Union[str, int]]] = None, query: Optional[str] = None) -> list[Dict[str, Any]]:
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
                note_ids = [int(note_id) for note_id in note_ids]
                params["notes"] = note_ids
            if query is not None:
                params["query"] = query
            return await self.anki_request("notesInfo", params)

        @self.mcp.tool()
        async def get_notes_mod_time(ctx: Context, note_ids: list[Union[str, int]]) -> list[Dict[str, Any]]:
            """Get modification times for notes.
            
            Args:
                note_ids: List of note IDs
            
            Returns:
                List of objects containing:
                    - noteId: int
                    - mod: int (modification timestamp)
            """
            note_ids = [int(note_id) for note_id in note_ids]
            return await self.anki_request("notesModTime", {"notes": note_ids})

        @self.mcp.tool()
        async def delete_empty_notes(ctx: Context) -> None:
            """Remove all empty notes."""
            return await self.anki_request("removeEmptyNotes")

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
        async def search_media_files(ctx: Context, pattern: str = "") -> list[str]:
            """Search for media files in Anki's media folder.
            
            Args:
                pattern: Optional pattern to filter files (e.g., "*.jpg")
            """
            return await self.anki_request("getMediaFilesNames", {"pattern": pattern})

        @self.mcp.tool()
        async def delete_media_file(ctx: Context, filename: str) -> None:
            """Delete a media file from Anki's media folder."""
            return await self.anki_request("deleteMediaFile", {"filename": filename})

        @self.mcp.tool()
        async def delete_deck(ctx: Context, deck_name: str, delete_cards_too: bool = False) -> None:
            """Delete a deck."""
            return await self.anki_request("deleteDecks", {"decks": [deck_name], "cardsToo": delete_cards_too})

        # GUI
        @self.mcp.tool()
        async def get_current_card(ctx: Context) -> str:
            """Get the current card."""
            current_card = await self.anki_request("guiCurrentCard")
            return json.dumps(current_card)

    def run(self):
        """Run the MCP server."""
        self.mcp.run()

def main():
    """Run the MCP server."""
    server = AnkiServer()
    server.run()


if __name__ == "__main__":
    main() 