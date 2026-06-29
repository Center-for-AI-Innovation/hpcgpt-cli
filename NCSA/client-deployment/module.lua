-- Module file for the Delta HPC-GPT OpenCode AI coding agent CLI
local root = "/sw/external/opencode"
local version = "1.17.11"

help([[
Delta HPC-GPT OpenCode AI coding agent CLI

Usage:
  module load hpc-gpt/]] .. version .. [[

  opencode

Documentation: https://opencode.ai/docs
]])

whatis("Name: HPC-GPT opencode")
whatis("Version: " .. version)
whatis("Description: Delta HPC-GPT OpenCode AI coding agent CLI")
whatis("URL: https://opencode.ai")

prepend_path("PATH", pathJoin(root, "bin"))
setenv("OPENCODE_CONFIG", pathJoin(root, "delta-opencode.jsonc")) -- Set this to your own config file
setenv("NCSA_LLM_URL", "https://example.endpoint/v1") -- Set this to your own hosted model URL

if (mode() == "load") then
  -- LmodMsgRaw avoids LmodMessage's line-wrapping ("Fill"), which distorts ASCII art.
  -- Use explicit per-line strings so Lua indentation is not included in the output.
  local banner = table.concat({
    " ____      _ _          _____                     _     ",
    "|    \\ ___| | |_ ___   |  |  |___ ___ ___ ___ ___| |_    ",
    "|  |  | -_| |  _| .'|  |     | . |  _|___| . | . |  _|   ",
    "|____/|___|_|_| |__,|  |__|__|  _|___|   |_  |  _|_|     ",
    "                             |_|         |___|_|         ",
    "       use `opencode` to get started chatting",
    "",
  }, "\n")
  LmodMsgRaw(banner)
end