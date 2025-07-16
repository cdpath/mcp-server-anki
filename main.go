package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

var (
	httpAddr       = flag.String("http", "", "if set, use streamable HTTP at this address, instead of stdin/stdout")
	ankiConnectURL = flag.String("anki-connect", "http://localhost:8765", "AnkiConnect URL")
)

type AnkiServer struct {
	ankiConnectURL string
	client         *http.Client
}

type AnkiRequest struct {
	Action  string      `json:"action"`
	Version int         `json:"version"`
	Params  interface{} `json:"params"`
}

type AnkiResponse struct {
	Result interface{} `json:"result"`
	Error  string      `json:"error,omitempty"`
}

func NewAnkiServer(ankiConnectURL string) *AnkiServer {
	return &AnkiServer{
		ankiConnectURL: ankiConnectURL,
		client:         &http.Client{Timeout: 30 * time.Second},
	}
}

func (s *AnkiServer) ankiRequest(ctx context.Context, action string, params interface{}) (interface{}, error) {
	if params == nil {
		params = map[string]interface{}{}
	}
	req := AnkiRequest{
		Action:  action,
		Version: 6,
		Params:  params,
	}

	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", s.ankiConnectURL, strings.NewReader(string(reqBody)))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := s.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	var ankiResp AnkiResponse
	if err := json.NewDecoder(resp.Body).Decode(&ankiResp); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	if ankiResp.Error != "" {
		return nil, fmt.Errorf("AnkiConnect error: %s", ankiResp.Error)
	}

	return ankiResp.Result, nil
}

func parseIDsFromPath(path string) []string {
	if path == "" {
		return nil
	}
	parts := strings.Split(path, ",")
	var ids []string
	for _, part := range parts {
		if trimmed := strings.TrimSpace(part); trimmed != "" {
			ids = append(ids, trimmed)
		}
	}
	return ids
}

func encodeCursor(data map[string]interface{}) (string, error) {
	jsonData, err := json.Marshal(data)
	if err != nil {
		return "", err
	}
	return base64.StdEncoding.EncodeToString(jsonData), nil
}

func decodeCursor(cursor string) (map[string]interface{}, error) {
	data, err := base64.StdEncoding.DecodeString(cursor)
	if err != nil {
		return nil, fmt.Errorf("invalid cursor: %w", err)
	}
	var result map[string]interface{}
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, fmt.Errorf("invalid cursor: %w", err)
	}
	return result, nil
}

func paginateList(items []interface{}, cursor string, pageSize int) (map[string]interface{}, error) {
	startIndex := 0
	if cursor != "" {
		cursorData, err := decodeCursor(cursor)
		if err != nil {
			return nil, err
		}
		if startIdx, ok := cursorData["start_index"].(float64); ok {
			startIndex = int(startIdx)
		}
	}

	endIndex := startIndex + pageSize
	if endIndex > len(items) {
		endIndex = len(items)
	}

	pageItems := items[startIndex:endIndex]
	result := map[string]interface{}{
		"items": pageItems,
	}

	if endIndex < len(items) {
		nextCursorData := map[string]interface{}{"start_index": endIndex}
		nextCursor, err := encodeCursor(nextCursorData)
		if err != nil {
			return nil, err
		}
		result["nextCursor"] = nextCursor
	}

	return result, nil
}

// Tool argument types
type SearchArgs struct {
	Query      string `json:"query"`
	SearchType string `json:"search_type"`
	Cursor     string `json:"cursor,omitempty"`
}

type CreateNotesArgs struct {
	Notes []map[string]interface{} `json:"notes"`
}

type UpdateNoteArgs struct {
	Note map[string]interface{} `json:"note"`
}

type ManageTagsArgs struct {
	Action         string        `json:"action"`
	NoteIDs        []interface{} `json:"note_ids"`
	Tags           string        `json:"tags"`
	TagToReplace   string        `json:"tag_to_replace,omitempty"`
	ReplaceWithTag string        `json:"replace_with_tag,omitempty"`
}

type ChangeCardStateArgs struct {
	Action      string        `json:"action"`
	CardIDs     []interface{} `json:"card_ids"`
	Days        string        `json:"days,omitempty"`
	EaseFactors []int         `json:"ease_factors,omitempty"`
}

type GUIControlArgs struct {
	Action string `json:"action"`
	Ease   *int   `json:"ease,omitempty"`
}

