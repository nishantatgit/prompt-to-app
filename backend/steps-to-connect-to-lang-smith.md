# LangSmith tracing setup (LangChain / LangGraph)

1. Create an API key
   - LangSmith → Settings (bottom left) → API Keys → Create API Key
   - Type: Personal Access Token, expiry: 1 year
   - Copy it immediately; it is shown only once
   - Do NOT use the agent onboarding wizard

2. Find your region (look at the browser address bar)
   - smith.langchain.com      → https://api.smith.langchain.com
   - eu.smith.langchain.com   → https://eu.api.smith.langchain.com
   - apac.smith.langchain.com → https://apac.api.smith.langchain.com

3. Add exactly these lines to .env
   LANGSMITH_TRACING=true
   LANGSMITH_ENDPOINT=<from step 2>
   LANGSMITH_API_KEY=<from step 1>
   LANGSMITH_PROJECT=<any name you choose, created automatically>
   - Never add LANGSMITH_AGENT_ID or LANGSMITH_AGENT_ENVIRONMENT

4. Load .env into the environment, at the top of the entry point (main.py)
   from pathlib import Path
   from dotenv import load_dotenv
   load_dotenv(Path(__file__).parent / ".env")
   - pydantic-settings alone does NOT do this

5. Check the shell has no old values
   env | grep -E "LANGSMITH|LANGCHAIN"
   - should print nothing; load_dotenv never overrides shell variables

6. Verify (run from the backend folder)
   uv run python -c "
   from dotenv import load_dotenv; load_dotenv('.env')
   from langchain_core.runnables import RunnableLambda
   from langchain_core.tracers.langchain import wait_for_all_tracers
   print(RunnableLambda(lambda x: 'pong').invoke('ping', config={'run_name': 'connection-test'}))
   wait_for_all_tracers()
   "
   - Pass: 'connection-test' appears under Tracing → your project
   - 403 error: endpoint region does not match the key
   - 400 "not both" error: an AGENT_ID variable is set somewhere
   - Nothing appears: wrong project name, or you are inside an agent view
     (close the agent with the × next to Overview)