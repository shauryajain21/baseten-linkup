# Linkup + OpenAI Integration Test Results

**Date:** November 22, 2025
**Test Script:** `test_linkup_openai.py`

## Overview

This document summarizes the testing of the Linkup + OpenAI-compatible integration for tool calling functionality. The integration allows an LLM to use Linkup's web search API as a function/tool to retrieve real-time information.

## Test Configuration

| Setting | Value |
|---------|-------|
| LLM Provider | Baseten (OpenAI-compatible endpoint) |
| Model | `deepseek-ai/DeepSeek-V3-0324` |
| Search Provider | Linkup API |
| Search Depth | `standard` |
| Output Type | `searchResults` |

## Tool Schema

```json
{
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the web for current information using Linkup...",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find information on the web"
                }
            },
            "required": ["query"]
        }
    }
}
```

## Test Queries

The following queries were designed to test tool calling behavior:

### Queries Expected to Trigger Tool Calling (Real-time Data)

| Query | Expected Behavior | Result |
|-------|-------------------|--------|
| "What are the latest developments in AI this week?" | Should trigger `search_web` | API Auth Error |
| "What is the current price of Bitcoin?" | Should trigger `search_web` | API Auth Error |
| "What's happening in the news today?" | Should trigger `search_web` | API Auth Error |
| "What are the top trending topics on social media right now?" | Should trigger `search_web` | API Auth Error |

### Queries That May Trigger Tool Calling (Context Dependent)

| Query | Expected Behavior | Result |
|-------|-------------------|--------|
| "Who won the most recent Super Bowl?" | May trigger `search_web` | API Auth Error |

### Queries Expected to Use Direct Response (General Knowledge)

| Query | Expected Behavior | Result |
|-------|-------------------|--------|
| "Explain how photosynthesis works" | Direct LLM response | API Auth Error |
| "What is the capital of France?" | Direct LLM response | API Auth Error |

## Test Results Summary

| Metric | Value |
|--------|-------|
| Total Queries | 7 |
| Tool Calling Triggered | 0 |
| Direct Responses | 0 |
| Errors | 7 |

### Error Details

All tests failed with authentication errors:

- **Baseten API:** `PermissionDeniedError: Access denied`
- **Linkup API:** `Access denied`

## Root Cause

The API keys provided appear to be invalid or expired. Both services returned authentication errors when tested via:
1. Python SDK calls
2. Direct curl requests

## Required Actions

To successfully run the integration tests:

1. **Get Valid Linkup API Key:**
   - Sign up at [Linkup](https://linkup.so)
   - Generate a new API key from the dashboard

2. **Get Valid Baseten API Key:**
   - Sign up at [Baseten](https://baseten.co)
   - Generate a new API key with access to DeepSeek-V3 model

3. **Update `.env` file:**
   ```
   BASETEN_API_KEY=your_valid_baseten_key
   LINKUP_API_KEY=your_valid_linkup_key
   ```

4. **Re-run tests:**
   ```bash
   python test_linkup_openai.py
   ```

## Integration Architecture

```
User Query
    |
    v
+-------------------+
|   OpenAI Client   |  (Baseten endpoint)
|   (DeepSeek-V3)   |
+-------------------+
    |
    | tool_calls: search_web(query)
    v
+-------------------+
|   Linkup Client   |
|   Web Search API  |
+-------------------+
    |
    | Search Results (JSON)
    v
+-------------------+
|   OpenAI Client   |  (Second call with results)
|   Final Response  |
+-------------------+
    |
    v
Final Answer to User
```

## Code Reference

The test script `test_linkup_openai.py` implements:

1. **Tool Definition** (lines 36-51): OpenAI function schema for `search_web`
2. **Search Execution** (lines 54-65): Linkup API call wrapper
3. **Query Runner** (lines 69-133): Main logic handling tool calls
4. **Test Suite** (lines 136-190): Batch testing with result collection

## Expected Behavior (With Valid Keys)

When running with valid API keys, the expected flow is:

1. User asks "What is the current price of Bitcoin?"
2. LLM recognizes this requires real-time data
3. LLM generates tool call: `search_web(query="Bitcoin current price")`
4. Linkup executes web search, returns results
5. Results passed back to LLM as tool response
6. LLM synthesizes final answer with current price data

## Alternative: Using OpenAI Directly

If you have an OpenAI API key instead of Baseten, modify `test_linkup_openai.py`:

```python
# Replace Baseten client initialization with:
openai_client = OpenAI(api_key="your_openai_api_key")

# Update MODEL to use GPT-4o:
MODEL = "gpt-4o"
```

---

*This document will be updated with actual test results once valid API keys are provided.*