type DeleteNotesArgs struct {
	NoteIDs []interface{} `json:"note_ids"`
}

type UpdateDeckConfigArgs struct {
	Config map[string]interface{} `json:"config"`
}

// Tool handlers
func (s *AnkiServer) handleSearch(ctx context.Context, ss *mcp.ServerSession, params *mcp.CallToolParamsFor[SearchArgs]) (*mcp.CallToolResult, error) {
	args := params.Arguments

	if args.SearchType != "cards" && args.SearchType != "notes" {
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: "search_type must be 'cards' or 'notes'"}},
			IsError: true,
		}, nil
	}

	var resultIDs []int
	var data []interface{}

	if args.SearchType == "cards" {
		ids, err := s.ankiRequest(ctx, "findCards", map[string]interface{}{"query": args.Query})
		if err != nil {
			return &mcp.CallToolResult{
				Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Error finding cards: %v", err)}},
				IsError: true,
			}, nil
		}
		if ids == nil {
			resultIDs = []int{}
		} else {
			idsSlice, ok := ids.([]interface{})
			if !ok {
				return &mcp.CallToolResult{
					Content: []mcp.Content{&mcp.TextContent{Text: "Unexpected response format from findCards"}},
					IsError: true,
				}, nil
			}
			resultIDs = make([]int, len(idsSlice))
			for i, v := range idsSlice {
				// AnkiConnect always returns numbers as float64
				if f, ok := v.(float64); ok {
					resultIDs[i] = int(f)
				} else {
					return &mcp.CallToolResult{
						Content: []mcp.Content{&mcp.TextContent{Text: "Non-numeric ID in findCards result"}},
						IsError: true,
					}, nil
				}
			}
		}

		if len(resultIDs) == 0 {
			data = []interface{}{}
		} else {
			cardsData, err := s.ankiRequest(ctx, "cardsInfo", map[string]interface{}{"cards": resultIDs})
			if err != nil {
				return &mcp.CallToolResult{
					Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Error getting cards info: %v", err)}},
					IsError: true,
				}, nil
			}
			if cardsData == nil {
				data = []interface{}{}
			} else {
				if cardsSlice, ok := cardsData.([]interface{}); ok {
					data = cardsSlice
				} else {
					return &mcp.CallToolResult{
						Content: []mcp.Content{&mcp.TextContent{Text: "Unexpected response format from cardsInfo"}},
						IsError: true,
					}, nil
				}
			}
		}
	} else {
		ids, err := s.ankiRequest(ctx, "findNotes", map[string]interface{}{"query": args.Query})
		if err != nil {
			return &mcp.CallToolResult{
				Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Error finding notes: %v", err)}},
				IsError: true,
			}, nil
		}
		if ids == nil {
			resultIDs = []int{}
		} else {
			idsSlice, ok := ids.([]interface{})
			if !ok {
				return &mcp.CallToolResult{
					Content: []mcp.Content{&mcp.TextContent{Text: "Unexpected response format from findNotes"}},
					IsError: true,
				}, nil
			}
			resultIDs = make([]int, len(idsSlice))
			for i, v := range idsSlice {
				// AnkiConnect always returns numbers as float64
				if f, ok := v.(float64); ok {
					resultIDs[i] = int(f)
				} else {
					return &mcp.CallToolResult{
						Content: []mcp.Content{&mcp.TextContent{Text: "Non-numeric ID in findNotes result"}},
						IsError: true,
					}, nil
				}
			}
		}

		if len(resultIDs) == 0 {
			data = []interface{}{}
		} else {
			notesData, err := s.ankiRequest(ctx, "notesInfo", map[string]interface{}{"notes": resultIDs})
			if err != nil {
				return &mcp.CallToolResult{
					Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Error getting notes info: %v", err)}},
					IsError: true,
				}, nil
			}
			if notesData == nil {
				data = []interface{}{}
			} else {
				if notesSlice, ok := notesData.([]interface{}); ok {
					data = notesSlice
				} else {
					return &mcp.CallToolResult{
						Content: []mcp.Content{&mcp.TextContent{Text: "Unexpected response format from notesInfo"}},
						IsError: true,
					}, nil
				}
			}
		}
	}

	paginated, err := paginateList(data, args.Cursor, 100)
	if err != nil {
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Error paginating results: %v", err)}},
			IsError: true,
		}, nil
	}

	result := map[string]interface{}{
		"search_type": args.SearchType,
		"query":       args.Query,
		"total_found": len(resultIDs),
		"items":       paginated["items"],
		"nextCursor":  paginated["nextCursor"],
	}

	resultJSON, _ := json.Marshal(result)
	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: string(resultJSON)}},
	}, nil
}

