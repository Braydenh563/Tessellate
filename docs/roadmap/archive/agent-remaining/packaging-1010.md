# Packaging agent, 2026-10-10: what is left

- Docker image not built: `docker` is on PATH but `docker info` reports no daemon here. `docker/Dockerfile` and `docker/compose.yaml` are unbuilt; the first real build may find a path or user-permission slip (`USER mm` and a root-created `/data` volume).
- Docker behind a reverse proxy: `host_allowed` answers 421 for a Host that is a name other than the container's own; a proxy forwarding `memory.example.com` needs an allowed-hosts variable (not built). `core/security.py` HostCheckMiddleware.
- MCP: no `resources` (notes) or `prompts` (skills); startup still loads the embedder (`mcp_server.serve`, `deps.init_app_state`); stdio only, so no packaged-app MCP (`MemoryMap.exe --mcp`) and no `/mcp` HTTP transport. AGENT_SKILLS_REFORM "does the MCP server work" items 4 (partly), 5, 6.
- MCP Settings row (`#mcp-config-group`, `renderMcpSnippet` in `frontend/js/skills.js`) was not opened in a browser; the lints and API test pass, the layout is unmeasured.
- System site-packages: shell launcher only (env variable `MEMORYMAP_SYSTEM_SITE_PACKAGES=1`, not a `--flag`, because the flag-order lint requires start.bat to carry the same flags); start.bat has no equivalent and `start.sh` path was syntax-checked (`bash -n`) and its decision function unit-tested, not run to a built venv.
- Triage-agent lints still red on this branch: README tool count (67) and the networkx conflict marker.
