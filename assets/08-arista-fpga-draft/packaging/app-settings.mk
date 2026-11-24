# FLLE application settings for the unmodified OpenFDK 3.2.0 app.mk.
# Read this file first, then the vendor resources/app.mk with a second -f.
# Declarations only: no recipes, shell functions, include or deployment steps.
# Assumes the src/ tree described in chapter 08, section 4.3.3.
.SECONDEXPANSION:
PROJECT := flle_filter
VERSION_ID := 0.2.0
BUILD_ID := 1
PROJECT_DIR := $(CURDIR)
BUILD_DIR := $(PROJECT_DIR)/build
APP_RPM := flle_filter-0.2.0.x86_64.rpm
APP_SWIX := flle_filter-0.2.0.swix
APP_BUILD_SQUASHFS :=
BITSTREAMS :=
REGFILES :=
DRIVERFILES :=
override DRIVER_REGS :=

# PDI and port JSON are already built; they are ordinary application files.
APPFILES := $(PROJECT_DIR)/src/__init__.py $(PROJECT_DIR)/src/LICENSE-Arista-BSD-3-Clause.txt \
    $(wildcard $(PROJECT_DIR)/src/eos/*.py $(PROJECT_DIR)/src/eos/*.yaml $(PROJECT_DIR)/src/fpga/*) \
    $(wildcard $(ARISTA_FDK_DIR)/resources/libapp/*.py) \
    $(wildcard $(ARISTA_FDK_DIR)/resources/libapp/pcie/*.py) \
    $(wildcard $(ARISTA_FDK_DIR)/resources/libapp/tuning_data/*.csv) \
    $(wildcard $(ARISTA_FDK_DIR)/resources/libapp/clkgen_profiles/*.txt) \
    $(wildcard $(ARISTA_FDK_DIR)/resources/libapp/clkgen_profiles/*.json)
APP_CLI_PLUGINS = $(APP_INSTALL_DIR)/eos/FlleFilterCli.py
APP_CLI_EXTENSIONS = $(APP_INSTALL_DIR)/eos/FlleFilter.yaml
APP_DAEMONS = $(APP_INSTALL_DIR)/eos/FlleFilterDaemon.py
RPM_SPEC_FILE = $(ARISTA_FDK_DIR)/resources/rpm.spec
# The vendor spec expects a summary macro; supply it without editing the spec.
override RPMBUILD = rpmbuild --define="_topdir $(RPMBUILD_DIR)" \
    --define="summary FLLE teaching FPGA filter"
