"""
Test script for Linkup + OpenAI Integration with Tool Calling
Based on: https://docs.linkup.so/pages/llms/openai-function-calling
"""
import os
import json
from datetime import datetime
from openai import OpenAI
from linkup import LinkupClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
LINKUP_API_KEY = os.environ.get("LINKUP_API_KEY")

if not OPENAI_API_KEY or not LINKUP_API_KEY:
    print("Error: API keys not found.")
    print(f"  OPENAI_API_KEY: {'set' if OPENAI_API_KEY else 'NOT SET'}")
    print(f"  LINKUP_API_KEY: {'set' if LINKUP_API_KEY else 'NOT SET'}")
    print("\nPlease set your API keys in a .env file or environment variables.")
    exit(1)

# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
linkup_client = LinkupClient(api_key=LINKUP_API_KEY)

# Define the function schema for OpenAI
tools = [{
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the web for current information using Linkup. Returns comprehensive content from relevant sources. Use this for any questions about current events, news, prices, or real-time data.",
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
}]


def execute_search(query: str) -> str:
    """Execute a Linkup search and return results as JSON string."""
    try:
        linkup_response = linkup_client.search(
            query=query,
            depth="standard",
            output_type="searchResults"
        )
        return json.dumps(linkup_response.model_dump(), indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def run_query(user_query: str, model: str = "gpt-4o") -> dict:
    """
    Run a single query through OpenAI with Linkup tool calling.
    Returns a dict with the query, tool calls made, and final response.
    """
    result = {
        "query": user_query,
        "model": model,
        "tool_calls": [],
        "final_response": None,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }

    try:
        # Initial messages
        messages = [
            {
                "role": "system",
                "content": f"You are a helpful assistant with access to real-time web search via the search_web function. Today is {datetime.now().strftime('%B %d, %Y')}. Use the search tool for any questions requiring current information."
            },
            {"role": "user", "content": user_query}
        ]

        print(f"\n{'='*60}")
        print(f"Query: {user_query}")
        print(f"Model: {model}")
        print(f"{'='*60}")

        # First API call - may trigger tool use
        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        message = response.choices[0].message

        # Check if tool calls were made
        if message.tool_calls:
            print(f"\n[Tool Calling Triggered]")
            messages.append(message)

            for tool_call in message.tool_calls:
                if tool_call.function.name == "search_web":
                    args = json.loads(tool_call.function.arguments)
                    search_query = args.get("query", "")

                    print(f"  - Searching: '{search_query}'")

                    # Execute the search
                    search_results = execute_search(search_query)

                    result["tool_calls"].append({
                        "function": "search_web",
                        "query": search_query,
                        "results_preview": search_results[:500] + "..." if len(search_results) > 500 else search_results
                    })

                    # Add tool response to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": search_results
                    })

            # Second API call - get final response with search results
            final_response = openai_client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )

            result["final_response"] = final_response.choices[0].message.content
        else:
            # No tool calls - direct response
            print(f"\n[No Tool Calling - Direct Response]")
            result["final_response"] = message.content

        print(f"\n[Response Preview]")
        preview = result["final_response"][:500] if result["final_response"] else "No response"
        print(preview + ("..." if len(result["final_response"] or "") > 500 else ""))

    except Exception as e:
        result["error"] = str(e)
        print(f"\n[ERROR] {e}")

    return result


def main():
    """Run test queries and collect results."""

    # Test queries designed to trigger tool calling
    test_queries = [
        # Should trigger tool calling (current events/real-time data)
        "What are the latest developments in AI this week?",
        "What is the current price of Bitcoin?",
        "What's happening in the news today?",

        # May or may not trigger (context dependent)
        "Who won the most recent Super Bowl?",
        "What are the top trending topics on social media right now?",

        # Less likely to trigger (general knowledge)
        "Explain how photosynthesis works",
        "What is the capital of France?",
    ]

    results = []

    print("\n" + "="*70)
    print("LINKUP + OPENAI INTEGRATION TEST")
    print(f"Testing {len(test_queries)} queries with tool calling")
    print("="*70)

    for query in test_queries:
        result = run_query(query)
        results.append(result)
        print("\n")

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    tool_calling_count = sum(1 for r in results if r["tool_calls"])
    direct_response_count = sum(1 for r in results if not r["tool_calls"] and not r["error"])
    error_count = sum(1 for r in results if r["error"])

    print(f"Total queries: {len(results)}")
    print(f"Tool calling triggered: {tool_calling_count}")
    print(f"Direct responses: {direct_response_count}")
    print(f"Errors: {error_count}")

    # Save results to JSON for documentation
    with open("test_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nDetailed results saved to test_results.json")

    return results


if __name__ == "__main__":
    main()
