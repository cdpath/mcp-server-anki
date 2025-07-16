package main

import (
	"context"
	"testing"
	"time"
)

func TestNewAnkiServer(t *testing.T) {
	server := NewAnkiServer("http://localhost:8765")
	if server == nil {
		t.Fatal("NewAnkiServer returned nil")
	}
	if server.ankiConnectURL != "http://localhost:8765" {
		t.Errorf("Expected ankiConnectURL to be 'http://localhost:8765', got '%s'", server.ankiConnectURL)
	}
	if server.client == nil {
		t.Fatal("HTTP client is nil")
	}
}

func TestParseIDsFromPath(t *testing.T) {
	tests := []struct {
		input    string
		expected []string
	}{
		{"", nil},
		{"123", []string{"123"}},
		{"123,456", []string{"123", "456"}},
		{"123, 456, 789", []string{"123", "456", "789"}},
		{"123, , 456", []string{"123", "456"}},
	}

	for _, test := range tests {
		result := parseIDsFromPath(test.input)
		if len(result) != len(test.expected) {
			t.Errorf("parseIDsFromPath(%q) returned %v, expected %v", test.input, result, test.expected)
			continue
		}
		for i, expected := range test.expected {
			if result[i] != expected {
				t.Errorf("parseIDsFromPath(%q)[%d] = %q, expected %q", test.input, i, result[i], expected)
			}
		}
	}
}

func TestCursorEncoding(t *testing.T) {
	data := map[string]interface{}{
		"start_index": 50,
		"test":        "value",
	}

	encoded, err := encodeCursor(data)
	if err != nil {
		t.Fatalf("encodeCursor failed: %v", err)
	}

	decoded, err := decodeCursor(encoded)
	if err != nil {
		t.Fatalf("decodeCursor failed: %v", err)
	}

	if decoded["start_index"].(float64) != 50 {
		t.Errorf("Expected start_index to be 50, got %v", decoded["start_index"])
	}
	if decoded["test"] != "value" {
		t.Errorf("Expected test to be 'value', got %v", decoded["test"])
	}
}

func TestPaginateList(t *testing.T) {
	items := []interface{}{"a", "b", "c", "d", "e", "f", "g", "h", "i", "j"}

	// Test first page
	result, err := paginateList(items, "", 3)
	if err != nil {
		t.Fatalf("paginateList failed: %v", err)
	}

	pageItems := result["items"].([]interface{})
	if len(pageItems) != 3 {
		t.Errorf("Expected 3 items, got %d", len(pageItems))
	}

	if pageItems[0] != "a" || pageItems[1] != "b" || pageItems[2] != "c" {
		t.Errorf("Expected items ['a', 'b', 'c'], got %v", pageItems)
	}

	// Check if nextCursor is present
	if result["nextCursor"] == nil {
		t.Error("Expected nextCursor to be present")
	}

	// Test second page
	nextCursor := result["nextCursor"].(string)
	result2, err := paginateList(items, nextCursor, 3)
	if err != nil {
		t.Fatalf("paginateList failed: %v", err)
	}

	pageItems2 := result2["items"].([]interface{})
	if len(pageItems2) != 3 {
		t.Errorf("Expected 3 items, got %d", len(pageItems2))
	}

	if pageItems2[0] != "d" || pageItems2[1] != "e" || pageItems2[2] != "f" {
		t.Errorf("Expected items ['d', 'e', 'f'], got %v", pageItems2)
	}
}

func TestAnkiRequestTimeout(t *testing.T) {
	server := NewAnkiServer("http://localhost:8765")

	// Create a context with a very short timeout
	ctx, cancel := context.WithTimeout(context.Background(), 1*time.Millisecond)
	defer cancel()

	// This should timeout quickly
	_, err := server.ankiRequest(ctx, "version", nil)
	if err == nil {
		t.Error("Expected timeout error, got nil")
	}
}
