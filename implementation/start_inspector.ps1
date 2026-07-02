$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ServerPath = Join-Path $ProjectDir "mcp_server.py"

npx -y @modelcontextprotocol/inspector python $ServerPath
