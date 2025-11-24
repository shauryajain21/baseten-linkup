import os
import json
import time
from datetime import datetime
from openai import OpenAI
from linkup import LinkupClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BASETEN_API_KEY = os.environ.get("BASETEN_API_KEY")
LINKUP_API_KEY = os.environ.get("LINKUP_API_KEY")

if not BASETEN_API_KEY or not LINKUP_API_KEY:
    print("Error: API keys not found. Please check your .env file.")
    exit(1)

MODEL_SLUG = "deepseek-ai/DeepSeek-V3-0324"

# Initialize clients
client = OpenAI(
    api_key=BASETEN_API_KEY,
    base_url="https://inference.baseten.co/v1"
)
linkup = LinkupClient(api_key=LINKUP_API_KEY)

# Tool definition
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
                        "description": "The search query"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# Test queries
TEST_QUERIES = [
    "Explain the core principles of object-oriented programming.",
    "Who was the author of To Kill a Mockingbird?",
    "What are the steps in the scientific method?",
    "Define the concept of 'machine learning bias'.",
    "What is the current price of Bitcoin?",
    "Summarize the latest news headlines regarding climate policy.",
    "Who won the most recent Grand Slam tennis tournament?",
    "What is the forecast for the stock market tomorrow?",
    "How many apples are sold in united states this year",
    "what is nvidia's stock price",
    "what is google's stock price",
    "use linkup to find new math olympiad winners",
    "who won the math olympiad recently",
    "What is the latest version of macbook in the market",
    "How many kids does cristiano Ronaldo has",
    "Do you think Nvidia is going to go up",
    "what are some new restaurants opening in new york",
    "what is the current price of a the flight from new york to new delhi",
    "who is arijit singh",
    "what is the age of shah rukh khan"
]

def run_agent_with_output_type(query, output_type):
    """Run the agent with a specific output_type and return results"""
    today_str = datetime.now().strftime("%B %d, %Y")
    current_year = datetime.now().year

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
        f"   • Mentions 'linkup'\n"
        f"   • Asks about 'what is happening' or 'what's new'\n\n"
        f"3. IMPORTANT: Use the tool EVEN IF you think you know the answer from your training data.\n"
        f"   Your training data is outdated. Real-time search always provides more accurate information.\n\n"
        f"4. When searching, include the current year ({current_year}) in your queries when relevant.\n\n"
        f"5. When in doubt between using your knowledge or the tool, ALWAYS choose the tool.\n\n"
        f"Remember: You have access to real-time information through the search_internet tool. Use it liberally!"
    )

    history = [{"role": "system", "content": system_prompt}]

    # Enhance message to force tool usage
    user_input_lower = query.lower()
    force_tool_keywords = [
        'linkup', 'search', 'look up', 'find out', 'check',
        'latest', 'current', 'recent', 'today', 'now',
        'stock price', 'news', 'weather', 'what is happening',
        'whats new', 'breaking', 'update', 'real-time', 'forecast',
        'price', 'winner', 'won', 'how many', 'age'
    ]

    needs_search = any(keyword in user_input_lower for keyword in force_tool_keywords)

    if needs_search:
        enhanced_message = (
            f"{query}\n\n"
            f"[SYSTEM INSTRUCTION: This query requires real-time information. "
            f"You MUST use the search_internet tool to answer this question.]"
        )
        history.append({"role": "user", "content": enhanced_message})
    else:
        history.append({"role": "user", "content": query})

    # Timing starts
    start_time = time.time()

    # First inference
    response = client.chat.completions.create(
        model=MODEL_SLUG,
        messages=history,
        tools=tools,
        tool_choice="auto"
    )

    message = response.choices[0].message
    tool_used = False
    linkup_latency = 0
    search_query = None

    if message.tool_calls:
        tool_used = True
        history.append(message)

        for tool_call in message.tool_calls:
            if tool_call.function.name == "search_internet":
                args = json.loads(tool_call.function.arguments)
                search_query = args.get("query")

                # Time the Linkup API call
                linkup_start = time.time()
                try:
                    linkup_result = linkup.search(
                        query=search_query,
                        depth="standard",
                        output_type=output_type
                    )
                    linkup_latency = time.time() - linkup_start

                    # Process results based on output_type
                    if output_type == "sourcedAnswer":
                        content = f"Answer: {linkup_result.answer}\nSources: {[s.url for s in linkup_result.sources]}"
                    else:  # searchResults
                        results_text = "\n\n".join([
                            f"Title: {r.name}\nURL: {r.url}\nContent: {r.content}"
                            for r in linkup_result.results
                        ])
                        content = f"Search Results:\n{results_text}"

                except Exception as e:
                    content = f"Error searching: {e}"
                    linkup_latency = time.time() - linkup_start

                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": content
                })

        # Second inference (synthesis)
        final_response = client.chat.completions.create(
            model=MODEL_SLUG,
            messages=history
        )
        final_answer = final_response.choices[0].message.content
    else:
        final_answer = message.content

    total_latency = time.time() - start_time

    return {
        "query": query,
        "output_type": output_type,
        "tool_used": tool_used,
        "search_query": search_query,
        "linkup_latency": round(linkup_latency, 3),
        "total_latency": round(total_latency, 3),
        "answer": final_answer
    }

