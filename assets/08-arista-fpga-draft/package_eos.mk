# Package an ALREADY BUILT BVL PDI. This does not compile any FPGA source.
# Uses OpenFDK 3.2.0 resources/app.mk (13a7aac5); adapt to the delivered BVL FDK.
# make -f package_eos.mk ARISTA_FDK_DIR=/absolute/fdk \
#   PDI_FILE=/absolute/flle_filter-bvl.pdi PORT_DEF_FILE=/absolute/ports.json \
#   EOS_VERSION=<the exact EOS version checked with this BVL FDK and image>
.SECONDEXPANSION:
.DEFAULT_GOAL := all
PROJECT := flle_filter
VERSION_ID := 0.2.0
BUILD_ID := 1
PROJECT_DIR := $(CURDIR)
ARISTA_FDK_DIR ?=
PDI_FILE ?=
PORT_DEF_FILE ?=
EOS_VERSION ?=

ifeq ($(strip $(EOS_VERSION)),)
$(error Provide EOS_VERSION: the exact version checked with this BVL FDK and image)
endif

ifeq ($(wildcard $(ARISTA_FDK_DIR)/resources/app.mk),)
$(error Provide ARISTA_FDK_DIR with resources/app.mk and the matching libapp)
endif
ifeq ($(wildcard $(PDI_FILE)),)
$(error Provide PDI_FILE: a real BVL image built and checked using the licensed FDK)
endif
ifneq ($(suffix $(PDI_FILE)),.pdi)
$(error PDI_FILE must be a .pdi image, not a renamed UltraScale+ .bit)
endif
ifeq ($(wildcard $(PORT_DEF_FILE)),)
$(error Provide PORT_DEF_FILE: port metadata matching that image's actual MAC/PHY)
endif

APP_RPM := $(PROJECT)-$(VERSION_ID).x86_64.rpm
APP_SWIX := $(PROJECT)-$(VERSION_ID).swix
APP_BUILD_SQUASHFS :=
APP_EOS_VERSION := '$(EOS_VERSION)'
BITSTREAMS :=
REGFILES :=
DRIVERFILES :=
# This packaging-only project has no Vivado *-cfg.json. Do not let app.mk
# derive driver register dependencies with a jq invocation reading stdin.
override DRIVER_REGS :=
APPFILES := $(shell find $(ARISTA_FDK_DIR)/resources/libapp -type f ! -name '*.pyc')
APP_CLI_PLUGINS = $(APP_INSTALL_DIR)/eos/FlleFilterCli.py
APP_CLI_EXTENSIONS = $(APP_INSTALL_DIR)/eos/FlleFilter.yaml
APP_DAEMONS = $(APP_INSTALL_DIR)/eos/FlleFilterDaemon.py
RPM_SPEC_FILE = $(BUILD_DIR)/flle_filter.spec
EXTRA_APP_FILES = $(patsubst $(PROJECT_DIR)/eos/%,$(APP_STAGING_DIR)/eos/%,$(wildcard $(PROJECT_DIR)/eos/*.py $(PROJECT_DIR)/eos/*.yaml)) \
    $(APP_STAGING_DIR)/__init__.py $(APP_STAGING_DIR)/LICENSE-Arista-BSD-3-Clause.txt \
    $(APP_STAGING_DIR)/fpga/flle_filter_registers.csv \
    $(APP_STAGING_DIR)/fpga/flle_filter-bvl.pdi $(APP_STAGING_DIR)/fpga/flle_filter-bvl-ports.json

.PHONY: all
all: $(APP_SWIX)

include $(ARISTA_FDK_DIR)/resources/app.mk

# Upstream app.mk creates this symlink with plain "ln -s" when it rebuilds
# the tarball. Remove only our own staging link before each packaging pass.
.PHONY: prepare_cli_stage
$(APP_TARBALL): prepare_cli_stage
prepare_cli_stage:
	python3 -c 'from pathlib import Path; root=Path("$(APP_STAGING_ROOT)").resolve(); link=root/"usr/share/CliExtension/FlleFilter.yaml"; expected="/opt/apps/flle_filter/eos/FlleFilter.yaml"; assert link.parent.resolve().is_relative_to(root), "Staging path escapes its root"; assert not link.exists() or link.is_symlink(), "Refusing to remove a non-symlink"; assert not link.is_symlink() or str(link.readlink()) == expected, "Refusing to remove another application link"; link.unlink() if link.is_symlink() else None'

$(BUILD_RPM): $(RPM_SPEC_FILE)

$(RPM_SPEC_FILE): $(ARISTA_FDK_DIR)/resources/rpm.spec
	@mkdir -p $(@D)
	sed 's/^Summary:.*/Summary: FLLE teaching FPGA filter/' $< > $@

$(APP_STAGING_DIR)/eos/%: $(PROJECT_DIR)/eos/%
	@mkdir -p $(@D)
	cp $< $@

$(APP_STAGING_DIR)/__init__.py:
	@mkdir -p $(@D)
	printf '%s\n' '"""FLLE filter application package."""' > $@

$(APP_STAGING_DIR)/LICENSE-Arista-BSD-3-Clause.txt: $(PROJECT_DIR)/LICENSE-Arista-BSD-3-Clause.txt
	@mkdir -p $(@D)
	cp $< $@

$(APP_STAGING_DIR)/fpga/flle_filter_registers.csv: $(PROJECT_DIR)/flle_filter_registers.csv
	@mkdir -p $(@D)
	cp $< $@

$(APP_STAGING_DIR)/fpga/flle_filter-bvl.pdi: $(PDI_FILE)
	@mkdir -p $(@D)
	cp $< $@

$(APP_STAGING_DIR)/fpga/flle_filter-bvl-ports.json: $(PORT_DEF_FILE)
	@mkdir -p $(@D)
	python3 -m json.tool $< > /dev/null
	cp $< $@