func (s *AnkiServer) handleCreateNotes(ctx context.Context, ss *mcp.ServerSession, params *mcp.CallToolParamsFor[CreateNotesArgs]) (*mcp.CallToolResult, error) {
	args := params.Arguments

	result, err := s.ankiRequest(ctx, "addNotes", map[string]interface{}{"notes": args.Notes})
	if err != nil {
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Error creating notes: %v", err)}},
			IsError: true,
		}, nil
	}

	resultJSON, _ := json.Marshal(result)
	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: string(resultJSON)}},
	}, nil
}

func (s *AnkiServer) handleUpdateNote(ctx context.Context, ss *mcp.ServerSession, params *mcp.CallToolParamsFor[UpdateNoteArgs]) (*mcp.CallToolResult, error) {
	args := params.Arguments

	_, err := s.ankiRequest(ctx, "updateNote", map[string]interface{}{"note": args.Note})
	if err != nil {
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Error updating note: %v", err)}},
			IsError: true,
		}, nil
	}

	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: "Note updated successfully"}},
	}, nil
}

func (s *AnkiServer) handleManageTags(ctx context.Context, ss *mcp.ServerSession, params *mcp.CallToolParamsFor[ManageTagsArgs]) (*mcp.CallToolResult, error) {
	args := params.Arguments

	// Convert note IDs to integers
	var noteIDs []int
	for _, id := range args.NoteIDs {
		switch v := id.(type) {
		case string:
			if intID, err := strconv.Atoi(v); err == nil {
				noteIDs = append(noteIDs, intID)
			}
		case float64:
			noteIDs = append(noteIDs, int(v))
		case int:
			noteIDs = append(noteIDs, v)
		}
	}

	var err error
	switch args.Action {
	case "add":
		_, err = s.ankiRequest(ctx, "addTags", map[string]interface{}{"notes": noteIDs, "tags": args.Tags})
	case "delete":
		_, err = s.ankiRequest(ctx, "removeTags", map[string]interface{}{"notes": noteIDs, "tags": args.Tags})
	case "replace":
		_, err = s.ankiRequest(ctx, "replaceTags", map[string]interface{}{
			"notes":            noteIDs,
			"tag_to_replace":   args.TagToReplace,
			"replace_with_tag": args.ReplaceWithTag,
		})
	default:
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Invalid action: %s. Must be 'add', 'delete', or 'replace'", args.Action)}},
			IsError: true,
		}, nil
	}

	if err != nil {
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Error managing tags: %v", err)}},
			IsError: true,
		}, nil
	}

	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: "Tags managed successfully"}},
	}, nil
}

func (s *AnkiServer) handleChangeCardState(ctx context.Context, ss *mcp.ServerSession, params *mcp.CallToolParamsFor[ChangeCardStateArgs]) (*mcp.CallToolResult, error) {
	args := params.Arguments

	// Convert card IDs to integers
	var cardIDs []int
	for _, id := range args.CardIDs {
		switch v := id.(type) {
		case string:
			if intID, err := strconv.Atoi(v); err == nil {
				cardIDs = append(cardIDs, intID)
			}
		case float64:
			cardIDs = append(cardIDs, int(v))
		case int:
			cardIDs = append(cardIDs, v)
		}
	}

	var result interface{}
	var err error

	switch args.Action {
	case "suspend":
		result, err = s.ankiRequest(ctx, "suspend", map[string]interface{}{"cards": cardIDs})
	case "unsuspend":
		result, err = s.ankiRequest(ctx, "unsuspend", map[string]interface{}{"cards": cardIDs})
	case "forget":
		_, err = s.ankiRequest(ctx, "forgetCards", map[string]interface{}{"cards": cardIDs})
		result = true
	case "relearn":
		_, err = s.ankiRequest(ctx, "relearnCards", map[string]interface{}{"cards": cardIDs})
		result = true
	case "set_due":
		if args.Days == "" {
			return &mcp.CallToolResult{
				Content: []mcp.Content{&mcp.TextContent{Text: "days parameter required for set_due action"}},
				IsError: true,
			}, nil
		}
		result, err = s.ankiRequest(ctx, "setDueDate", map[string]interface{}{"cards": cardIDs, "days": args.Days})
	case "set_ease":
		if len(args.EaseFactors) != len(cardIDs) {
			return &mcp.CallToolResult{
				Content: []mcp.Content{&mcp.TextContent{Text: "ease_factors must match card_ids length for set_ease action"}},
				IsError: true,
			}, nil
		}
		result, err = s.ankiRequest(ctx, "setEaseFactors", map[string]interface{}{"cards": cardIDs, "easeFactors": args.EaseFactors})
	default:
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Invalid action: %s", args.Action)}},
			IsError: true,
		}, nil
	}

	if err != nil {
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Error changing card state: %v", err)}},
			IsError: true,
		}, nil
	}

	resultJSON, _ := json.Marshal(result)
	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: string(resultJSON)}},
	}, nil
}