def main():
    print("=" * 80)
    print("BENCHMARKING: sourcedAnswer vs searchResults")
    print("=" * 80)
    print(f"Testing {len(TEST_QUERIES)} queries with both output types...\n")

    results = []

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\n[{i}/{len(TEST_QUERIES)}] Testing: {query[:60]}...")

        # Test with sourcedAnswer
        print("  → Running with sourcedAnswer...")
        result_sourced = run_agent_with_output_type(query, "sourcedAnswer")
        time.sleep(1)  # Brief pause between calls

        # Test with searchResults
        print("  → Running with searchResults...")
        result_search = run_agent_with_output_type(query, "searchResults")
        time.sleep(1)  # Brief pause between calls

        results.append({
            "query": query,
            "sourcedAnswer": result_sourced,
            "searchResults": result_search
        })

        print(f"  ✓ sourcedAnswer: {result_sourced['total_latency']}s (Linkup: {result_sourced['linkup_latency']}s)")
        print(f"  ✓ searchResults: {result_search['total_latency']}s (Linkup: {result_search['linkup_latency']}s)")

    # Save results to JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"benchmark_results_{timestamp}.json"

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80)

    # Calculate statistics
    sourced_latencies = [r["sourcedAnswer"]["total_latency"] for r in results]
    search_latencies = [r["searchResults"]["total_latency"] for r in results]

    sourced_linkup = [r["sourcedAnswer"]["linkup_latency"] for r in results if r["sourcedAnswer"]["tool_used"]]
    search_linkup = [r["searchResults"]["linkup_latency"] for r in results if r["searchResults"]["tool_used"]]

    print(f"\nTotal Latency Statistics:")
    print(f"  sourcedAnswer - Avg: {sum(sourced_latencies)/len(sourced_latencies):.3f}s, Min: {min(sourced_latencies):.3f}s, Max: {max(sourced_latencies):.3f}s")
    print(f"  searchResults - Avg: {sum(search_latencies)/len(search_latencies):.3f}s, Min: {min(search_latencies):.3f}s, Max: {max(search_latencies):.3f}s")

    if sourced_linkup and search_linkup:
        print(f"\nLinkup API Latency (when tool used):")
        print(f"  sourcedAnswer - Avg: {sum(sourced_linkup)/len(sourced_linkup):.3f}s")
        print(f"  searchResults - Avg: {sum(search_linkup)/len(search_linkup):.3f}s")
        print(f"  Speedup: {((sum(sourced_linkup)/len(sourced_linkup)) / (sum(search_linkup)/len(search_linkup)) - 1) * 100:.1f}% faster")

    print(f"\nDetailed results saved to: {output_file}")
    print("\nGenerating human-readable report...")

    # Generate markdown report
    report_file = f"benchmark_report_{timestamp}.md"
    with open(report_file, 'w') as f:
        f.write("# Benchmark Report: sourcedAnswer vs searchResults\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Model:** {MODEL_SLUG}\n\n")
        f.write(f"**Queries Tested:** {len(TEST_QUERIES)}\n\n")

        f.write("## Summary Statistics\n\n")
        f.write("### Total Latency\n")
        f.write(f"- **sourcedAnswer**: Avg {sum(sourced_latencies)/len(sourced_latencies):.3f}s (Min: {min(sourced_latencies):.3f}s, Max: {max(sourced_latencies):.3f}s)\n")
        f.write(f"- **searchResults**: Avg {sum(search_latencies)/len(search_latencies):.3f}s (Min: {min(search_latencies):.3f}s, Max: {max(search_latencies):.3f}s)\n\n")

        if sourced_linkup and search_linkup:
            f.write("### Linkup API Latency\n")
            f.write(f"- **sourcedAnswer**: Avg {sum(sourced_linkup)/len(sourced_linkup):.3f}s\n")
            f.write(f"- **searchResults**: Avg {sum(search_linkup)/len(search_linkup):.3f}s\n")
            f.write(f"- **Speedup**: {((sum(sourced_linkup)/len(sourced_linkup)) / (sum(search_linkup)/len(search_linkup)) - 1) * 100:.1f}% faster\n\n")

        f.write("## Detailed Results\n\n")

        for i, result in enumerate(results, 1):
            f.write(f"### {i}. {result['query']}\n\n")

            # sourcedAnswer
            f.write("**sourcedAnswer:**\n")
            f.write(f"- Tool Used: {result['sourcedAnswer']['tool_used']}\n")
            if result['sourcedAnswer']['search_query']:
                f.write(f"- Search Query: `{result['sourcedAnswer']['search_query']}`\n")
            f.write(f"- Linkup Latency: {result['sourcedAnswer']['linkup_latency']}s\n")
            f.write(f"- Total Latency: {result['sourcedAnswer']['total_latency']}s\n")
            f.write(f"- Answer: {result['sourcedAnswer']['answer'][:200]}...\n\n")

            # searchResults
            f.write("**searchResults:**\n")
            f.write(f"- Tool Used: {result['searchResults']['tool_used']}\n")
            if result['searchResults']['search_query']:
                f.write(f"- Search Query: `{result['searchResults']['search_query']}`\n")
            f.write(f"- Linkup Latency: {result['searchResults']['linkup_latency']}s\n")
            f.write(f"- Total Latency: {result['searchResults']['total_latency']}s\n")
            f.write(f"- Answer: {result['searchResults']['answer'][:200]}...\n\n")

            # Comparison
            latency_diff = result['sourcedAnswer']['total_latency'] - result['searchResults']['total_latency']
            f.write(f"**Comparison:** searchResults was {latency_diff:.3f}s {'faster' if latency_diff > 0 else 'slower'}\n\n")
            f.write("---\n\n")

    print(f"Human-readable report saved to: {report_file}")

if __name__ == "__main__":
    main()
