import asyncio
import base64
import os
import unittest

from server import AnkiServer

def async_test(coro):
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper

class TestAnkiServerIntegration(unittest.TestCase):
    @async_test
    async def setUp(self):
        self.server = AnkiServer()
        self.test_deck_name = "Test_Integration_Deck"
        self.test_model_name = "Basic"  # Using Anki's default Basic model
        # Create a test deck
        await self.server.anki_request("createDeck", {"deck": self.test_deck_name})

    @async_test
    async def tearDown(self):
        if hasattr(self, 'server') and hasattr(self, 'test_deck_name'):
            # Clean up: delete test deck
            await self.server.anki_request("deleteDecks", 
                {"decks": [self.test_deck_name], "cardsToo": True})

    @async_test
    async def test_deck_operations(self):
        # Test deck creation
        deck_id = await self.server.anki_request("createDeck", {"deck": self.test_deck_name})
        self.assertIsNotNone(deck_id)

        # Test listing decks
        decks = await self.server.anki_request("deckNames")
        self.assertIn(self.test_deck_name, decks)

        # Test getting deck configuration
        config = await self.server.anki_request("getDeckConfig", {"deck": self.test_deck_name})
        self.assertIsInstance(config, dict)

    @async_test
    async def test_note_operations(self):
        # Test adding a note
        note = {
            "deckName": self.test_deck_name,
            "modelName": self.test_model_name,
            "fields": {
                "Front": "Test Front",
                "Back": "Test Back"
            },
            "tags": ["test_tag"]
        }
        note_id = await self.server.anki_request("addNote", {"note": note})
        self.assertIsInstance(note_id, int)

        # Test finding notes
        notes = await self.server.anki_request("findNotes", {"query": f"deck:{self.test_deck_name}"})
        self.assertIn(note_id, notes)

        # Test updating note fields
        new_fields = {
            "Front": "Updated Front",
            "Back": "Updated Back"
        }
        await self.server.anki_request("updateNoteFields", {
            "note": {"id": note_id, "fields": new_fields}
        })

        # Test adding and removing tags
        await self.server.anki_request("addTags", {"notes": [note_id], "tags": "new_tag"})
        await self.server.anki_request("removeTags", {"notes": [note_id], "tags": "test_tag"})

    @async_test
    async def test_card_operations(self):
        # First add a note to get a card
        note = {
            "deckName": self.test_deck_name,
            "modelName": self.test_model_name,
            "fields": {
                "Front": "Card Test Front",
                "Back": "Card Test Back"
            }
        }
        note_id = await self.server.anki_request("addNote", {"note": note})
        
        # Get cards for the note
        cards = await self.server.anki_request("findCards", {"query": f"nid:{note_id}"})
        self.assertTrue(len(cards) > 0)
        card_id = cards[0]

        # Test getting card info
        card_info = await self.server.anki_request("cardsInfo", {"cards": [card_id]})
        self.assertIsInstance(card_info, list)
        self.assertEqual(len(card_info), 1)

        # Test setting card due time using the correct API
        await self.server.anki_request("setDueDate", {
            "cards": [card_id],
            "days": "1"
        })

    @async_test
    async def test_media_operations(self):
        # Test storing a media file
        test_content = "Test content"
        test_filename = "test.txt"
        encoded_content = base64.b64encode(test_content.encode()).decode()
        
        await self.server.anki_request("storeMediaFile", {
            "filename": test_filename,
            "data": encoded_content
        })

        # Test listing media files
        files = await self.server.anki_request("getMediaFilesNames", {"pattern": "test.*"})
        self.assertIn(test_filename, files)

        # Test deleting media file
        await self.server.anki_request("deleteMediaFile", {"filename": test_filename})
        files = await self.server.anki_request("getMediaFilesNames", {"pattern": "test.*"})
        self.assertNotIn(test_filename, files)

if __name__ == "__main__":
    unittest.main() 