func (s *AnkiServer) handleGUIControl(ctx context.Context, ss *mcp.ServerSession, params *mcp.CallToolParamsFor[GUIControlArgs]) (*mcp.CallToolResult, error) {
	args := params.Arguments

	var result interface{}
	var err error

	switch args.Action {
	case "current_card":
		result, err = s.ankiRequest(ctx, "guiCurrentCard", nil)
	case "show_answer":
		result, err = s.ankiRequest(ctx, "guiShowAnswer", nil)
	case "answer":
		if args.Ease == nil {
			return &mcp.CallToolResult{
				Content: []mcp.Content{&mcp.TextContent{Text: "ease parameter required for answer action"}},
				IsError: true,
			}, nil
		}
		if *args.Ease < 1 || *args.Ease > 4 {
			return &mcp.CallToolResult{
				Content: []mcp.Content{&mcp.TextContent{Text: "ease must be 1 (Again), 2 (Hard), 3 (Good), or 4 (Easy)"}},
				IsError: true,
			}, nil
		}
		// Ensure the card is on the answer side
		_, err = s.ankiRequest(ctx, "guiShowAnswer", nil)
		if err != nil {
			return &mcp.CallToolResult{
				Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Error showing answer: %v", err)}},
				IsError: true,
			}, nil
		}
		result, err = s.ankiRequest(ctx, "guiAnswerCard", map[string]interface{}{"ease": *args.Ease})
	case "undo":
		result, err = s.ankiRequest(ctx, "guiUndo", nil)
	default:
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Invalid action: %s. Available actions are: current_card, show_answer, answer, undo", args.Action)}},
			IsError: true,
		}, nil
	}

	if err != nil {
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Error in GUI control: %v", err)}},
			IsError: true,
		}, nil
	}

	resultJSON, _ := json.Marshal(result)
	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: string(resultJSON)}},
	}, nil
}

func (s *AnkiServer) handleDeleteNotes(ctx context.Context, ss *mcp.ServerSession, params *mcp.CallToolParamsFor[DeleteNotesArgs]) (*mcp.CallToolResult, error) {
	args := params.Arguments

	// Convert note IDs to integers
	var noteIDs []int
	for _, id := range args.NoteIDs {
		switch v := id.(type) {
		case string:
			if intID, err := strconv.Atoi(v); err == nil {
				noteIDs = append(noteIDs, intID)
			}
		case float64:
			noteIDs = append(noteIDs, int(v))
		case int:
			noteIDs = append(noteIDs, v)
		}
	}

	_, err := s.ankiRequest(ctx, "deleteNotes", map[string]interface{}{"notes": noteIDs})
	if err != nil {
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Error deleting notes: %v", err)}},
			IsError: true,
		}, nil
	}

	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: "Notes deleted successfully"}},
	}, nil
}

func (s *AnkiServer) handleUpdateDeckConfig(ctx context.Context, ss *mcp.ServerSession, params *mcp.CallToolParamsFor[UpdateDeckConfigArgs]) (*mcp.CallToolResult, error) {
	args := params.Arguments

	result, err := s.ankiRequest(ctx, "saveDeckConfig", map[string]interface{}{"config": args.Config})
	if err != nil {
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("Error updating deck config: %v", err)}},
			IsError: true,
		}, nil
	}

	resultJSON, _ := json.Marshal(result)
	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: string(resultJSON)}},
	}, nil
}

