$ErrorActionPreference = "Stop"
# Convert the Blueprint UI files to XML.
# This requires the blueprint-compiler submodule to be checked out.
.\blueprint-compiler\blueprint-compiler.py batch-compile skytemple_ssb_debugger\data\widget skytemple_ssb_debugger\data\widget (Resolve-Path skytemple_ssb_debugger\data\widget\*.blp)
if ($LASTEXITCODE) { exit $LASTEXITCODE }
