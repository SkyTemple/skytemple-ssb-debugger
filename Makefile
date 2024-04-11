# Makefile for generating files.
# Does NOT install the Python package or dependencies.
# Make sure to install those first and also checkout the submodules.

.PHONY: clean all
.DEFAULT_GOAL: all

rwildcard=$(foreach d,$(wildcard $(1:=/*)),$(call rwildcard,$d,$2) $(filter $(subst *,%,$2),$d))
ALL_BLP=$(call rwildcard,skytemple,*.blp)
ALL_UI=$(ALL_BLP:.blp=.ui)

%.ui: %.blp
	./blueprint-compiler/blueprint-compiler.py compile --output "$@" "$<"

all: $(ALL_UI)

clean:
	find skytemple_ssb_debugger -name "*.ui" -type f -delete