func (s *AnkiServer) handleAllDecks(ctx context.Context, ss *mcp.ServerSession, params *mcp.ReadResourceParams) (*mcp.ReadResourceResult, error) {
	decks, err := s.ankiRequest(ctx, "deckNamesAndIds", nil)
	if err != nil {
		return nil, err
	}

	if decks == nil {
		decks = map[string]interface{}{}
	}

	deckMap, ok := decks.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response format from deckNamesAndIds")
	}

	var deckList []map[string]interface{}
	for name, id := range deckMap {
		deckList = append(deckList, map[string]interface{}{
			"name": name,
			"id":   id,
		})
	}

	data, _ := json.Marshal(deckList)
	return &mcp.ReadResourceResult{
		Contents: []*mcp.ResourceContents{
			{URI: params.URI, MIMEType: "application/json", Text: string(data)},
		},
	}, nil
}

func (s *AnkiServer) handleDeckConfig(ctx context.Context, ss *mcp.ServerSession, params *mcp.ReadResourceParams) (*mcp.ReadResourceResult, error) {
	// Extract deck_id from URI
	uri := params.URI
	deckID := strings.TrimPrefix(uri, "anki://decks/")
	deckID = strings.TrimSuffix(deckID, "/config")

	var config interface{}
	var err error

	// Try as ID first if it looks numeric, otherwise try as name
	if _, err := strconv.Atoi(deckID); err == nil {
		config, err = s.ankiRequest(ctx, "getDeckConfig", map[string]interface{}{"deck": deckID})
	} else {
		config, err = s.ankiRequest(ctx, "getDeckConfig", map[string]interface{}{"deck": deckID})
	}

	if err != nil {
		return nil, err
	}

	if config == nil {
		config = map[string]interface{}{}
	}

	data, _ := json.Marshal(config)
	return &mcp.ReadResourceResult{
		Contents: []*mcp.ResourceContents{
			{URI: params.URI, MIMEType: "application/json", Text: string(data)},
		},
	}, nil
}

func (s *AnkiServer) handleDeckStats(ctx context.Context, ss *mcp.ServerSession, params *mcp.ReadResourceParams) (*mcp.ReadResourceResult, error) {
	// Extract deck_id from URI
	uri := params.URI
	deckID := strings.TrimPrefix(uri, "anki://decks/")
	deckID = strings.TrimSuffix(deckID, "/stats")

	stats, err := s.ankiRequest(ctx, "getDeckStats", map[string]interface{}{"decks": []string{deckID}})
	if err != nil {
		return nil, err
	}

	if stats == nil {
		stats = map[string]interface{}{}
	}

	data, _ := json.Marshal(stats)
	return &mcp.ReadResourceResult{
		Contents: []*mcp.ResourceContents{
			{URI: params.URI, MIMEType: "application/json", Text: string(data)},
		},
	}, nil
}

func (s *AnkiServer) handleAllModels(ctx context.Context, ss *mcp.ServerSession, params *mcp.ReadResourceParams) (*mcp.ReadResourceResult, error) {
	modelNamesAndIDs, err := s.ankiRequest(ctx, "modelNamesAndIds", nil)
	if err != nil {
		return nil, err
	}

	if modelNamesAndIDs == nil {
		modelNamesAndIDs = map[string]interface{}{}
	}

	modelMap, ok := modelNamesAndIDs.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response format from modelNamesAndIds")
	}

	var modelIDs []interface{}
	for _, id := range modelMap {
		modelIDs = append(modelIDs, id)
	}

	models, err := s.ankiRequest(ctx, "findModelsById", map[string]interface{}{"modelIds": modelIDs})
	if err != nil {
		return nil, err
	}

	if models == nil {
		models = []interface{}{}
	}

	data, _ := json.Marshal(models)
	return &mcp.ReadResourceResult{
		Contents: []*mcp.ResourceContents{
			{URI: params.URI, MIMEType: "application/json", Text: string(data)},
		},
	}, nil
}

