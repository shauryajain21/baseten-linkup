import os
import json
import sys
from datetime import datetime
from openai import OpenAI
from linkup import LinkupClient
from dotenv import load_dotenv

# --- CONFIGURATION ---
# Load environment variables for secure access
load_dotenv()
BASETEN_API_KEY = os.environ.get("BASETEN_API_KEY")
LINKUP_API_KEY = os.environ.get("LINKUP_API_KEY")

if not BASETEN_API_KEY or not LINKUP_API_KEY:
    print("Error: API keys not found. Please check your .env file.")
    exit(1)

# We leverage DeepSeek-V3 on Baseten for its superior tool-calling capabilities
MODEL_SLUG = "deepseek-ai/DeepSeek-V3-0324"

# --- INITIALIZATION ---
# Baseten provides an OpenAI-compatible endpoint, allowing drop-in replacement
client = OpenAI(
    api_key=BASETEN_API_KEY,
    base_url="https://inference.baseten.co/v1"
)

linkup = LinkupClient(api_key=LINKUP_API_KEY)

# --- TOOL DEFINITION ---
# This schema informs the model about the available external capabilities
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_internet",
            "description": "Use this tool to search for real-time information, news, stock prices, or facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (e.g. 'NVIDIA stock price')"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

def main():
    print(f"--- Serverless Agent (Model: {MODEL_SLUG}) ---")
    print("Type 'quit' to exit.\n")

    # SYSTEM PROMPT ENGINEERING
    # Injecting the current date is critical for the model to understand "fresh" vs "stale" data.
    today_str = datetime.now().strftime("%B %d, %Y")
    current_year = datetime.now().year

    # ENHANCED SYSTEM PROMPT - Fixes tool calling issues
    system_prompt = (
        f"You are a helpful assistant with access to real-time web search via Linkup. Today is {today_str}.\n\n"
        f"CRITICAL INSTRUCTIONS - YOU MUST FOLLOW THESE RULES:\n\n"
        f"1. ALWAYS use the search_internet tool for ANY questions about:\n"
        f"   • Current events, breaking news, or recent developments\n"
        f"   • Stock prices, market data, cryptocurrency prices, or financial information\n"
        f"   • Weather forecasts or current weather conditions\n"
        f"   • Sports scores, schedules, or recent game results\n"
        f"   • Recent publications, articles, books, or media releases\n"
        f"   • Product prices, availability, or reviews\n"
        f"   • Any information that changes over time or requires up-to-date data\n\n"
        f"2. ALWAYS use the search_internet tool when the user:\n"
        f"   • Explicitly asks you to 'search', 'look up', 'find', or 'check'\n"
        f"   • Uses words like 'latest', 'current', 'recent', 'today', 'now'\n"
        f"   • Mentions 'linkup' (Linkup is your search tool - ALWAYS use it when mentioned)\n"
        f"   • Asks about 'what is happening' or 'what's new'\n\n"
        f"3. IMPORTANT: Use the tool EVEN IF you think you know the answer from your training data.\n"
        f"   Your training data is outdated. Real-time search always provides more accurate information.\n\n"
        f"4. When searching, include the current year ({current_year}) in your queries when relevant.\n\n"
        f"5. When in doubt between using your knowledge or the tool, ALWAYS choose the tool.\n\n"
        f"Remember: You have access to real-time information through the search_internet tool. Use it liberally!"
    )

    # Initialize conversation state
    history = [{"role": "system", "content": system_prompt}]

    # Configuration for context management to prevent tool fatigue
    MAX_HISTORY_TURNS = 10

    while True:
        try:
            # 1. Capture User Input
            user_input = input("You: ")
            if user_input.lower() in ["quit", "exit"]:
                print("Goodbye!")
                break

            # KEYWORD DETECTION - Forces tool usage for specific queries
            user_input_lower = user_input.lower()
            force_tool_keywords = [
                'linkup', 'search', 'look up', 'find out', 'check',
                'latest', 'current', 'recent', 'today', 'now',
                'stock price', 'news', 'weather', 'what is happening',
                'whats new', 'breaking', 'update', 'real-time'
            ]

            needs_search = any(keyword in user_input_lower for keyword in force_tool_keywords)

            # Add enhanced message if search keywords detected
            if needs_search:
                enhanced_message = (
                    f"{user_input}\n\n"
                    f"[SYSTEM INSTRUCTION: This query requires real-time information. "
                    f"You MUST use the search_internet tool to answer this question.]"
                )
                history.append({"role": "user", "content": enhanced_message})
            else:
                history.append({"role": "user", "content": user_input})

            # CONTEXT WINDOW MANAGEMENT - Prevents tool fatigue after extended conversations
            if len(history) > (MAX_HISTORY_TURNS * 2) + 1:
                print("ℹ️  Optimizing conversation context...")
                history = [history[0]] + history[-(MAX_HISTORY_TURNS * 2):]

            # 2. Inference Pass 1: Reasoning
            response = client.chat.completions.create(
                model=MODEL_SLUG,
                messages=history,
                tools=tools,
                tool_choice="auto"
            )

            message = response.choices[0].message

            # 3. Tool Execution Logic
            if message.tool_calls:
                print(f"🤖 [Reasoning]: Tool call detected...")

                # Append the model's tool request to the context window
                history.append(message)

                for tool_call in message.tool_calls:
                    if tool_call.function.name == "search_internet":
                        # Parse arguments generated by the model
                        args = json.loads(tool_call.function.arguments)
                        q = args.get("query")

                        print(f"🔍 [Action]: Searching Linkup for '{q}'...")

                        try:
                            # Execute search against Linkup API
                            linkup_result = linkup.search(
                                query=q,
                                depth="standard",
                                output_type="searchResults"
                            )

                            # Structure the retrieved context from search results
                            results_text = "\n\n".join([
                                f"Title: {r.name}\nURL: {r.url}\nContent: {r.content}"
                                for r in linkup_result.results
                            ])
                            content = f"Search Results:\n{results_text}"
                            print("✓ Search completed")

                        except Exception as e:
                            content = f"Error searching: {e}"
                            print(f"✗ Search failed: {e}")

                        # Feed tool output back into the context window
                        history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": content
                        })

                # 4. Inference Pass 2: Synthesis
                final_response = client.chat.completions.create(
                    model=MODEL_SLUG,
                    messages=history
                )
                final_msg = final_response.choices[0].message
                print(f"💡 Agent: {final_msg.content}\n")

                # Update history with final response
                history.append(final_msg)

            else:
                # Direct response path (no tools required)
                print(f"💡 Agent: {message.content}\n")
                history.append(message)

        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
