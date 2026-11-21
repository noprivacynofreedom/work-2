ATLAS MCP MONITOR — targeted integration patch

WHAT IT DOES
* Launches only MCP servers explicitly listed in settings.json.
* Performs real MCP JSON-RPC initialize and tools/list requests.
* Reports process state, PID, discovered tools, latency, last check and errors.
* Exposes GET /api/mcp/status and POST /api/mcp/check.
* Adds MCP status to /api/health.
* Agents can retrieve authoritative status via GET http://127.0.0.1:8090/api/mcp/status.
* Never labels a server online based on model-generated text.

INSTALL
1. Back up server.py and settings.json.
2. Copy mcp_monitor.py into the project root.
3. Replace server.py with the supplied server.py.
4. Merge the mcp_servers array from settings.example.json into your existing
   settings.json (do not overwrite your other settings).
5. Start Atlas normally. MCP servers are started lazily by POST /api/mcp/check
   or when an agent/UI asks for status with ?refresh=1.
6. Only configure servers you trust. The current mcp_agent.py exposes shell and
   file-writing capabilities; do not enable it without restricting/approving tools.

IMPORTANT
* The archive's mcp_commander.py uses a fixed workspace path and a simplified
  JSON-RPC loop. It may not fully implement current MCP transport semantics.
  The monitor will show protocol errors rather than falsely reporting it online.
* mcp_agent.py requires the MCP Python SDK and exposes terminal/file-write tools.
  It is intentionally NOT enabled by default.
* This patch adds truthful health/status visibility, not full agent tool invocation.
* app.py shutdown integration must call server.stop_mcp_services() if it starts
  MCP children. This patch's MCP processes are owned by server.py and are stopped
  by stop_mcp_services() when the host calls it; standalone server exit hooks also
  attempt cleanup. For best Windows GUI lifecycle, wire that call into app.py's
  existing stop_owned() as described in README.