func (s *AnkiServer) handleModelInfo(ctx context.Context, ss *mcp.ServerSession, params *mcp.ReadResourceParams) (*mcp.ReadResourceResult, error) {
	// Extract model_name from URI
	uri := params.URI
	modelName := strings.TrimPrefix(uri, "anki://models/")

	fieldsOnTemplates, err := s.ankiRequest(ctx, "modelFieldsOnTemplates", map[string]interface{}{"modelName": modelName})
	if err != nil {
		return nil, err
	}

	if fieldsOnTemplates == nil {
		fieldsOnTemplates = map[string]interface{}{}
	}

	data, _ := json.Marshal(fieldsOnTemplates)
	return &mcp.ReadResourceResult{
		Contents: []*mcp.ResourceContents{
			{URI: params.URI, MIMEType: "application/json", Text: string(data)},
		},
	}, nil
}

func (s *AnkiServer) handleCardsInfo(ctx context.Context, ss *mcp.ServerSession, params *mcp.ReadResourceParams) (*mcp.ReadResourceResult, error) {
	// Extract card_ids from URI
	uri := params.URI
	cardIDsStr := strings.TrimPrefix(uri, "anki://cards/")
	cardIDsStr = strings.TrimSuffix(cardIDsStr, "/info")

	cardIDList := parseIDsFromPath(cardIDsStr)
	if len(cardIDList) == 0 {
		return nil, fmt.Errorf("no card IDs provided")
	}

	var cardIDs []int
	for _, idStr := range cardIDList {
		if id, err := strconv.Atoi(idStr); err == nil {
			cardIDs = append(cardIDs, id)
		}
	}

	cards, err := s.ankiRequest(ctx, "cardsInfo", map[string]interface{}{"cards": cardIDs})
	if err != nil {
		return nil, err
	}

	if cards == nil {
		cards = []interface{}{}
	}

	cardsData, ok := cards.([]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response format from cardsInfo")
	}

	var result interface{}
	if len(cardIDs) == 1 {
		if len(cardsData) == 0 {
			return nil, fmt.Errorf("card %d not found", cardIDs[0])
		}
		result = cardsData[0]
	} else {
		result = cardsData
	}

	data, _ := json.Marshal(result)
	return &mcp.ReadResourceResult{
		Contents: []*mcp.ResourceContents{
			{URI: params.URI, MIMEType: "application/json", Text: string(data)},
		},
	}, nil
}

func (s *AnkiServer) handleNotesInfo(ctx context.Context, ss *mcp.ServerSession, params *mcp.ReadResourceParams) (*mcp.ReadResourceResult, error) {
	// Extract note_ids from URI
	uri := params.URI
	noteIDsStr := strings.TrimPrefix(uri, "anki://notes/")
	noteIDsStr = strings.TrimSuffix(noteIDsStr, "/info")

	noteIDList := parseIDsFromPath(noteIDsStr)
	if len(noteIDList) == 0 {
		return nil, fmt.Errorf("no note IDs provided")
	}

	var noteIDs []int
	for _, idStr := range noteIDList {
		if id, err := strconv.Atoi(idStr); err == nil {
			noteIDs = append(noteIDs, id)
		}
	}

	notes, err := s.ankiRequest(ctx, "notesInfo", map[string]interface{}{"notes": noteIDs})
	if err != nil {
		return nil, err
	}

	if notes == nil {
		notes = []interface{}{}
	}

	notesData, ok := notes.([]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response format from notesInfo")
	}

	var result interface{}
	if len(noteIDs) == 1 {
		if len(notesData) == 0 {
			return nil, fmt.Errorf("note %d not found", noteIDs[0])
		}
		result = notesData[0]
	} else {
		result = notesData
	}

	data, _ := json.Marshal(result)
	return &mcp.ReadResourceResult{
		Contents: []*mcp.ResourceContents{
			{URI: params.URI, MIMEType: "application/json", Text: string(data)},
		},
	}, nil
}

