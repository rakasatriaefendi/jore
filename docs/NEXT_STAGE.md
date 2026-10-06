# Next orchestration stage

v1.6 retains dynamic provider/model discovery and adds the polished interactive
command surface without replacing the proven Auto orchestration path.

Next priorities:

1. retry policy and attempt budget
2. provider failure vs task failure classification
3. failure fingerprint and loop detection
4. automatic free-model switching
5. Codex escalation menu
   - Diagnose
   - Prompt
   - Fix
6. compact RunState / handoff packet
7. provider cooldown handling
8. provider capability layer for MCP, skills, permissions, diff/status/usage
9. persistent AgentHub header/status line inspired by Codex/OpenCode/Claude Code
10. optional semantic/vector memory only if SQLite retrieval becomes insufficient

Do not add a vector database merely for chat history.