func (s *AnkiServer) handleCardsReviews(ctx context.Context, ss *mcp.ServerSession, params *mcp.ReadResourceParams) (*mcp.ReadResourceResult, error) {
	// Extract card_ids from URI
	uri := params.URI
	cardIDsStr := strings.TrimPrefix(uri, "anki://cards/")
	cardIDsStr = strings.TrimSuffix(cardIDsStr, "/reviews")

	cardIDList := parseIDsFromPath(cardIDsStr)
	if len(cardIDList) == 0 {
		return nil, fmt.Errorf("no card IDs provided")
	}

	var cardIDs []int
	for _, idStr := range cardIDList {
		if id, err := strconv.Atoi(idStr); err == nil {
			cardIDs = append(cardIDs, id)
		}
	}

	reviews, err := s.ankiRequest(ctx, "getReviewsOfCards", map[string]interface{}{"cards": cardIDs})
	if err != nil {
		return nil, err
	}

	if reviews == nil {
		reviews = []interface{}{}
	}

	data, _ := json.Marshal(reviews)
	return &mcp.ReadResourceResult{
		Contents: []*mcp.ResourceContents{
			{URI: params.URI, MIMEType: "application/json", Text: string(data)},
		},
	}, nil
}

func (s *AnkiServer) handleAllTags(ctx context.Context, ss *mcp.ServerSession, params *mcp.ReadResourceParams) (*mcp.ReadResourceResult, error) {
	tags, err := s.ankiRequest(ctx, "getTags", nil)
	if err != nil {
		return nil, err
	}

	if tags == nil {
		tags = []interface{}{}
	}

	data, _ := json.Marshal(tags)
	return &mcp.ReadResourceResult{
		Contents: []*mcp.ResourceContents{
			{URI: params.URI, MIMEType: "application/json", Text: string(data)},
		},
	}, nil
}

func (s *AnkiServer) handleCurrentSession(ctx context.Context, ss *mcp.ServerSession, params *mcp.ReadResourceParams) (*mcp.ReadResourceResult, error) {
	currentCard, err := s.ankiRequest(ctx, "guiCurrentCard", nil)
	if err != nil {
		return nil, err
	}

	result := map[string]interface{}{
		"current_card": currentCard,
		"timestamp":    time.Now().Unix(),
	}

	data, _ := json.Marshal(result)
	return &mcp.ReadResourceResult{
		Contents: []*mcp.ResourceContents{
			{URI: params.URI, MIMEType: "application/json", Text: string(data)},
		},
	}, nil
}

func (s *AnkiServer) handleCollectionStats(ctx context.Context, ss *mcp.ServerSession, params *mcp.ReadResourceParams) (*mcp.ReadResourceResult, error) {
	statsHTML, err := s.ankiRequest(ctx, "getCollectionStatsHTML", map[string]interface{}{"wholeCollection": true})
	if err != nil {
		return nil, err
	}

	if statsHTML == nil {
		statsHTML = ""
	}

	result := map[string]interface{}{
		"stats_html":   statsHTML,
		"generated_at": time.Now().Unix(),
	}

	data, _ := json.Marshal(result)
	return &mcp.ReadResourceResult{
		Contents: []*mcp.ResourceContents{
			{URI: params.URI, MIMEType: "application/json", Text: string(data)},
		},
	}, nil
}

func (s *AnkiServer) handleDailyStats(ctx context.Context, ss *mcp.ServerSession, params *mcp.ReadResourceParams) (*mcp.ReadResourceResult, error) {
	todayReviews, err := s.ankiRequest(ctx, "getNumCardsReviewedToday", nil)
	if err != nil {
		return nil, err
	}

	if todayReviews == nil {
		todayReviews = 0
	}

	result := map[string]interface{}{
		"today": todayReviews,
		"date":  time.Now().Format("2006-01-02"),
	}

	data, _ := json.Marshal(result)
	return &mcp.ReadResourceResult{
		Contents: []*mcp.ResourceContents{
			{URI: params.URI, MIMEType: "application/json", Text: string(data)},
		},
	}, nil
}

func main() {
	flag.Parse()

	ankiServer := NewAnkiServer(*ankiConnectURL)

	// Create MCP server
	server := mcp.NewServer(&mcp.Implementation{
		Name:    "Anki MCP",
		Version: "0.2.0",
	}, &mcp.ServerOptions{
		Instructions: "Anki MCP server providing access to Anki flashcards via AnkiConnect",
	})

	// Add tools
	mcp.AddTool(server, &mcp.Tool{
		Name:        "anki_search",
		Description: "Search cards or notes using Anki's search syntax with pagination",
	}, ankiServer.handleSearch)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "anki_create_notes",
		Description: "Create one or more notes in Anki",
	}, ankiServer.handleCreateNotes)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "anki_update_note",
		Description: "Update a note's fields and/or tags",
	}, ankiServer.handleUpdateNote)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "anki_manage_tags",
		Description: "Manage tags on notes",
	}, ankiServer.handleManageTags)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "anki_change_card_state",
		Description: "Change card states and properties",
	}, ankiServer.handleChangeCardState)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "anki_gui_control",
		Description: "Control Anki GUI for interactive learning",
	}, ankiServer.handleGUIControl)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "anki_delete_notes",
		Description: "Delete notes by their IDs",
	}, ankiServer.handleDeleteNotes)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "anki_update_deck_config",
		Description: "Update deck configuration",
	}, ankiServer.handleUpdateDeckConfig)

	// Add resources
	server.AddResource(&mcp.Resource{
		Name:        "all_decks",
		Description: "Get all deck names and IDs",
		URI:         "anki://decks",
		MIMEType:    "application/json",
	}, ankiServer.handleAllDecks)

	server.AddResourceTemplate(&mcp.ResourceTemplate{
		Name:        "deck_config",
		Description: "Get configuration of specific deck by ID or name",
		URITemplate: "anki://decks/{deck_id}/config",
		MIMEType:    "application/json",
	}, ankiServer.handleDeckConfig)

	server.AddResourceTemplate(&mcp.ResourceTemplate{
		Name:        "deck_stats",
		Description: "Get statistics for a deck by deck_id",
		URITemplate: "anki://decks/{deck_id}/stats",
		MIMEType:    "application/json",
	}, ankiServer.handleDeckStats)

	server.AddResource(&mcp.Resource{
		Name:        "all_models",
		Description: "Get all note models with their templates and fields",
		URI:         "anki://models",
		MIMEType:    "application/json",
	}, ankiServer.handleAllModels)

	server.AddResourceTemplate(&mcp.ResourceTemplate{
		Name:        "model_info",
		Description: "Get model info for a specific model, including templates and fields",
		URITemplate: "anki://models/{model_name}",
		MIMEType:    "application/json",
	}, ankiServer.handleModelInfo)

	server.AddResourceTemplate(&mcp.ResourceTemplate{
		Name:        "cards_info",
		Description: "Get information about one or more cards (comma-separated IDs)",
		URITemplate: "anki://cards/{card_ids}/info",
		MIMEType:    "application/json",
	}, ankiServer.handleCardsInfo)

	server.AddResourceTemplate(&mcp.ResourceTemplate{
		Name:        "notes_info",
		Description: "Get information about one or more notes (comma-separated IDs)",
		URITemplate: "anki://notes/{note_ids}/info",
		MIMEType:    "application/json",
	}, ankiServer.handleNotesInfo)

	server.AddResourceTemplate(&mcp.ResourceTemplate{
		Name:        "cards_reviews",
		Description: "Get review history for one or more cards (comma-separated IDs)",
		URITemplate: "anki://cards/{card_ids}/reviews",
		MIMEType:    "application/json",
	}, ankiServer.handleCardsReviews)

	server.AddResource(&mcp.Resource{
		Name:        "all_tags",
		Description: "Get all available tags",
		URI:         "anki://tags",
		MIMEType:    "application/json",
	}, ankiServer.handleAllTags)

	server.AddResource(&mcp.Resource{
		Name:        "current_session",
		Description: "Get current learning session state including current card",
		URI:         "anki://session/current",
		MIMEType:    "application/json",
	}, ankiServer.handleCurrentSession)

	server.AddResource(&mcp.Resource{
		Name:        "collection_stats",
		Description: "Get collection statistics in HTML format",
		URI:         "anki://collection/stats",
		MIMEType:    "application/json",
	}, ankiServer.handleCollectionStats)

	server.AddResource(&mcp.Resource{
		Name:        "daily_stats",
		Description: "Get daily review statistics",
		URI:         "anki://stats/daily",
		MIMEType:    "application/json",
	}, ankiServer.handleDailyStats)

	// Start server with appropriate transport
	if *httpAddr != "" {
		handler := mcp.NewStreamableHTTPHandler(func(*http.Request) *mcp.Server {
			return server
		}, nil)
		log.Printf("MCP handler listening at %s", *httpAddr)
		http.ListenAndServe(*httpAddr, handler)
	} else {
		t := mcp.NewStdioTransport()
		if err := server.Run(context.Background(), t); err != nil {
			log.Printf("Server failed: %v", err)
		}
	}
}
